import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { FileText, CreditCard, Wallet2, Tag, ScrollText, Receipt, Calculator } from 'lucide-react'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { customersApi, subscriptionsApi, invoicesApi, paymentsApi, walletsApi, creditNotesApi, taxesApi } from '@/lib/api'
import type { Subscription, Invoice, Payment, Wallet as WalletType, AppliedCoupon, CreditNote, AppliedTax } from '@/types/billing'

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(cents / 100)
}

function CustomerOutstandingBalance({ customerId, currency }: { customerId: string; currency: string }) {
  const { data: invoices } = useQuery({
    queryKey: ['customer-invoices-balance', customerId],
    queryFn: () => invoicesApi.list({ customer_id: customerId }),
  })

  const outstanding = (invoices ?? [])
    .filter((i) => i.status === 'finalized')
    .reduce((sum, i) => sum + Number(i.total), 0)

  const overdue = (invoices ?? [])
    .filter((i) => i.status === 'finalized' && i.due_date && new Date(i.due_date) < new Date())
    .reduce((sum, i) => sum + Number(i.total), 0)

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Outstanding Balance</CardTitle>
          <FileText className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-orange-600">{formatCurrency(outstanding, currency)}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {(invoices ?? []).filter((i) => i.status === 'finalized').length} unpaid invoice(s)
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Overdue Amount</CardTitle>
          <FileText className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${overdue > 0 ? 'text-red-600' : 'text-muted-foreground'}`}>
            {formatCurrency(overdue, currency)}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {(invoices ?? []).filter((i) => i.status === 'finalized' && i.due_date && new Date(i.due_date) < new Date()).length} overdue invoice(s)
          </p>
        </CardContent>
      </Card>
    </div>
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
              <TableCell className="font-mono">{formatCurrency(Number(invoice.total), invoice.currency)}</TableCell>
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
              <TableCell className="font-mono">{formatCurrency(Number(payment.amount), payment.currency)}</TableCell>
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
              <TableCell className="font-mono">{formatCurrency(Number(wallet.balance_cents), wallet.currency)}</TableCell>
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
              <TableCell className="font-mono">
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
              <TableCell className="font-mono">{formatCurrency(Number(cn.credit_amount_cents), cn.currency)}</TableCell>
              <TableCell>{format(new Date(cn.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function formatTaxRate(rate: string | number): string {
  const num = typeof rate === 'string' ? parseFloat(rate) : rate
  return `${(num * 100).toFixed(2)}%`
}

function CustomerTaxesTab({ customerId }: { customerId: string }) {
  const { data: appliedTaxes, isLoading } = useQuery({
    queryKey: ['customer-taxes', customerId],
    queryFn: () => taxesApi.listApplied({ taxable_type: 'customer', taxable_id: customerId }),
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

  if (!appliedTaxes?.length) {
    return <p className="text-sm text-muted-foreground py-4">No taxes applied</p>
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Tax ID</TableHead>
            <TableHead>Rate</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {appliedTaxes.map((at) => (
            <TableRow key={at.id}>
              <TableCell>
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                  {at.tax_id.substring(0, 8)}...
                </code>
              </TableCell>
              <TableCell>{at.tax_rate ? formatTaxRate(at.tax_rate) : '\u2014'}</TableCell>
              <TableCell className="font-mono">{formatCurrency(Number(at.tax_amount_cents))}</TableCell>
              <TableCell>{format(new Date(at.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>()

  const { data: customer, isLoading, error } = useQuery({
    queryKey: ['customer', id],
    queryFn: () => customersApi.get(id!),
    enabled: !!id,
  })

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load customer. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/admin/customers">Customers</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>
              {isLoading ? <Skeleton className="h-4 w-32 inline-block" /> : customer?.name}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {isLoading ? (
        <div className="space-y-6">
          <div>
            <Skeleton className="h-7 w-48 mb-1" />
            <Skeleton className="h-4 w-64" />
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      ) : customer ? (
        <>
          {/* Header */}
          <div>
            <h2 className="text-xl font-semibold tracking-tight">{customer.name}</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              {customer.external_id}{customer.email ? ` \u2022 ${customer.email}` : ''}
            </p>
          </div>

          {/* Outstanding Balance */}
          <CustomerOutstandingBalance customerId={customer.id} currency={customer.currency} />

          {/* Customer Information */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Customer Information</CardTitle>
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

          {/* Related Data Tabs */}
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
              <TabsTrigger value="taxes">
                <Calculator className="mr-2 h-4 w-4" />
                Taxes
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
            <TabsContent value="taxes">
              <CustomerTaxesTab customerId={customer.id} />
            </TabsContent>
          </Tabs>
        </>
      ) : null}
    </div>
  )
}
