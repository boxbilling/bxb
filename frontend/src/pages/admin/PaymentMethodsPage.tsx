import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, CreditCard, Landmark, Star, Trash2 } from 'lucide-react'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { customersApi, paymentMethodsApi, ApiError } from '@/lib/api'
import type { PaymentMethod, PaymentMethodCreate } from '@/types/billing'

const providerLabels: Record<string, string> = {
  stripe: 'Stripe',
  gocardless: 'GoCardless',
  adyen: 'Adyen',
}

const providerVariants: Record<string, 'default' | 'secondary' | 'outline'> = {
  stripe: 'default',
  gocardless: 'secondary',
  adyen: 'outline',
}

function formatDetails(method: PaymentMethod): string {
  const details = method.details as { last4?: string; brand?: string; exp_month?: number; exp_year?: number } | null
  if (!details) return method.type
  if (details.brand && details.last4) {
    const parts = [`${details.brand} ending in ${details.last4}`]
    if (details.exp_month && details.exp_year) {
      parts.push(`exp ${String(details.exp_month).padStart(2, '0')}/${String(details.exp_year).slice(-2)}`)
    }
    return parts.join(', ')
  }
  if (details.last4) return `**** ${details.last4}`
  return method.type
}

function PaymentMethodFormDialog({
  open,
  onOpenChange,
  onSubmit,
  isLoading,
  customers,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: PaymentMethodCreate) => void
  isLoading: boolean
  customers: { id: string; name: string }[]
}) {
  const [formData, setFormData] = useState<PaymentMethodCreate>({
    customer_id: '',
    provider: 'stripe',
    provider_payment_method_id: '',
    type: 'card',
    is_default: false,
    details: {},
  })
  const [last4, setLast4] = useState('')
  const [brand, setBrand] = useState('')
  const [expMonth, setExpMonth] = useState('')
  const [expYear, setExpYear] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const details: Record<string, unknown> = {}
    if (last4) details.last4 = last4
    if (brand) details.brand = brand
    if (expMonth) details.exp_month = Number(expMonth)
    if (expYear) details.exp_year = Number(expYear)
    onSubmit({ ...formData, details })
  }

  const resetForm = () => {
    setFormData({
      customer_id: '',
      provider: 'stripe',
      provider_payment_method_id: '',
      type: 'card',
      is_default: false,
      details: {},
    })
    setLast4('')
    setBrand('')
    setExpMonth('')
    setExpYear('')
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen) resetForm()
        onOpenChange(isOpen)
      }}
    >
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add Payment Method</DialogTitle>
            <DialogDescription>
              Register a new payment method for a customer
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="pm-customer">Customer *</Label>
              <Select
                value={formData.customer_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, customer_id: value })
                }
              >
                <SelectTrigger id="pm-customer">
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

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pm-provider">Provider *</Label>
                <Select
                  value={formData.provider}
                  onValueChange={(value) =>
                    setFormData({ ...formData, provider: value })
                  }
                >
                  <SelectTrigger id="pm-provider">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="stripe">Stripe</SelectItem>
                    <SelectItem value="gocardless">GoCardless</SelectItem>
                    <SelectItem value="adyen">Adyen</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="pm-type">Type *</Label>
                <Select
                  value={formData.type}
                  onValueChange={(value) =>
                    setFormData({ ...formData, type: value })
                  }
                >
                  <SelectTrigger id="pm-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="card">Card</SelectItem>
                    <SelectItem value="bank_account">Bank Account</SelectItem>
                    <SelectItem value="direct_debit">Direct Debit</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="pm-provider-id">Provider Payment Method ID *</Label>
              <Input
                id="pm-provider-id"
                value={formData.provider_payment_method_id}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    provider_payment_method_id: e.target.value,
                  })
                }
                placeholder="pm_1234567890"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pm-brand">Card Brand</Label>
                <Input
                  id="pm-brand"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  placeholder="Visa"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pm-last4">Last 4 Digits</Label>
                <Input
                  id="pm-last4"
                  value={last4}
                  onChange={(e) => setLast4(e.target.value)}
                  placeholder="4242"
                  maxLength={4}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pm-exp-month">Expiry Month</Label>
                <Input
                  id="pm-exp-month"
                  type="number"
                  value={expMonth}
                  onChange={(e) => setExpMonth(e.target.value)}
                  placeholder="12"
                  min={1}
                  max={12}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pm-exp-year">Expiry Year</Label>
                <Input
                  id="pm-exp-year"
                  type="number"
                  value={expYear}
                  onChange={(e) => setExpYear(e.target.value)}
                  placeholder="2025"
                />
              </div>
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
              disabled={isLoading || !formData.customer_id || !formData.provider_payment_method_id}
            >
              {isLoading ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function PaymentMethodsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [customerFilter, setCustomerFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)
  const [deleteMethod, setDeleteMethod] = useState<PaymentMethod | null>(null)
  const [setDefaultMethod, setSetDefaultMethod] = useState<PaymentMethod | null>(null)

  // Fetch payment methods
  const { data: paymentMethods = [], isLoading } = useQuery({
    queryKey: ['payment-methods', customerFilter],
    queryFn: () =>
      paymentMethodsApi.list(
        customerFilter !== 'all' ? { customer_id: customerFilter } : undefined
      ),
  })

  // Fetch customers for display and filtering
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  const customerMap = new Map(customers.map((c) => [c.id, c]))

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: PaymentMethodCreate) => paymentMethodsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] })
      setFormOpen(false)
      toast.success('Payment method created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to create payment method'
      toast.error(message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => paymentMethodsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] })
      setDeleteMethod(null)
      toast.success('Payment method deleted successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to delete payment method'
      toast.error(message)
    },
  })

  // Set default mutation
  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => paymentMethodsApi.setDefault(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] })
      setSetDefaultMethod(null)
      toast.success('Default payment method updated')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to set default payment method'
      toast.error(message)
    },
  })

  // Filter by search
  const filteredMethods = paymentMethods.filter((pm) => {
    if (!search) return true
    const customer = customerMap.get(pm.customer_id)
    const customerName = customer?.name?.toLowerCase() ?? ''
    const details = formatDetails(pm).toLowerCase()
    const searchLower = search.toLowerCase()
    return customerName.includes(searchLower) || details.includes(searchLower)
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Payment Methods</h1>
          <p className="text-muted-foreground">
            Manage customer payment methods
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Payment Method
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search payment methods..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={customerFilter} onValueChange={setCustomerFilter}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Filter by customer" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Customers</SelectItem>
            {customers.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Details</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Default</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                </TableRow>
              ))
            ) : filteredMethods.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                  No payment methods found
                </TableCell>
              </TableRow>
            ) : (
              filteredMethods.map((pm) => {
                const customer = customerMap.get(pm.customer_id)
                return (
                  <TableRow key={pm.id}>
                    <TableCell className="font-medium">
                      {customer?.name ?? pm.customer_id.slice(0, 8)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        {pm.type === 'card' ? (
                          <CreditCard className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <Landmark className="h-4 w-4 text-muted-foreground" />
                        )}
                        <span className="text-sm">
                          {pm.type === 'bank_account'
                            ? 'Bank Account'
                            : pm.type === 'direct_debit'
                              ? 'Direct Debit'
                              : 'Card'}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm">{formatDetails(pm)}</span>
                    </TableCell>
                    <TableCell>
                      <Badge variant={providerVariants[pm.provider] ?? 'outline'}>
                        {providerLabels[pm.provider] ?? pm.provider}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {pm.is_default && (
                        <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {format(new Date(pm.created_at), 'MMM d, yyyy')}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {!pm.is_default && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setSetDefaultMethod(pm)}
                            title="Set as default"
                          >
                            <Star className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteMethod(pm)}
                          disabled={pm.is_default}
                          title={pm.is_default ? 'Cannot delete default payment method' : 'Delete'}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Add Payment Method Dialog */}
      <PaymentMethodFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
        customers={customers.map((c) => ({ id: c.id, name: c.name }))}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteMethod}
        onOpenChange={(open) => !open && setDeleteMethod(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Payment Method</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this payment method? This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteMethod && deleteMutation.mutate(deleteMethod.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Set Default Confirmation */}
      <AlertDialog
        open={!!setDefaultMethod}
        onOpenChange={(open) => !open && setSetDefaultMethod(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Set as Default</AlertDialogTitle>
            <AlertDialogDescription>
              Set this payment method as the default for{' '}
              {customerMap.get(setDefaultMethod?.customer_id ?? '')?.name ??
                'this customer'}
              ? The current default will be unset.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                setDefaultMethod &&
                setDefaultMutation.mutate(setDefaultMethod.id)
              }
            >
              {setDefaultMutation.isPending ? 'Updating...' : 'Set Default'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
