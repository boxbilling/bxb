import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Bar, BarChart, XAxis, YAxis, CartesianGrid } from 'recharts'

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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { ChargeUsageTable } from './ChargeUsageTable'
import { subscriptionsApi, customersApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'

const pastUsageChartConfig = {
  amount: {
    label: 'Amount',
    color: 'var(--primary)',
  },
} satisfies ChartConfig

export function CustomerUsageSection({ customerId, externalId }: { customerId: string; externalId: string }) {
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string>('')

  const { data: subscriptions, isLoading: subsLoading } = useQuery({
    queryKey: ['customer-subscriptions', customerId],
    queryFn: () => subscriptionsApi.list({ customer_id: customerId }),
  })

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
