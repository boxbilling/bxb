import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Link } from 'react-router-dom'
import { TrendingUp, Activity, BarChart3, Calendar, Package, AlertTriangle, ExternalLink, Layers } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { usageThresholdsApi, customersApi, subscriptionsApi, plansApi, billableMetricsApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'
import type { BillableMetric } from '@/types/billing'

function intervalLabel(interval: string) {
  return (
    {
      weekly: 'week',
      monthly: 'month',
      quarterly: 'quarter',
      yearly: 'year',
    }[interval] ?? interval
  )
}

interface SubscriptionOverviewTabProps {
  subscriptionId: string
  customerExternalId?: string
  subscriptionExternalId?: string
  customerId?: string
  planId?: string
  previousPlanId?: string | null
  downgradedAt?: string | null
}

export function SubscriptionOverviewTab({
  subscriptionId,
  customerExternalId,
  subscriptionExternalId,
  customerId,
  planId,
  previousPlanId,
  downgradedAt,
}: SubscriptionOverviewTabProps) {
  const { data: plan, isLoading: planLoading } = useQuery({
    queryKey: ['plan', planId],
    queryFn: () => plansApi.get(planId!),
    enabled: !!planId,
  })

  const { data: previousPlan } = useQuery({
    queryKey: ['plan', previousPlanId],
    queryFn: () => plansApi.get(previousPlanId!),
    enabled: !!previousPlanId && !!downgradedAt,
  })

  const { data: metrics } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: () => billableMetricsApi.list(),
    enabled: !!plan?.charges?.length,
  })

  const metricMap = new Map(metrics?.map((m: BillableMetric) => [m.id, m]) ?? [])

  const { data: usage, isLoading: usageLoading, isError: usageError } = useQuery({
    queryKey: ['current-usage', subscriptionId],
    queryFn: () => usageThresholdsApi.getCurrentUsage(subscriptionId),
    enabled: !!subscriptionId,
  })

  const { data: customerUsage, isLoading: customerUsageLoading } = useQuery({
    queryKey: ['customer-usage', customerExternalId, subscriptionExternalId],
    queryFn: () => customersApi.getCurrentUsage(customerExternalId!, subscriptionExternalId!),
    enabled: !!customerExternalId && !!subscriptionExternalId,
  })

  const { data: usageTrend, isLoading: usageTrendLoading } = useQuery({
    queryKey: ['usage-trend', subscriptionId],
    queryFn: () => subscriptionsApi.getUsageTrend(subscriptionId),
    enabled: !!subscriptionId,
  })

  return (
    <div className="space-y-6">
      {/* Plan Summary */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Package className="h-4 w-4" />
              Plan Details
            </CardTitle>
            {plan && (
              <Link
                to={`/admin/plans/${plan.id}`}
                className="text-sm text-primary hover:underline flex items-center gap-1"
              >
                View Plan
                <ExternalLink className="h-3 w-3" />
              </Link>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {planLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-64" />
            </div>
          ) : !plan ? (
            <p className="text-sm text-muted-foreground">No plan data available</p>
          ) : (
            <div className="space-y-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold">{plan.name}</span>
                  <Badge variant="secondary">{plan.code}</Badge>
                </div>
                <p className="text-2xl font-bold font-mono">
                  {formatCents(plan.amount_cents, plan.currency)}
                  <span className="text-sm font-normal text-muted-foreground">/{intervalLabel(plan.interval)}</span>
                </p>
                {plan.description && (
                  <p className="text-sm text-muted-foreground">{plan.description}</p>
                )}
              </div>

              {previousPlanId && downgradedAt && previousPlan && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Pending Downgrade</AlertTitle>
                  <AlertDescription>
                    Downgrading from <span className="font-medium">{previousPlan.name}</span>.
                    Scheduled for {format(new Date(downgradedAt), 'MMM d, yyyy')}.
                  </AlertDescription>
                </Alert>
              )}

              {plan.charges && plan.charges.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                    <Layers className="h-3.5 w-3.5" />
                    Charges ({plan.charges.length})
                  </div>
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Metric</TableHead>
                          <TableHead>Charge Model</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {plan.charges.map((charge) => {
                          const metric = metricMap.get(charge.billable_metric_id)
                          return (
                            <TableRow key={charge.id}>
                              <TableCell>
                                <div>{metric?.name ?? 'Unknown metric'}</div>
                                <div className="text-xs text-muted-foreground">
                                  {metric?.code ?? charge.billable_metric_id.slice(0, 8)}
                                </div>
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline">{charge.charge_model}</Badge>
                              </TableCell>
                            </TableRow>
                          )
                        })}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Current Usage */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Current Usage
          </CardTitle>
        </CardHeader>
        <CardContent>
          {usageLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-4 w-48" />
            </div>
          ) : usageError || !usage ? (
            <p className="text-sm text-muted-foreground">No usage data available</p>
          ) : (
            <div className="space-y-2">
              <p className="text-3xl font-semibold font-mono">
                {formatCents(parseInt(usage.current_usage_amount_cents))}
              </p>
              <p className="text-sm text-muted-foreground flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                Billing Period: {format(new Date(usage.billing_period_start), 'MMM d, yyyy')} &mdash; {format(new Date(usage.billing_period_end), 'MMM d, yyyy')}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Usage Trend Chart */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Usage Trend
          </CardTitle>
        </CardHeader>
        <CardContent>
          {usageTrendLoading ? (
            <div className="h-[200px] flex items-center justify-center">
              <Skeleton className="h-full w-full" />
            </div>
          ) : !usageTrend?.data_points?.length ? (
            <div className="h-[200px] flex items-center justify-center text-muted-foreground">
              <p className="text-sm">No usage trend data available</p>
            </div>
          ) : (
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={usageTrend.data_points}>
                  <defs>
                    <linearGradient id="usageTrendFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(val: string) => {
                      const d = new Date(val + 'T00:00:00')
                      return format(d, 'MMM d')
                    }}
                    tick={{ fontSize: 11 }}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 11 }}
                    width={50}
                    tickFormatter={(val: number) => val.toLocaleString()}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const point = payload[0].payload
                      const d = new Date(point.date + 'T00:00:00')
                      return (
                        <div className="rounded-md border bg-background px-3 py-2 text-sm shadow-sm">
                          <p className="font-medium">{format(d, 'MMM d, yyyy')}</p>
                          <p className="text-muted-foreground">
                            Usage: <span className="font-mono font-medium text-foreground">{Number(point.value).toLocaleString()}</span>
                          </p>
                          <p className="text-muted-foreground">
                            Events: <span className="font-mono font-medium text-foreground">{point.events_count.toLocaleString()}</span>
                          </p>
                        </div>
                      )
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="var(--primary)"
                    strokeWidth={2}
                    fill="url(#usageTrendFill)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Per-Metric Usage Breakdown */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Usage Breakdown
            </CardTitle>
            {customerId && (
              <Link
                to={`/admin/customers/${customerId}?tab=usage`}
                className="text-sm text-primary hover:underline"
              >
                View Full Usage
              </Link>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {customerUsageLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : !customerUsage?.charges?.length ? (
            <p className="text-sm text-muted-foreground">No per-metric usage data available</p>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Metric</TableHead>
                    <TableHead>Units</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead className="hidden md:table-cell">Charge Model</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {customerUsage.charges.map((charge, idx) => (
                    <TableRow key={`${charge.billable_metric.code}-${idx}`}>
                      <TableCell>
                        <div>{charge.billable_metric.name}</div>
                        <div className="text-xs text-muted-foreground">{charge.billable_metric.code}</div>
                      </TableCell>
                      <TableCell className="font-mono">{charge.units}</TableCell>
                      <TableCell className="font-mono">
                        {formatCents(Number(charge.amount_cents), customerUsage.currency)}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <Badge variant="outline">{charge.charge_model}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
