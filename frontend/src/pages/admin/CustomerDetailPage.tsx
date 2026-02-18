import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { FileText, CreditCard, Tag, ScrollText, Plus, Pencil, History } from 'lucide-react'
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
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { CustomerFormDialog } from '@/components/CustomerFormDialog'
import { CustomerAvatar } from '@/components/CustomerAvatar'
import { CustomerHealthBadge } from '@/components/CustomerHealthBadge'
import { AuditTrailTimeline } from '@/components/AuditTrailTimeline'
import { CustomerPaymentMethodsCard } from '@/components/customer-detail/CustomerPaymentMethodsCard'
import { PortalLinkDialog } from '@/components/customer-detail/PortalLinkDialog'
import { CustomerSubscriptionsTable } from '@/components/customer-detail/CustomerSubscriptionsTable'
import { CustomerInvoicesTable } from '@/components/customer-detail/CustomerInvoicesTable'
import { CustomerPaymentsTable } from '@/components/customer-detail/CustomerPaymentsTable'
import { CustomerWalletsTable } from '@/components/customer-detail/CustomerWalletsTable'
import { CustomerCouponsTable } from '@/components/customer-detail/CustomerCouponsTable'
import { CustomerCreditNotesTable } from '@/components/customer-detail/CustomerCreditNotesTable'
import { CustomerFeesTable } from '@/components/customer-detail/CustomerFeesTable'
import { customersApi, subscriptionsApi, invoicesApi, plansApi, ApiError } from '@/lib/api'
import { SubscriptionFormDialog } from '@/components/SubscriptionFormDialog'
import type { CustomerCurrentUsageResponse, CustomerUpdate, SubscriptionCreate } from '@/types/billing'
import { formatCents } from '@/lib/utils'

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
    <div className="grid grid-cols-2 gap-3 md:gap-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Outstanding Balance</CardTitle>
          <FileText className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-orange-600">{formatCents(outstanding, currency)}</div>
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
            {formatCents(overdue, currency)}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {(invoices ?? []).filter((i) => i.status === 'finalized' && i.due_date && new Date(i.due_date) < new Date()).length} overdue invoice(s)
          </p>
        </CardContent>
      </Card>
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
              <TableCell className="text-right font-mono">{formatCents(Number(charge.amount_cents), currency)}</TableCell>
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
    color: 'var(--primary)',
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
                    <span className="text-lg font-semibold">{formatCents(Number(currentUsage.amount_cents), currentUsage.currency)}</span>
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
                    <span className="text-lg font-semibold">{formatCents(Number(projectedUsage.amount_cents), projectedUsage.currency)}</span>
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
                              formatCents(Number(value) * 100, pastUsage[0]?.currency ?? 'USD')
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
                              {formatCents(Number(period.amount_cents), period.currency)}
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
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
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
              <Button variant="outline" size="sm" className="w-full md:w-auto" onClick={() => setEditOpen(true)}>
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
            <div className="overflow-x-auto">
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
            </div>

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
                  <CustomerSubscriptionsTable customerId={customer.id} />
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
                  <CustomerInvoicesTable customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Fees</h3>
                  <CustomerFeesTable customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Credit Notes</h3>
                  <CustomerCreditNotesTable customerId={customer.id} />
                </div>
              </div>
            </TabsContent>

            {/* Payments: Payment Methods + Payments + Wallets */}
            <TabsContent value="payments">
              <div className="space-y-6">
                <CustomerPaymentMethodsCard customerId={customer.id} customerName={customer.name} />
                <div>
                  <h3 className="text-sm font-medium mb-3">Payment History</h3>
                  <CustomerPaymentsTable customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Wallets</h3>
                  <CustomerWalletsTable customerId={customer.id} />
                </div>
              </div>
            </TabsContent>

            {/* Coupons */}
            <TabsContent value="coupons">
              <CustomerCouponsTable customerId={customer.id} />
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
