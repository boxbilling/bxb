import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  UserPlus,
  Eye,
  Percent,
} from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { couponsApi, customersApi, ApiError } from '@/lib/api'
import type {
  Coupon,
  CouponCreate,
  CouponUpdate,
  ApplyCouponRequest,
  AppliedCoupon,
} from '@/types/billing'

function formatCurrency(cents: number | string, currency: string = 'USD'): string {
  const num = typeof cents === 'string' ? parseFloat(cents) : cents
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(num / 100)
}

// --- Create/Edit Coupon Dialog ---
function CouponFormDialog({
  open,
  onOpenChange,
  coupon,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  coupon?: Coupon | null
  onSubmit: (data: CouponCreate | CouponUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<{
    code: string
    name: string
    description: string
    coupon_type: 'fixed_amount' | 'percentage'
    amount_cents: string
    amount_currency: string
    percentage_rate: string
    frequency: 'once' | 'recurring' | 'forever'
    frequency_duration: string
    reusable: boolean
    expiration: 'no_expiration' | 'time_limit'
    expiration_at: string
  }>({
    code: coupon?.code ?? '',
    name: coupon?.name ?? '',
    description: coupon?.description ?? '',
    coupon_type: (coupon?.coupon_type as 'fixed_amount' | 'percentage') ?? 'fixed_amount',
    amount_cents: coupon?.amount_cents ?? '',
    amount_currency: coupon?.amount_currency ?? 'USD',
    percentage_rate: coupon?.percentage_rate ?? '',
    frequency: (coupon?.frequency as 'once' | 'recurring' | 'forever') ?? 'once',
    frequency_duration: coupon?.frequency_duration ? String(coupon.frequency_duration) : '',
    reusable: coupon?.reusable ?? true,
    expiration: (coupon?.expiration as 'no_expiration' | 'time_limit') ?? 'no_expiration',
    expiration_at: coupon?.expiration_at
      ? format(new Date(coupon.expiration_at), "yyyy-MM-dd'T'HH:mm")
      : '',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (coupon) {
      const update: CouponUpdate = {}
      if (formData.name) update.name = formData.name
      if (formData.description) update.description = formData.description
      update.expiration = formData.expiration
      if (formData.expiration === 'time_limit' && formData.expiration_at)
        update.expiration_at = new Date(formData.expiration_at).toISOString()
      onSubmit(update)
    } else {
      const create: CouponCreate = {
        code: formData.code,
        name: formData.name,
        coupon_type: formData.coupon_type,
        frequency: formData.frequency,
        reusable: formData.reusable,
        expiration: formData.expiration,
      }
      if (formData.description) create.description = formData.description
      if (formData.coupon_type === 'fixed_amount') {
        create.amount_cents = formData.amount_cents
        create.amount_currency = formData.amount_currency
      } else {
        create.percentage_rate = formData.percentage_rate
      }
      if (formData.frequency === 'recurring' && formData.frequency_duration)
        create.frequency_duration = parseInt(formData.frequency_duration)
      if (formData.expiration === 'time_limit' && formData.expiration_at)
        create.expiration_at = new Date(formData.expiration_at).toISOString()
      onSubmit(create)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[80vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {coupon ? 'Edit Coupon' : 'Create Coupon'}
            </DialogTitle>
            <DialogDescription>
              {coupon
                ? 'Update coupon settings'
                : 'Create a new discount coupon'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="code">Code *</Label>
                <Input
                  id="code"
                  value={formData.code}
                  onChange={(e) =>
                    setFormData({ ...formData, code: e.target.value })
                  }
                  placeholder="e.g. SUMMER20"
                  disabled={!!coupon}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="e.g. Summer Sale"
                  required
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Optional description"
              />
            </div>
            {!coupon && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="coupon_type">Type *</Label>
                    <Select
                      value={formData.coupon_type}
                      onValueChange={(value: 'fixed_amount' | 'percentage') =>
                        setFormData({ ...formData, coupon_type: value })
                      }
                    >
                      <SelectTrigger id="coupon_type">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="fixed_amount">Fixed Amount</SelectItem>
                        <SelectItem value="percentage">Percentage</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    {formData.coupon_type === 'fixed_amount' ? (
                      <>
                        <Label htmlFor="amount_cents">Amount (cents) *</Label>
                        <Input
                          id="amount_cents"
                          type="number"
                          min="1"
                          value={formData.amount_cents}
                          onChange={(e) =>
                            setFormData({ ...formData, amount_cents: e.target.value })
                          }
                          placeholder="e.g. 1000"
                          required
                        />
                      </>
                    ) : (
                      <>
                        <Label htmlFor="percentage_rate">Percentage *</Label>
                        <Input
                          id="percentage_rate"
                          type="number"
                          step="0.01"
                          min="0.01"
                          max="100"
                          value={formData.percentage_rate}
                          onChange={(e) =>
                            setFormData({ ...formData, percentage_rate: e.target.value })
                          }
                          placeholder="e.g. 20"
                          required
                        />
                      </>
                    )}
                  </div>
                </div>
                {formData.coupon_type === 'fixed_amount' && (
                  <div className="space-y-2">
                    <Label htmlFor="amount_currency">Currency</Label>
                    <Input
                      id="amount_currency"
                      value={formData.amount_currency}
                      onChange={(e) =>
                        setFormData({ ...formData, amount_currency: e.target.value })
                      }
                      placeholder="USD"
                      maxLength={3}
                    />
                  </div>
                )}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="frequency">Frequency *</Label>
                    <Select
                      value={formData.frequency}
                      onValueChange={(value: 'once' | 'recurring' | 'forever') =>
                        setFormData({ ...formData, frequency: value })
                      }
                    >
                      <SelectTrigger id="frequency">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="once">Once</SelectItem>
                        <SelectItem value="recurring">Recurring</SelectItem>
                        <SelectItem value="forever">Forever</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {formData.frequency === 'recurring' && (
                    <div className="space-y-2">
                      <Label htmlFor="frequency_duration">Duration (periods)</Label>
                      <Input
                        id="frequency_duration"
                        type="number"
                        min="1"
                        value={formData.frequency_duration}
                        onChange={(e) =>
                          setFormData({ ...formData, frequency_duration: e.target.value })
                        }
                        placeholder="e.g. 3"
                      />
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="reusable"
                    checked={formData.reusable}
                    onChange={(e) =>
                      setFormData({ ...formData, reusable: e.target.checked })
                    }
                    className="h-4 w-4 rounded border-input"
                  />
                  <Label htmlFor="reusable">Reusable (can be applied to multiple customers)</Label>
                </div>
              </>
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="expiration">Expiration</Label>
                <Select
                  value={formData.expiration}
                  onValueChange={(value: 'no_expiration' | 'time_limit') =>
                    setFormData({ ...formData, expiration: value })
                  }
                >
                  <SelectTrigger id="expiration">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="no_expiration">No Expiration</SelectItem>
                    <SelectItem value="time_limit">Time Limit</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {formData.expiration === 'time_limit' && (
                <div className="space-y-2">
                  <Label htmlFor="expiration_at">Expires At</Label>
                  <Input
                    id="expiration_at"
                    type="datetime-local"
                    value={formData.expiration_at}
                    onChange={(e) =>
                      setFormData({ ...formData, expiration_at: e.target.value })
                    }
                  />
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isLoading || (!coupon && (!formData.code || !formData.name))}
            >
              {isLoading ? 'Saving...' : coupon ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- Apply Coupon Dialog ---
function ApplyCouponDialog({
  open,
  onOpenChange,
  coupon,
  customers,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  coupon: Coupon | null
  customers: Array<{ id: string; name: string }>
  onSubmit: (data: ApplyCouponRequest) => void
  isLoading: boolean
}) {
  const [customerId, setCustomerId] = useState('')
  const [amountOverride, setAmountOverride] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!coupon) return
    const data: ApplyCouponRequest = {
      coupon_code: coupon.code,
      customer_id: customerId,
    }
    if (amountOverride) data.amount_cents = amountOverride
    onSubmit(data)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Apply Coupon</DialogTitle>
            <DialogDescription>
              Apply "{coupon?.name}" to a customer
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {coupon && (
              <div className="rounded-md bg-muted p-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Coupon</span>
                  <span className="font-medium">{coupon.code}</span>
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-muted-foreground">Discount</span>
                  <span className="font-medium">
                    {coupon.coupon_type === 'percentage'
                      ? `${coupon.percentage_rate}%`
                      : formatCurrency(coupon.amount_cents || '0', coupon.amount_currency || 'USD')}
                  </span>
                </div>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="apply_customer">Customer *</Label>
              <Select value={customerId} onValueChange={setCustomerId}>
                <SelectTrigger id="apply_customer">
                  <SelectValue placeholder="Select a customer" />
                </SelectTrigger>
                <SelectContent>
                  {customers.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {coupon?.coupon_type === 'fixed_amount' && (
              <div className="space-y-2">
                <Label htmlFor="amount_override">Amount Override (cents)</Label>
                <Input
                  id="amount_override"
                  type="number"
                  min="1"
                  value={amountOverride}
                  onChange={(e) => setAmountOverride(e.target.value)}
                  placeholder="Leave empty to use default"
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !customerId}>
              {isLoading ? 'Applying...' : 'Apply'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- Applied Coupons Dialog ---
function AppliedCouponsDialog({
  open,
  onOpenChange,
  coupon,
  customers,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  coupon: Coupon | null
  customers: Array<{ id: string; name: string }>
}) {
  // Fetch applied coupons for all customers to find those with this coupon
  // We query each customer's applied coupons, but since we can't filter by coupon,
  // we rely on listing all customers and their coupons
  const customerQueries = customers.map((c) => ({
    id: c.id,
    name: c.name,
  }))

  // Fetch applied coupons for each customer
  const { data: allApplied = [], isLoading } = useQuery({
    queryKey: ['applied-coupons-all'],
    queryFn: async () => {
      const results: Array<AppliedCoupon & { customerName: string }> = []
      for (const c of customerQueries) {
        try {
          const applied = await customersApi.getAppliedCoupons(c.id)
          for (const a of applied) {
            results.push({ ...a, customerName: c.name })
          }
        } catch {
          // skip customers with errors
        }
      }
      return results
    },
    enabled: !!coupon && open,
  })

  const couponApplied = allApplied.filter((a) => a.coupon_id === coupon?.id)

  if (!coupon) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Applied Coupons</DialogTitle>
          <DialogDescription>
            Customers with "{coupon.name}" ({coupon.code}) applied
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Customer</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Frequency</TableHead>
                <TableHead>Remaining</TableHead>
                <TableHead>Applied</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-12" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                  </TableRow>
                ))
              ) : couponApplied.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="h-16 text-center text-muted-foreground"
                  >
                    No customers have this coupon applied
                  </TableCell>
                </TableRow>
              ) : (
                couponApplied.map((applied) => (
                  <TableRow key={applied.id}>
                    <TableCell className="font-medium">
                      {applied.customerName}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={applied.status === 'active' ? 'default' : 'secondary'}
                      >
                        {applied.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{applied.frequency}</TableCell>
                    <TableCell>
                      {applied.frequency_duration_remaining ?? '—'}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {format(new Date(applied.created_at), 'MMM d, yyyy')}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function CouponsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)
  const [editingCoupon, setEditingCoupon] = useState<Coupon | null>(null)
  const [applyCoupon, setApplyCoupon] = useState<Coupon | null>(null)
  const [viewApplied, setViewApplied] = useState<Coupon | null>(null)
  const [terminateCoupon, setTerminateCoupon] = useState<Coupon | null>(null)

  // Fetch coupons
  const {
    data: coupons = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['coupons'],
    queryFn: () => couponsApi.list(),
  })

  // Fetch customers for apply dialog
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  // Filter coupons
  const filteredCoupons = coupons.filter((c) => {
    const matchesSearch =
      !search ||
      c.code.toLowerCase().includes(search.toLowerCase()) ||
      c.name.toLowerCase().includes(search.toLowerCase())
    const matchesStatus =
      statusFilter === 'all' || c.status === statusFilter
    return matchesSearch && matchesStatus
  })

  // Stats
  const stats = {
    total: coupons.length,
    active: coupons.filter((c) => c.status === 'active').length,
    fixed: coupons.filter((c) => c.coupon_type === 'fixed_amount').length,
    percentage: coupons.filter((c) => c.coupon_type === 'percentage').length,
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: CouponCreate) => couponsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['coupons'] })
      setFormOpen(false)
      toast.success('Coupon created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to create coupon'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ code, data }: { code: string; data: CouponUpdate }) =>
      couponsApi.update(code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['coupons'] })
      setEditingCoupon(null)
      setFormOpen(false)
      toast.success('Coupon updated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to update coupon'
      toast.error(message)
    },
  })

  // Terminate mutation
  const terminateMutation = useMutation({
    mutationFn: (code: string) => couponsApi.terminate(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['coupons'] })
      setTerminateCoupon(null)
      toast.success('Coupon terminated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to terminate coupon'
      toast.error(message)
    },
  })

  // Apply mutation
  const applyMutation = useMutation({
    mutationFn: (data: ApplyCouponRequest) => couponsApi.apply(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applied-coupons-all'] })
      setApplyCoupon(null)
      toast.success('Coupon applied successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to apply coupon'
      toast.error(message)
    },
  })

  const handleSubmit = (data: CouponCreate | CouponUpdate) => {
    if (editingCoupon) {
      updateMutation.mutate({ code: editingCoupon.code, data: data as CouponUpdate })
    } else {
      createMutation.mutate(data as CouponCreate)
    }
  }

  const handleEdit = (coupon: Coupon) => {
    setEditingCoupon(coupon)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingCoupon(null)
    }
    setFormOpen(open)
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load coupons. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Coupons</h2>
          <p className="text-muted-foreground">
            Manage discount coupons for customers
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Coupon
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Coupons
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Coupons
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats.active}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Fixed Amount
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.fixed}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Percentage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {stats.percentage}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by code or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="terminated">Terminated</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Discount</TableHead>
              <TableHead>Frequency</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Expiration</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : filteredCoupons.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={8}
                  className="h-24 text-center text-muted-foreground"
                >
                  No coupons found
                </TableCell>
              </TableRow>
            ) : (
              filteredCoupons.map((coupon) => (
                <TableRow key={coupon.id}>
                  <TableCell>
                    <code className="text-sm bg-muted px-1.5 py-0.5 rounded font-medium">
                      {coupon.code}
                    </code>
                  </TableCell>
                  <TableCell className="font-medium">{coupon.name}</TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {coupon.coupon_type === 'fixed_amount' ? 'Fixed' : 'Percentage'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Percent className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="font-medium">
                        {coupon.coupon_type === 'percentage'
                          ? `${coupon.percentage_rate}%`
                          : formatCurrency(coupon.amount_cents || '0', coupon.amount_currency || 'USD')}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{coupon.frequency}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        coupon.status === 'active' ? 'default' : 'secondary'
                      }
                    >
                      {coupon.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {coupon.expiration_at
                      ? format(new Date(coupon.expiration_at), 'MMM d, yyyy')
                      : '—'}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => setViewApplied(coupon)}
                        >
                          <Eye className="mr-2 h-4 w-4" />
                          View Applied
                        </DropdownMenuItem>
                        {coupon.status === 'active' && (
                          <>
                            <DropdownMenuItem
                              onClick={() => handleEdit(coupon)}
                            >
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => setApplyCoupon(coupon)}
                            >
                              <UserPlus className="mr-2 h-4 w-4" />
                              Apply to Customer
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => setTerminateCoupon(coupon)}
                              className="text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Terminate
                            </DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create/Edit Dialog */}
      <CouponFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        coupon={editingCoupon}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Apply Coupon Dialog */}
      <ApplyCouponDialog
        open={!!applyCoupon}
        onOpenChange={(open) => !open && setApplyCoupon(null)}
        coupon={applyCoupon}
        customers={customers.map((c) => ({ id: c.id, name: c.name }))}
        onSubmit={(data) => applyMutation.mutate(data)}
        isLoading={applyMutation.isPending}
      />

      {/* View Applied Coupons Dialog */}
      <AppliedCouponsDialog
        open={!!viewApplied}
        onOpenChange={(open) => !open && setViewApplied(null)}
        coupon={viewApplied}
        customers={customers.map((c) => ({ id: c.id, name: c.name }))}
      />

      {/* Terminate Confirmation */}
      <AlertDialog
        open={!!terminateCoupon}
        onOpenChange={(open) => !open && setTerminateCoupon(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Terminate Coupon</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to terminate "{terminateCoupon?.name}" (
              {terminateCoupon?.code})? This coupon will no longer be applicable
              to new customers.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                terminateCoupon &&
                terminateMutation.mutate(terminateCoupon.code)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {terminateMutation.isPending ? 'Terminating...' : 'Terminate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
