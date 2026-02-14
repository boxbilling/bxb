import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Plus, Search, MoreHorizontal, Pencil, Trash2, Mail, Users, CreditCard, Clock, Globe, ExternalLink, FileText, Receipt, Wallet2, Tag, ScrollText } from 'lucide-react'
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
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { customersApi, subscriptionsApi, invoicesApi, paymentsApi, walletsApi, creditNotesApi, ApiError } from '@/lib/api'
import type { Customer, CustomerCreate, CustomerUpdate, Subscription, Invoice, Payment, Wallet as WalletType, AppliedCoupon, CreditNote } from '@/types/billing'

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(cents / 100)
}

function CustomerFormDialog({
  open,
  onOpenChange,
  customer,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  customer?: Customer | null
  onSubmit: (data: CustomerCreate | CustomerUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<CustomerCreate>({
    external_id: customer?.external_id ?? '',
    name: customer?.name ?? '',
    email: customer?.email ?? undefined,
    currency: customer?.currency ?? 'USD',
    timezone: customer?.timezone ?? 'UTC',
    invoice_grace_period: customer?.invoice_grace_period ?? 0,
    net_payment_term: customer?.net_payment_term ?? 30,
  })
  const [billingMetadataJson, setBillingMetadataJson] = useState(
    customer?.billing_metadata ? JSON.stringify(customer.billing_metadata, null, 2) : ''
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    let billing_metadata: { [key: string]: unknown } | undefined
    if (billingMetadataJson.trim()) {
      try {
        billing_metadata = JSON.parse(billingMetadataJson)
      } catch {
        toast.error('Invalid JSON in billing metadata')
        return
      }
    }
    const data = {
      ...formData,
      invoice_grace_period: Number(formData.invoice_grace_period),
      net_payment_term: Number(formData.net_payment_term),
      ...(billing_metadata !== undefined ? { billing_metadata } : {}),
    }
    onSubmit(data)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {customer ? 'Edit Customer' : 'Create Customer'}
            </DialogTitle>
            <DialogDescription>
              {customer
                ? 'Update customer information'
                : 'Add a new customer to your billing system'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="external_id">External ID *</Label>
                <Input
                  id="external_id"
                  value={formData.external_id}
                  onChange={(e) =>
                    setFormData({ ...formData, external_id: e.target.value })
                  }
                  placeholder="cust_123"
                  required
                  disabled={!!customer}
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
                  placeholder="Acme Corp"
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={formData.email ?? ''}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value || undefined })
                  }
                  placeholder="billing@example.com"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="currency">Currency</Label>
                <Input
                  id="currency"
                  value={formData.currency}
                  onChange={(e) =>
                    setFormData({ ...formData, currency: e.target.value })
                  }
                  placeholder="USD"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Input
                id="timezone"
                value={formData.timezone}
                onChange={(e) =>
                  setFormData({ ...formData, timezone: e.target.value })
                }
                placeholder="UTC"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="invoice_grace_period">Invoice Grace Period (days)</Label>
                <Input
                  id="invoice_grace_period"
                  type="number"
                  value={formData.invoice_grace_period}
                  onChange={(e) =>
                    setFormData({ ...formData, invoice_grace_period: Number(e.target.value) })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="net_payment_term">Net Payment Term (days)</Label>
                <Input
                  id="net_payment_term"
                  type="number"
                  value={formData.net_payment_term}
                  onChange={(e) =>
                    setFormData({ ...formData, net_payment_term: Number(e.target.value) })
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="billing_metadata">Billing Metadata (JSON)</Label>
              <Textarea
                id="billing_metadata"
                value={billingMetadataJson}
                onChange={(e) => setBillingMetadataJson(e.target.value)}
                placeholder='{"key": "value"}'
                rows={3}
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
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Saving...' : customer ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function CustomerSubscriptionsTab({ customerId }: { customerId: string }) {
  const { data: subscriptions, isLoading } = useQuery({
    queryKey: ['customer-subscriptions', customerId],
    queryFn: () => subscriptionsApi.list({ customer_id: customerId }),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (!subscriptions?.length) {
    return <p className="text-sm text-muted-foreground py-4">No subscriptions found</p>
  }

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    active: 'default',
    pending: 'secondary',
    canceled: 'outline',
    terminated: 'destructive',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>External ID</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Started At</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {subscriptions.map((sub) => (
            <TableRow key={sub.id}>
              <TableCell>
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{sub.external_id}</code>
              </TableCell>
              <TableCell>
                <Badge variant={statusVariant[sub.status] ?? 'outline'}>{sub.status}</Badge>
              </TableCell>
              <TableCell>{sub.started_at ? format(new Date(sub.started_at), 'MMM d, yyyy') : '\u2014'}</TableCell>
              <TableCell>{format(new Date(sub.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function CustomerInvoicesTab({ customerId }: { customerId: string }) {
  const { data: invoices, isLoading } = useQuery({
    queryKey: ['customer-invoices', customerId],
    queryFn: () => invoicesApi.list({ customer_id: customerId }),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (!invoices?.length) {
    return <p className="text-sm text-muted-foreground py-4">No invoices found</p>
  }

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    draft: 'secondary',
    finalized: 'outline',
    paid: 'default',
    voided: 'destructive',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Number</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Total</TableHead>
            <TableHead>Issued At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invoices.map((invoice) => (
            <TableRow key={invoice.id}>
              <TableCell>{invoice.invoice_number || '\u2014'}</TableCell>
              <TableCell>
                <Badge variant={statusVariant[invoice.status] ?? 'outline'}>{invoice.status}</Badge>
              </TableCell>
              <TableCell>{formatCurrency(Number(invoice.total), invoice.currency)}</TableCell>
              <TableCell>{invoice.issued_at ? format(new Date(invoice.issued_at), 'MMM d, yyyy') : '\u2014'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function CustomerPaymentsTab({ customerId }: { customerId: string }) {
  const { data: payments, isLoading } = useQuery({
    queryKey: ['customer-payments', customerId],
    queryFn: () => paymentsApi.list({ customer_id: customerId }),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (!payments?.length) {
    return <p className="text-sm text-muted-foreground py-4">No payments found</p>
  }

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    pending: 'secondary',
    processing: 'outline',
    succeeded: 'default',
    failed: 'destructive',
    refunded: 'outline',
    canceled: 'secondary',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Amount</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {payments.map((payment) => (
            <TableRow key={payment.id}>
              <TableCell>{formatCurrency(Number(payment.amount), payment.currency)}</TableCell>
              <TableCell>
                <Badge variant={statusVariant[payment.status] ?? 'outline'}>{payment.status}</Badge>
              </TableCell>
              <TableCell>{payment.provider || '\u2014'}</TableCell>
              <TableCell>{format(new Date(payment.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function CustomerWalletsTab({ customerId }: { customerId: string }) {
  const { data: wallets, isLoading } = useQuery({
    queryKey: ['customer-wallets', customerId],
    queryFn: () => walletsApi.list({ customer_id: customerId }),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (!wallets?.length) {
    return <p className="text-sm text-muted-foreground py-4">No wallets found</p>
  }

  const statusVariant: Record<string, 'default' | 'destructive'> = {
    active: 'default',
    terminated: 'destructive',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Balance</TableHead>
            <TableHead>Credits Balance</TableHead>
            <TableHead>Expiration</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {wallets.map((wallet) => (
            <TableRow key={wallet.id}>
              <TableCell>
                <div>{wallet.name ?? '\u2014'}</div>
                {wallet.code && <div className="text-xs text-muted-foreground">{wallet.code}</div>}
              </TableCell>
              <TableCell>
                <Badge variant={statusVariant[wallet.status] ?? 'outline'}>{wallet.status}</Badge>
              </TableCell>
              <TableCell>{formatCurrency(Number(wallet.balance_cents), wallet.currency)}</TableCell>
              <TableCell>{wallet.credits_balance}</TableCell>
              <TableCell>{wallet.expiration_at ? format(new Date(wallet.expiration_at), 'MMM d, yyyy') : 'Never'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function CustomerCouponsTab({ customerId }: { customerId: string }) {
  const { data: coupons, isLoading } = useQuery({
    queryKey: ['customer-coupons', customerId],
    queryFn: () => customersApi.getAppliedCoupons(customerId),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (!coupons?.length) {
    return <p className="text-sm text-muted-foreground py-4">No applied coupons found</p>
  }

  const statusVariant: Record<string, 'default' | 'destructive'> = {
    active: 'default',
    terminated: 'destructive',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Coupon ID</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {coupons.map((coupon) => (
            <TableRow key={coupon.id}>
              <TableCell>
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                  {coupon.coupon_id.substring(0, 8)}...
                </code>
              </TableCell>
              <TableCell>
                <Badge variant={statusVariant[coupon.status] ?? 'outline'}>{coupon.status}</Badge>
              </TableCell>
              <TableCell>
                {coupon.amount_cents
                  ? formatCurrency(Number(coupon.amount_cents), coupon.amount_currency ?? 'USD')
                  : `${coupon.percentage_rate}%`}
              </TableCell>
              <TableCell>{format(new Date(coupon.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function CustomerCreditNotesTab({ customerId }: { customerId: string }) {
  const { data: creditNotes, isLoading } = useQuery({
    queryKey: ['customer-credit-notes', customerId],
    queryFn: () => creditNotesApi.list({ customer_id: customerId }),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (!creditNotes?.length) {
    return <p className="text-sm text-muted-foreground py-4">No credit notes found</p>
  }

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    draft: 'secondary',
    finalized: 'outline',
    voided: 'destructive',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Number</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Reason</TableHead>
            <TableHead>Credit Amount</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {creditNotes.map((cn) => (
            <TableRow key={cn.id}>
              <TableCell>{cn.number || '\u2014'}</TableCell>
              <TableCell>
                <Badge variant={statusVariant[cn.status] ?? 'outline'}>{cn.status}</Badge>
              </TableCell>
              <TableCell>{cn.reason || '\u2014'}</TableCell>
              <TableCell>{formatCurrency(Number(cn.credit_amount_cents), cn.currency)}</TableCell>
              <TableCell>{format(new Date(cn.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function CustomerDetailSheet({
  open,
  onOpenChange,
  customer,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  customer: Customer | null
}) {
  if (!customer) return null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>{customer.name}</SheetTitle>
          <SheetDescription>
            {customer.external_id}{customer.email ? ` \u2022 ${customer.email}` : ''}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-6 px-4 pb-4">
          <Card>
            <CardHeader>
              <CardTitle>Customer Information</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">External ID</span>
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{customer.external_id}</code>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Email</span>
                  <span>{customer.email ?? '\u2014'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Currency</span>
                  <Badge variant="outline">{customer.currency}</Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Timezone</span>
                  <span>{customer.timezone}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Invoice Grace Period</span>
                  <span>{customer.invoice_grace_period} days</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Net Payment Term</span>
                  <span>{customer.net_payment_term} days</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Billing Metadata</span>
                  {customer.billing_metadata && Object.keys(customer.billing_metadata).length > 0 ? (
                    <pre className="text-xs bg-muted p-2 rounded">{JSON.stringify(customer.billing_metadata, null, 2)}</pre>
                  ) : (
                    <span>None</span>
                  )}
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Created</span>
                  <span>{format(new Date(customer.created_at), 'MMM d, yyyy HH:mm')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Updated</span>
                  <span>{format(new Date(customer.updated_at), 'MMM d, yyyy HH:mm')}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Separator />

          <Tabs defaultValue="subscriptions">
            <TabsList>
              <TabsTrigger value="subscriptions">
                <ScrollText className="mr-2 h-4 w-4" />
                Subscriptions
              </TabsTrigger>
              <TabsTrigger value="invoices">
                <FileText className="mr-2 h-4 w-4" />
                Invoices
              </TabsTrigger>
              <TabsTrigger value="payments">
                <CreditCard className="mr-2 h-4 w-4" />
                Payments
              </TabsTrigger>
              <TabsTrigger value="wallets">
                <Wallet2 className="mr-2 h-4 w-4" />
                Wallets
              </TabsTrigger>
              <TabsTrigger value="coupons">
                <Tag className="mr-2 h-4 w-4" />
                Coupons
              </TabsTrigger>
              <TabsTrigger value="credit-notes">
                <Receipt className="mr-2 h-4 w-4" />
                Credit Notes
              </TabsTrigger>
            </TabsList>
            <TabsContent value="subscriptions">
              <CustomerSubscriptionsTab customerId={customer.id} />
            </TabsContent>
            <TabsContent value="invoices">
              <CustomerInvoicesTab customerId={customer.id} />
            </TabsContent>
            <TabsContent value="payments">
              <CustomerPaymentsTab customerId={customer.id} />
            </TabsContent>
            <TabsContent value="wallets">
              <CustomerWalletsTab customerId={customer.id} />
            </TabsContent>
            <TabsContent value="coupons">
              <CustomerCouponsTab customerId={customer.id} />
            </TabsContent>
            <TabsContent value="credit-notes">
              <CustomerCreditNotesTab customerId={customer.id} />
            </TabsContent>
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default function CustomersPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null)
  const [deleteCustomer, setDeleteCustomer] = useState<Customer | null>(null)
  const [currencyFilter, setCurrencyFilter] = useState<string>('all')
  const [detailCustomer, setDetailCustomer] = useState<Customer | null>(null)

  // Fetch customers from API
  const { data: customers, isLoading, error } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  // Derive unique currencies
  const uniqueCurrencies = [...new Set(customers?.map(c => c.currency) ?? [])]

  // Filter customers by search and currency (client-side)
  const filteredCustomers = customers?.filter((c) => {
    const matchesSearch = !search ||
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.email?.toLowerCase().includes(search.toLowerCase()) ||
      c.external_id.toLowerCase().includes(search.toLowerCase())
    const matchesCurrency = currencyFilter === 'all' || c.currency === currencyFilter
    return matchesSearch && matchesCurrency
  }) ?? []

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: CustomerCreate) => customersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      setFormOpen(false)
      toast.success('Customer created successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create customer'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CustomerUpdate }) =>
      customersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      setEditingCustomer(null)
      setFormOpen(false)
      toast.success('Customer updated successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update customer'
      toast.error(message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => customersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      setDeleteCustomer(null)
      toast.success('Customer deleted successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete customer'
      toast.error(message)
    },
  })

  const handleSubmit = (data: CustomerCreate | CustomerUpdate) => {
    if (editingCustomer) {
      updateMutation.mutate({ id: editingCustomer.id, data })
    } else {
      createMutation.mutate(data as CustomerCreate)
    }
  }

  const handleEdit = (customer: Customer) => {
    setEditingCustomer(customer)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingCustomer(null)
    }
    setFormOpen(open)
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load customers. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Customers</h2>
          <p className="text-muted-foreground">
            Manage your customers and their billing information
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Customer
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Customers</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{customers?.length ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Unique Currencies</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{uniqueCurrencies.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">With Email</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{customers?.filter(c => c.email).length ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recently Added</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{customers?.filter(c => { const d = new Date(c.created_at); const now = new Date(); return (now.getTime() - d.getTime()) < 30 * 24 * 60 * 60 * 1000 }).length ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filter */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search customers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={currencyFilter} onValueChange={setCurrencyFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Currency" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All currencies</SelectItem>
            {uniqueCurrencies.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>External ID</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Timezone</TableHead>
              <TableHead>Currency</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : filteredCustomers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center">
                  No customers found
                </TableCell>
              </TableRow>
            ) : (
              filteredCustomers.map((customer) => (
                <TableRow key={customer.id}>
                  <TableCell>
                    <div className="font-medium">{customer.name}</div>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                      {customer.external_id}
                    </code>
                  </TableCell>
                  <TableCell>
                    {customer.email ? (
                      <div className="flex items-center gap-1 text-sm">
                        <Mail className="h-3 w-3 text-muted-foreground" />
                        {customer.email}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">&mdash;</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className="text-sm">{customer.timezone}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{customer.currency}</Badge>
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setDetailCustomer(customer)}>
                          <ExternalLink className="mr-2 h-4 w-4" />
                          View Details
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleEdit(customer)}>
                          <Pencil className="mr-2 h-4 w-4" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => setDeleteCustomer(customer)}
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
      <CustomerFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        customer={editingCustomer}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteCustomer}
        onOpenChange={(open) => !open && setDeleteCustomer(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Customer</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &ldquo;{deleteCustomer?.name}&rdquo;? This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteCustomer && deleteMutation.mutate(deleteCustomer.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Customer Detail Sheet */}
      <CustomerDetailSheet
        open={!!detailCustomer}
        onOpenChange={(open) => !open && setDetailCustomer(null)}
        customer={detailCustomer}
      />
    </div>
  )
}
