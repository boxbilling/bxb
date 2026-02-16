import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, TrendingUp, Shield, Activity } from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { portalApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'
import { usePortalToken } from '@/layouts/PortalLayout'

export default function PortalUsagePage() {
  const token = usePortalToken()
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string>('')

  const { data: subscriptions = [], isLoading: subscriptionsLoading } = useQuery({
    queryKey: ['portal-subscriptions', token],
    queryFn: () => portalApi.listSubscriptions(token),
    enabled: !!token,
  })

  // Auto-select subscription if customer has only one
  const activeSubscriptions = subscriptions.filter(
    (s) => s.status === 'active' || s.status === 'pending'
  )

  useEffect(() => {
    if (activeSubscriptions.length === 1 && !selectedSubscriptionId) {
      setSelectedSubscriptionId(activeSubscriptions[0].id)
    }
  }, [activeSubscriptions, selectedSubscriptionId])

  const { data: usage, isLoading: usageLoading } = useQuery({
    queryKey: ['portal-usage', token, selectedSubscriptionId],
    queryFn: () => portalApi.getCurrentUsage(token, selectedSubscriptionId),
    enabled: !!token && !!selectedSubscriptionId,
  })

  const { data: usageTrend } = useQuery({
    queryKey: ['portal-usage-trend', token, selectedSubscriptionId],
    queryFn: () => portalApi.getUsageTrend(token, selectedSubscriptionId),
    enabled: !!token && !!selectedSubscriptionId,
  })

  const { data: usageLimits } = useQuery({
    queryKey: ['portal-usage-limits', token, selectedSubscriptionId],
    queryFn: () => portalApi.getUsageLimits(token, selectedSubscriptionId),
    enabled: !!token && !!selectedSubscriptionId,
  })

  const { data: projectedUsage } = useQuery({
    queryKey: ['portal-projected-usage', token, selectedSubscriptionId],
    queryFn: () => portalApi.getProjectedUsage(token, selectedSubscriptionId),
    enabled: !!token && !!selectedSubscriptionId,
  })

  const selectedSub = subscriptions.find((s) => s.id === selectedSubscriptionId)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Usage</h1>
        <p className="text-muted-foreground">
          View your current billing period usage
        </p>
      </div>

      {/* Subscription Selector */}
      {activeSubscriptions.length !== 1 && (
        <div className="max-w-sm">
          <Select
            value={selectedSubscriptionId}
            onValueChange={setSelectedSubscriptionId}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select a subscription" />
            </SelectTrigger>
            <SelectContent>
              {subscriptionsLoading ? (
                <SelectItem value="loading" disabled>
                  Loading...
                </SelectItem>
              ) : activeSubscriptions.length === 0 ? (
                <SelectItem value="none" disabled>
                  No active subscriptions
                </SelectItem>
              ) : (
                activeSubscriptions.map((sub) => (
                  <SelectItem key={sub.id} value={sub.id}>
                    {sub.plan.name} ({sub.external_id})
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Show selected subscription info when auto-selected */}
      {activeSubscriptions.length === 1 && selectedSub && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Subscription:</span>
          <Badge variant="outline">{selectedSub.plan.name}</Badge>
          <span className="text-xs">({selectedSub.external_id})</span>
        </div>
      )}

      {!selectedSubscriptionId ? (
        <Card>
          <CardContent className="py-12 text-center">
            <BarChart3 className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              Select a subscription to view usage
            </p>
          </CardContent>
        </Card>
      ) : usageLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-24 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <>
          {/* Projected Usage Card */}
          {projectedUsage && (
            <Card className="border-primary/20 bg-primary/5">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <TrendingUp className="h-5 w-5 text-primary" />
                  Projected End-of-Period Usage
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  Based on {projectedUsage.days_elapsed} days of usage ({projectedUsage.days_remaining} days remaining)
                </p>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Current Total</p>
                    <p className="text-lg font-semibold">
                      {formatCents(Number(projectedUsage.current_total_cents), projectedUsage.currency)}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Projected Total</p>
                    <p className="text-lg font-bold text-primary">
                      {formatCents(Number(projectedUsage.projected_total_cents), projectedUsage.currency)}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Period Progress</p>
                    <div className="mt-1">
                      <Progress
                        value={Math.round((projectedUsage.days_elapsed / projectedUsage.total_days) * 100)}
                        className="h-2"
                      />
                      <p className="text-xs text-muted-foreground mt-1">
                        {Math.round((projectedUsage.days_elapsed / projectedUsage.total_days) * 100)}% complete
                      </p>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Period</p>
                    <p className="text-sm">
                      {new Date(projectedUsage.period_start).toLocaleDateString()} &ndash;{' '}
                      {new Date(projectedUsage.period_end).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                {projectedUsage.charges.length > 0 && (
                  <div className="mt-4 rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Metric</TableHead>
                          <TableHead className="text-right">Current Units</TableHead>
                          <TableHead className="text-right">Projected Units</TableHead>
                          <TableHead className="text-right">Projected Amount</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {projectedUsage.charges.map((charge, index) => (
                          <TableRow key={index}>
                            <TableCell className="font-medium">
                              {charge.metric_name}
                              <Badge variant="outline" className="ml-2 text-xs">
                                {charge.charge_model}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">{Number(charge.current_units).toFixed(1)}</TableCell>
                            <TableCell className="text-right font-medium">{Number(charge.projected_units).toFixed(1)}</TableCell>
                            <TableCell className="text-right">
                              {formatCents(Number(charge.projected_amount_cents), projectedUsage.currency)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Usage Limits / Progress Bars */}
          {usageLimits && usageLimits.items.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Shield className="h-5 w-5" />
                  Plan Limits
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {usageLimits.items.map((item) => (
                    <div key={item.feature_code}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{item.feature_name}</span>
                          <Badge variant="outline" className="text-xs">
                            {item.feature_type}
                          </Badge>
                        </div>
                        {item.feature_type === 'quantity' && item.limit_value != null ? (
                          <span className="text-sm text-muted-foreground">
                            {Number(item.current_usage).toFixed(0)} / {Number(item.limit_value).toFixed(0)}
                          </span>
                        ) : item.feature_type === 'boolean' ? (
                          <Badge variant={Number(item.current_usage) > 0 ? 'default' : 'secondary'}>
                            {Number(item.current_usage) > 0 ? 'Enabled' : 'Disabled'}
                          </Badge>
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            {Number(item.current_usage).toFixed(0)}
                          </span>
                        )}
                      </div>
                      {item.feature_type === 'quantity' && item.limit_value != null && (
                        <Progress
                          value={item.usage_percentage ?? 0}
                          className={`h-2 ${
                            (item.usage_percentage ?? 0) >= 90
                              ? '[&>div]:bg-red-500'
                              : (item.usage_percentage ?? 0) >= 70
                                ? '[&>div]:bg-yellow-500'
                                : ''
                          }`}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Usage Trend Chart */}
          {usageTrend && usageTrend.data_points.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Activity className="h-5 w-5" />
                  Usage Trend
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[200px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={usageTrend.data_points.map((p) => ({
                        date: new Date(p.date).toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                        }),
                        value: Number(p.value),
                        events: p.events_count,
                      }))}
                    >
                      <defs>
                        <linearGradient id="portalUsageGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 12 }}
                        className="text-muted-foreground"
                      />
                      <YAxis
                        tick={{ fontSize: 12 }}
                        className="text-muted-foreground"
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'hsl(var(--background))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '6px',
                        }}
                        formatter={(value: number, name: string) => {
                          if (name === 'value') return [value.toFixed(2), 'Usage']
                          return [value, 'Events']
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="value"
                        stroke="hsl(var(--primary))"
                        fill="url(#portalUsageGradient)"
                        strokeWidth={2}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Current Usage Table */}
          {usage && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="h-5 w-5" />
                  Current Usage
                </CardTitle>
                <p className="text-sm text-muted-foreground">
                  {new Date(usage.from_datetime).toLocaleDateString()} &ndash;{' '}
                  {new Date(usage.to_datetime).toLocaleDateString()}
                </p>
              </CardHeader>
              <CardContent>
                {usage.charges.length > 0 ? (
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Metric</TableHead>
                          <TableHead>Units</TableHead>
                          <TableHead>Amount</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {usage.charges.map((charge, index) => (
                          <TableRow key={index}>
                            <TableCell className="font-medium">
                              {charge.billable_metric.name}
                              <Badge variant="outline" className="ml-2 text-xs">
                                {charge.billable_metric.code}
                              </Badge>
                            </TableCell>
                            <TableCell>{charge.units}</TableCell>
                            <TableCell>
                              {formatCents(
                                Number(charge.amount_cents),
                                usage.currency
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No usage data for this period
                  </p>
                )}

                <div className="mt-4 flex justify-end">
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">Total</p>
                    <p className="text-lg font-bold">
                      {formatCents(Number(usage.amount_cents), usage.currency)}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
