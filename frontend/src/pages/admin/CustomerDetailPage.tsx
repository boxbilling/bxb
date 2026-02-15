import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { FileText, CreditCard, Wallet2, Tag, ScrollText, Landmark, Star, Trash2, Plus, ExternalLink, Copy, Check, Pencil, History } from 'lucide-react'
import { Bar, BarChart, XAxis, YAxis, CartesianGrid } from 'recharts'
import { toast } from 'sonner'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { CustomerFormDialog } from '@/components/CustomerFormDialog'
import { CustomerAvatar } from '@/components/CustomerAvatar'
import { CustomerHealthBadge } from '@/components/CustomerHealthBadge'
import { CardBrandIcon } from '@/components/CardBrandIcon'
import { PaymentMethodFormDialog } from '@/components/PaymentMethodFormDialog'
import { AuditTrailTimeline } from '@/components/AuditTrailTimeline'
import { customersApi, subscriptionsApi, invoicesApi, paymentsApi, walletsApi, creditNotesApi, feesApi, paymentMethodsApi, plansApi, ApiError } from '@/lib/api'
import { SubscriptionFormDialog } from '@/components/SubscriptionFormDialog'
import type { Subscription, Invoice, Payment, Wallet as WalletType, AppliedCoupon, CreditNote, CustomerCurrentUsageResponse, PaymentMethod, PaymentMethodCreate, CustomerUpdate, SubscriptionCreate } from '@/types/billing'

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


function CustomerFeesTab({ customerId }: { customerId: string }) {
  const { data: fees, isLoading } = useQuery({
    queryKey: ['customer-fees', customerId],
    queryFn: () => feesApi.list({ customer_id: customerId }),
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

  if (!fees?.length) {
    return <p className="text-sm text-muted-foreground py-4">No fees found</p>
  }

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    pending: 'secondary',
    succeeded: 'default',
    failed: 'destructive',
    refunded: 'outline',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Type</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Payment Status</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {fees.map((fee) => (
            <TableRow key={fee.id}>
              <TableCell>
                <Badge variant="outline">{fee.fee_type}</Badge>
              </TableCell>
              <TableCell>{fee.description || fee.metric_code || '\u2014'}</TableCell>
              <TableCell>
                <Badge variant={statusVariant[fee.payment_status] ?? 'outline'}>{fee.payment_status}</Badge>
              </TableCell>
              <TableCell className="font-mono">{formatCurrency(Number(fee.total_amount_cents))}</TableCell>
              <TableCell>{format(new Date(fee.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function CustomerActivityTab({ customerId }: { customerId: string }) {
  return (
    <div className="space-y-4">
      <AuditTrailTimeline
        resourceType="customer"
        resourceId={customerId}
        limit={50}
        showViewAll
      />
    </div>
  )
}

function CustomerPaymentMethodsCard({ customerId, customerName }: { customerId: string; customerName: string }) {
  const queryClient = useQueryClient()
  const [deleteMethod, setDeleteMethod] = useState<PaymentMethod | null>(null)
  const [addFormOpen, setAddFormOpen] = useState(false)

  const { data: paymentMethods, isLoading } = useQuery({
    queryKey: ['customer-payment-methods', customerId],
    queryFn: () => paymentMethodsApi.list({ customer_id: customerId }),
  })

  const createMutation = useMutation({
    mutationFn: (data: PaymentMethodCreate) => paymentMethodsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-payment-methods', customerId] })
      setAddFormOpen(false)
      toast.success('Payment method added')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to add payment method')
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => paymentMethodsApi.setDefault(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-payment-methods', customerId] })
      toast.success('Default payment method updated')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to set default payment method')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => paymentMethodsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-payment-methods', customerId] })
      setDeleteMethod(null)
      toast.success('Payment method removed')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to remove payment method')
    },
  })

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-sm font-medium">Payment Methods</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setAddFormOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Payment Method
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : !paymentMethods?.length ? (
            <p className="text-sm text-muted-foreground py-4">No payment methods found</p>
          ) : (
            <div className="space-y-3">
              {paymentMethods.map((pm) => {
                const details = pm.details as { last4?: string; brand?: string; exp_month?: number; exp_year?: number } | null
                const brand = details?.brand
                const last4 = details?.last4
                const expMonth = details?.exp_month
                const expYear = details?.exp_year

                return (
                  <div
                    key={pm.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="flex items-center gap-3">
                      {pm.type === 'card' && brand ? (
                        <CardBrandIcon brand={brand} size={28} />
                      ) : pm.type === 'card' ? (
                        <CreditCard className="h-6 w-6 text-muted-foreground" />
                      ) : (
                        <Landmark className="h-6 w-6 text-muted-foreground" />
                      )}
                      <div>
                        {last4 ? (
                          <div className="font-mono text-sm font-semibold tracking-wider">
                            {'•••• •••• •••• '}{last4}
                            {expMonth && expYear && (
                              <span className="ml-2 text-xs text-muted-foreground font-normal tracking-normal">
                                {String(expMonth).padStart(2, '0')}/{String(expYear).slice(-2)}
                              </span>
                            )}
                          </div>
                        ) : (
                          <div className="text-sm font-medium">
                            {pm.type === 'bank_account' ? 'Bank Account' : pm.type === 'direct_debit' ? 'Direct Debit' : 'Card'}
                          </div>
                        )}
                        <div className="text-xs text-muted-foreground">
                          {pm.provider}
                        </div>
                      </div>
                      {pm.is_default && (
                        <Badge variant="secondary" className="ml-2">Default</Badge>
                      )}
                    </div>
                    <div className="flex gap-1">
                      {!pm.is_default && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDefaultMutation.mutate(pm.id)}
                          disabled={setDefaultMutation.isPending}
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
                        title={pm.is_default ? 'Cannot remove default payment method' : 'Remove'}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <PaymentMethodFormDialog
        open={addFormOpen}
        onOpenChange={setAddFormOpen}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
        customers={[{ id: customerId, name: customerName }]}
        defaultCustomerId={customerId}
      />

      <AlertDialog
        open={!!deleteMethod}
        onOpenChange={(open) => !open && setDeleteMethod(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Payment Method</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove this payment method? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMethod && deleteMutation.mutate(deleteMethod.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Removing...' : 'Remove'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

function ChargeUsageTable({ charges, currency }: { charges: CustomerCurrentUsageResponse['charges']; currency: string }) {
  if (!charges.length) {
    return <p className="text-sm text-muted-foreground py-2">No charge data</p>
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Metric</TableHead>
            <TableHead>Units</TableHead>
            <TableHead>Charge Model</TableHead>
            <TableHead className="text-right">Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {charges.map((charge, idx) => (
            <TableRow key={`${charge.billable_metric.code}-${idx}`}>
              <TableCell>
                <div>{charge.billable_metric.name}</div>
                <div className="text-xs text-muted-foreground">{charge.billable_metric.code}</div>
              </TableCell>
              <TableCell className="font-mono">{charge.units}</TableCell>
              <TableCell>
                <Badge variant="outline">{charge.charge_model}</Badge>
              </TableCell>
              <TableCell className="text-right font-mono">{formatCurrency(Number(charge.amount_cents), currency)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

const pastUsageChartConfig = {
  amount: {
    label: 'Amount',
    color: 'hsl(var(--primary))',
  },
} satisfies ChartConfig

function CustomerUsageTab({ customerId, externalId }: { customerId: string; externalId: string }) {
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string>('')

  const { data: subscriptions, isLoading: subsLoading } = useQuery({
    queryKey: ['customer-subscriptions', customerId],
    queryFn: () => subscriptionsApi.list({ customer_id: customerId }),
  })

  const selectedSubscription = subscriptions?.find((s) => s.external_id === selectedSubscriptionId)

  const { data: currentUsage, isLoading: currentLoading } = useQuery({
    queryKey: ['customer-usage', externalId, selectedSubscriptionId],
    queryFn: () => customersApi.getCurrentUsage(externalId, selectedSubscriptionId),
    enabled: !!selectedSubscriptionId,
  })

  const { data: projectedUsage, isLoading: projectedLoading } = useQuery({
    queryKey: ['customer-projected-usage', externalId, selectedSubscriptionId],
    queryFn: () => customersApi.getProjectedUsage(externalId, selectedSubscriptionId),
    enabled: !!selectedSubscriptionId,
  })

  const { data: pastUsage, isLoading: pastLoading } = useQuery({
    queryKey: ['customer-past-usage', externalId, selectedSubscriptionId],
    queryFn: () => customersApi.getPastUsage(externalId, selectedSubscriptionId, 3),
    enabled: !!selectedSubscriptionId,
  })

  if (subsLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (!subscriptions?.length) {
    return <p className="text-sm text-muted-foreground py-4">No subscriptions found. Usage data requires an active subscription.</p>
  }

  const chartData = (pastUsage ?? []).map((period) => ({
    period: `${format(new Date(period.from_datetime), 'MMM d')} – ${format(new Date(period.to_datetime), 'MMM d')}`,
    amount: Number(period.amount_cents) / 100,
  }))

  return (
    <div className="space-y-6">
      {/* Subscription Selector */}
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium">Subscription:</span>
        <Select value={selectedSubscriptionId} onValueChange={setSelectedSubscriptionId}>
          <SelectTrigger className="w-[280px]">
            <SelectValue placeholder="Select a subscription" />
          </SelectTrigger>
          <SelectContent>
            {subscriptions.map((sub) => (
              <SelectItem key={sub.id} value={sub.external_id}>
                {sub.external_id} ({sub.status})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {!selectedSubscriptionId ? (
        <p className="text-sm text-muted-foreground py-4">Select a subscription to view usage data.</p>
      ) : (
        <div className="space-y-6">
          {/* Current Usage */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Current Usage</CardTitle>
            </CardHeader>
            <CardContent>
              {currentLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : currentUsage ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-muted-foreground">Period:</span>
                    <span>
                      {format(new Date(currentUsage.from_datetime), 'MMM d, yyyy')} – {format(new Date(currentUsage.to_datetime), 'MMM d, yyyy')}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-muted-foreground">Total:</span>
                    <span className="text-lg font-semibold">{formatCurrency(Number(currentUsage.amount_cents), currentUsage.currency)}</span>
                  </div>
                  <ChargeUsageTable charges={currentUsage.charges} currency={currentUsage.currency} />
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No current usage data available.</p>
              )}
            </CardContent>
          </Card>

          {/* Projected Usage */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Projected Usage</CardTitle>
            </CardHeader>
            <CardContent>
              {projectedLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : projectedUsage ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-muted-foreground">Projected Period:</span>
                    <span>
                      {format(new Date(projectedUsage.from_datetime), 'MMM d, yyyy')} – {format(new Date(projectedUsage.to_datetime), 'MMM d, yyyy')}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-muted-foreground">Projected Total:</span>
                    <span className="text-lg font-semibold">{formatCurrency(Number(projectedUsage.amount_cents), projectedUsage.currency)}</span>
                  </div>
                  <ChargeUsageTable charges={projectedUsage.charges} currency={projectedUsage.currency} />
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No projected usage data available.</p>
              )}
            </CardContent>
          </Card>

          {/* Past Usage */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Past Usage</CardTitle>
            </CardHeader>
            <CardContent>
              {pastLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : pastUsage?.length ? (
                <div className="space-y-4">
                  {/* Bar Chart */}
                  <ChartContainer config={pastUsageChartConfig} className="h-[200px] w-full">
                    <BarChart data={chartData} accessibilityLayer>
                      <CartesianGrid vertical={false} />
                      <XAxis
                        dataKey="period"
                        tickLine={false}
                        axisLine={false}
                        tickMargin={8}
                      />
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        tickMargin={8}
                        tickFormatter={(v) => `$${v}`}
                      />
                      <ChartTooltip
                        content={
                          <ChartTooltipContent
                            formatter={(value) =>
                              formatCurrency(Number(value) * 100, pastUsage[0]?.currency ?? 'USD')
                            }
                          />
                        }
                      />
                      <Bar dataKey="amount" fill="var(--color-amount)" radius={4} />
                    </BarChart>
                  </ChartContainer>

                  {/* Accordion for period details */}
                  <Accordion type="multiple">
                    {pastUsage.map((period, idx) => (
                      <AccordionItem key={idx} value={`period-${idx}`}>
                        <AccordionTrigger>
                          <div className="flex items-center gap-4">
                            <span>
                              {format(new Date(period.from_datetime), 'MMM d, yyyy')} – {format(new Date(period.to_datetime), 'MMM d, yyyy')}
                            </span>
                            <span className="font-mono text-muted-foreground">
                              {formatCurrency(Number(period.amount_cents), period.currency)}
                            </span>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          <ChargeUsageTable charges={period.charges} currency={period.currency} />
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No past usage data available.</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

function PortalLinkDialog({ externalId }: { externalId: string }) {
  const [open, setOpen] = useState(false)
  const [portalUrl, setPortalUrl] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const mutation = useMutation({
    mutationFn: () => customersApi.getPortalUrl(externalId),
    onSuccess: (data) => {
      setPortalUrl(data.portal_url)
      setCopied(false)
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to generate portal link')
    },
  })

  const handleOpen = () => {
    setOpen(true)
    setPortalUrl(null)
    setCopied(false)
    mutation.mutate()
  }

  const handleCopy = async () => {
    if (!portalUrl) return
    await navigator.clipboard.writeText(portalUrl)
    setCopied(true)
    toast.success('Portal link copied to clipboard')
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <>
      <Button variant="default" size="sm" onClick={handleOpen}>
        <ExternalLink className="mr-2 h-4 w-4" />
        Portal Link
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Customer Portal Link</DialogTitle>
            <DialogDescription>
              Share this link with the customer. Link expires in 12 hours.
            </DialogDescription>
          </DialogHeader>
          {mutation.isPending ? (
            <Skeleton className="h-10 w-full" />
          ) : portalUrl ? (
            <div className="flex items-center gap-2">
              <Input readOnly value={portalUrl} className="font-mono text-xs" />
              <Button variant="outline" size="icon" onClick={handleCopy}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
          ) : mutation.isError ? (
            <p className="text-sm text-destructive">Failed to generate portal link.</p>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  )
}

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [editOpen, setEditOpen] = useState(false)
  const [subscriptionFormOpen, setSubscriptionFormOpen] = useState(false)

  const { data: customer, isLoading, error } = useQuery({
    queryKey: ['customer', id],
    queryFn: () => customersApi.get(id!),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: (data: CustomerUpdate) => customersApi.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer', id] })
      setEditOpen(false)
      toast.success('Customer updated successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update customer'
      toast.error(message)
    },
  })

  const { data: plans } = useQuery({
    queryKey: ['plans'],
    queryFn: () => plansApi.list(),
  })

  const createSubscriptionMutation = useMutation({
    mutationFn: (data: SubscriptionCreate) => subscriptionsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-subscriptions', id] })
      setSubscriptionFormOpen(false)
      toast.success('Subscription created successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create subscription'
      toast.error(message)
    },
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
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <CustomerAvatar name={customer.name} size="lg" />
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-semibold tracking-tight">{customer.name}</h2>
                  <CustomerHealthBadge customerId={customer.id} />
                </div>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {customer.external_id}{customer.email ? ` \u2022 ${customer.email}` : ''}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                <Pencil className="mr-2 h-3.5 w-3.5" />
                Edit
              </Button>
              <PortalLinkDialog externalId={customer.external_id} />
            </div>
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
                <div className="space-y-1">
                  <span className="text-muted-foreground">Billing Metadata</span>
                  {customer.billing_metadata && Object.keys(customer.billing_metadata).length > 0 ? (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {Object.entries(customer.billing_metadata).map(([key, value]) => (
                        <Badge key={key} variant="outline" className="font-normal text-xs">
                          <span className="font-medium">{key}:</span>
                          <span className="ml-1 text-muted-foreground">{String(value)}</span>
                        </Badge>
                      ))}
                    </div>
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
          <Tabs defaultValue="overview">
            <TabsList>
              <TabsTrigger value="overview">
                <ScrollText className="mr-2 h-4 w-4" />
                Overview
              </TabsTrigger>
              <TabsTrigger value="billing">
                <FileText className="mr-2 h-4 w-4" />
                Billing
              </TabsTrigger>
              <TabsTrigger value="payments">
                <CreditCard className="mr-2 h-4 w-4" />
                Payments
              </TabsTrigger>
              <TabsTrigger value="coupons">
                <Tag className="mr-2 h-4 w-4" />
                Coupons
              </TabsTrigger>
              <TabsTrigger value="activity">
                <History className="mr-2 h-4 w-4" />
                Activity
              </TabsTrigger>
            </TabsList>

            {/* Overview: Subscriptions + Usage */}
            <TabsContent value="overview">
              <div className="space-y-6">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium">Subscriptions</h3>
                    <Button variant="outline" size="sm" onClick={() => setSubscriptionFormOpen(true)}>
                      <Plus className="mr-2 h-4 w-4" />
                      Create Subscription
                    </Button>
                  </div>
                  <CustomerSubscriptionsTab customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Usage</h3>
                  <CustomerUsageTab customerId={customer.id} externalId={customer.external_id} />
                </div>
              </div>
            </TabsContent>

            {/* Billing: Invoices + Fees + Credit Notes */}
            <TabsContent value="billing">
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-medium mb-3">Invoices</h3>
                  <CustomerInvoicesTab customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Fees</h3>
                  <CustomerFeesTab customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Credit Notes</h3>
                  <CustomerCreditNotesTab customerId={customer.id} />
                </div>
              </div>
            </TabsContent>

            {/* Payments: Payment Methods + Payments + Wallets */}
            <TabsContent value="payments">
              <div className="space-y-6">
                <CustomerPaymentMethodsCard customerId={customer.id} customerName={customer.name} />
                <div>
                  <h3 className="text-sm font-medium mb-3">Payment History</h3>
                  <CustomerPaymentsTab customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Wallets</h3>
                  <CustomerWalletsTab customerId={customer.id} />
                </div>
              </div>
            </TabsContent>

            {/* Coupons */}
            <TabsContent value="coupons">
              <CustomerCouponsTab customerId={customer.id} />
            </TabsContent>

            {/* Activity: Audit Trail */}
            <TabsContent value="activity">
              <CustomerActivityTab customerId={customer.id} />
            </TabsContent>
          </Tabs>

          {/* Edit Customer Dialog */}
          <CustomerFormDialog
            open={editOpen}
            onOpenChange={setEditOpen}
            customer={customer}
            onSubmit={(data) => updateMutation.mutate(data as CustomerUpdate)}
            isLoading={updateMutation.isPending}
          />

          {/* Create Subscription Dialog */}
          <SubscriptionFormDialog
            open={subscriptionFormOpen}
            onOpenChange={setSubscriptionFormOpen}
            customers={customer ? [customer] : []}
            plans={plans ?? []}
            onSubmit={(data) => createSubscriptionMutation.mutate(data)}
            isLoading={createSubscriptionMutation.isPending}
            defaultCustomerId={customer?.id}
          />
        </>
      ) : null}
    </div>
  )
}
