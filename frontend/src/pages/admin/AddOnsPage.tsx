import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  UserPlus,
  Gift,
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
import { addOnsApi, customersApi, ApiError } from '@/lib/api'
import type {
  AddOn,
  AddOnCreate,
  AddOnUpdate,
  ApplyAddOnRequest,
} from '@/types/billing'

function formatCurrency(cents: number | string, currency: string = 'USD'): string {
  const num = typeof cents === 'string' ? parseFloat(cents) : cents
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(num / 100)
}

// --- Create/Edit Add-on Dialog ---
function AddOnFormDialog({
  open,
  onOpenChange,
  addOn,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  addOn?: AddOn | null
  onSubmit: (data: AddOnCreate | AddOnUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<{
    code: string
    name: string
    description: string
    amount_cents: string
    amount_currency: string
    invoice_display_name: string
  }>({
    code: addOn?.code ?? '',
    name: addOn?.name ?? '',
    description: addOn?.description ?? '',
    amount_cents: addOn?.amount_cents ?? '',
    amount_currency: addOn?.amount_currency ?? 'USD',
    invoice_display_name: addOn?.invoice_display_name ?? '',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (addOn) {
      const update: AddOnUpdate = {}
      if (formData.name) update.name = formData.name
      if (formData.description) update.description = formData.description
      if (formData.amount_cents) update.amount_cents = formData.amount_cents
      if (formData.amount_currency) update.amount_currency = formData.amount_currency
      if (formData.invoice_display_name) update.invoice_display_name = formData.invoice_display_name
      onSubmit(update)
    } else {
      const create: AddOnCreate = {
        code: formData.code,
        name: formData.name,
        amount_cents: formData.amount_cents,
        amount_currency: formData.amount_currency,
      }
      if (formData.description) create.description = formData.description
      if (formData.invoice_display_name) create.invoice_display_name = formData.invoice_display_name
      onSubmit(create)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {addOn ? 'Edit Add-on' : 'Create Add-on'}
            </DialogTitle>
            <DialogDescription>
              {addOn
                ? 'Update add-on settings'
                : 'Create a new one-time add-on charge'}
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
                  placeholder="e.g. setup-fee"
                  disabled={!!addOn}
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
                  placeholder="e.g. Setup Fee"
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
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="amount_cents">Amount (cents) *</Label>
                <Input
                  id="amount_cents"
                  type="number"
                  min="1"
                  value={formData.amount_cents}
                  onChange={(e) =>
                    setFormData({ ...formData, amount_cents: e.target.value })
                  }
                  placeholder="e.g. 5000"
                  required
                />
              </div>
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
            </div>
            <div className="space-y-2">
              <Label htmlFor="invoice_display_name">Invoice Display Name</Label>
              <Input
                id="invoice_display_name"
                value={formData.invoice_display_name}
                onChange={(e) =>
                  setFormData({ ...formData, invoice_display_name: e.target.value })
                }
                placeholder="Name shown on invoice"
              />
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
              disabled={isLoading || (!addOn && (!formData.code || !formData.name || !formData.amount_cents))}
            >
              {isLoading ? 'Saving...' : addOn ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- Apply Add-on Dialog ---
function ApplyAddOnDialog({
  open,
  onOpenChange,
  addOn,
  customers,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  addOn: AddOn | null
  customers: Array<{ id: string; name: string }>
  onSubmit: (data: ApplyAddOnRequest) => void
  isLoading: boolean
}) {
  const [customerId, setCustomerId] = useState('')
  const [amountOverride, setAmountOverride] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!addOn) return
    const data: ApplyAddOnRequest = {
      add_on_code: addOn.code,
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
            <DialogTitle>Apply Add-on</DialogTitle>
            <DialogDescription>
              Apply "{addOn?.name}" to a customer
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {addOn && (
              <div className="rounded-md bg-muted p-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Add-on</span>
                  <span className="font-medium">{addOn.code}</span>
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-muted-foreground">Amount</span>
                  <span className="font-medium">
                    {formatCurrency(addOn.amount_cents, addOn.amount_currency)}
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

export default function AddOnsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [editingAddOn, setEditingAddOn] = useState<AddOn | null>(null)
  const [applyAddOn, setApplyAddOn] = useState<AddOn | null>(null)
  const [deleteAddOn, setDeleteAddOn] = useState<AddOn | null>(null)

  // Fetch add-ons
  const {
    data: addOns = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['add-ons'],
    queryFn: () => addOnsApi.list(),
  })

  // Fetch customers for apply dialog
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  // Filter add-ons
  const filteredAddOns = addOns.filter((a) => {
    return (
      !search ||
      a.code.toLowerCase().includes(search.toLowerCase()) ||
      a.name.toLowerCase().includes(search.toLowerCase())
    )
  })

  // Stats
  const currencies = [...new Set(addOns.map((a) => a.amount_currency))]
  const stats = {
    total: addOns.length,
    currencies: currencies.length,
    avgAmount:
      addOns.length > 0
        ? addOns.reduce(
            (sum, a) => sum + (typeof a.amount_cents === 'string' ? parseFloat(a.amount_cents) : a.amount_cents),
            0
          ) / addOns.length
        : 0,
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: AddOnCreate) => addOnsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['add-ons'] })
      setFormOpen(false)
      toast.success('Add-on created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to create add-on'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ code, data }: { code: string; data: AddOnUpdate }) =>
      addOnsApi.update(code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['add-ons'] })
      setEditingAddOn(null)
      setFormOpen(false)
      toast.success('Add-on updated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to update add-on'
      toast.error(message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (code: string) => addOnsApi.delete(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['add-ons'] })
      setDeleteAddOn(null)
      toast.success('Add-on deleted successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to delete add-on'
      toast.error(message)
    },
  })

  // Apply mutation
  const applyMutation = useMutation({
    mutationFn: (data: ApplyAddOnRequest) => addOnsApi.apply(data),
    onSuccess: () => {
      setApplyAddOn(null)
      toast.success('Add-on applied successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to apply add-on'
      toast.error(message)
    },
  })

  const handleSubmit = (data: AddOnCreate | AddOnUpdate) => {
    if (editingAddOn) {
      updateMutation.mutate({ code: editingAddOn.code, data: data as AddOnUpdate })
    } else {
      createMutation.mutate(data as AddOnCreate)
    }
  }

  const handleEdit = (addOn: AddOn) => {
    setEditingAddOn(addOn)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingAddOn(null)
    }
    setFormOpen(open)
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load add-ons. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Add-ons</h2>
          <p className="text-muted-foreground">
            Manage one-time add-on charges
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Add-on
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Add-ons
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Currencies
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.currencies}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Average Amount
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(stats.avgAmount)}
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
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Currency</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : filteredAddOns.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="h-24 text-center text-muted-foreground"
                >
                  No add-ons found
                </TableCell>
              </TableRow>
            ) : (
              filteredAddOns.map((addOn) => (
                <TableRow key={addOn.id}>
                  <TableCell>
                    <code className="text-sm bg-muted px-1.5 py-0.5 rounded font-medium">
                      {addOn.code}
                    </code>
                  </TableCell>
                  <TableCell className="font-medium">{addOn.name}</TableCell>
                  <TableCell className="text-muted-foreground text-sm max-w-[200px] truncate">
                    {addOn.description || '—'}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Gift className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="font-medium">
                        {formatCurrency(addOn.amount_cents, addOn.amount_currency)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{addOn.amount_currency}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {format(new Date(addOn.created_at), 'MMM d, yyyy')}
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
                          onClick={() => handleEdit(addOn)}
                        >
                          <Pencil className="mr-2 h-4 w-4" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setApplyAddOn(addOn)}
                        >
                          <UserPlus className="mr-2 h-4 w-4" />
                          Apply to Customer
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setDeleteAddOn(addOn)}
                          className="text-destructive"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
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
      <AddOnFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        addOn={editingAddOn}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Apply Add-on Dialog */}
      <ApplyAddOnDialog
        open={!!applyAddOn}
        onOpenChange={(open) => !open && setApplyAddOn(null)}
        addOn={applyAddOn}
        customers={customers.map((c) => ({ id: c.id, name: c.name }))}
        onSubmit={(data) => applyMutation.mutate(data)}
        isLoading={applyMutation.isPending}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteAddOn}
        onOpenChange={(open) => !open && setDeleteAddOn(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Add-on</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deleteAddOn?.name}" (
              {deleteAddOn?.code})? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteAddOn && deleteMutation.mutate(deleteAddOn.code)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
