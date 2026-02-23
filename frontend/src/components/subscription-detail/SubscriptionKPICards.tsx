import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Calendar, Clock, DollarSign, FileText } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { invoicesApi, subscriptionsApi, usageThresholdsApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'
import type { Subscription, Plan } from '@/lib/api'

interface SubscriptionKPICardsProps {
  subscriptionId: string
  subscription?: Subscription
  plan?: Plan
  isLoading?: boolean
}

export function SubscriptionKPICards({
  subscriptionId,
  subscription,
  plan,
  isLoading,
}: SubscriptionKPICardsProps) {
  const isTerminalStatus =
    subscription?.status === 'terminated' || subscription?.status === 'canceled'

  const { data: nextBillingDate, isLoading: nextBillingLoading } = useQuery({
    queryKey: ['next-billing-date', subscriptionId],
    queryFn: () => subscriptionsApi.getNextBillingDate(subscriptionId),
    enabled: !!subscription && !isTerminalStatus,
  })

  const { data: usage, isLoading: usageLoading } = useQuery({
    queryKey: ['current-usage', subscriptionId],
    queryFn: () => usageThresholdsApi.getCurrentUsage(subscriptionId),
    enabled: !!subscriptionId,
  })

  const { data: invoices, isLoading: invoicesLoading } = useQuery({
    queryKey: ['subscription-invoices', subscriptionId],
    queryFn: () => invoicesApi.list({ subscription_id: subscriptionId }),
    enabled: !!subscriptionId,
  })

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-4" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-7 w-20 mb-1" />
              <Skeleton className="h-3 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
      {/* Next Billing */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Next Billing</CardTitle>
          <Clock className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          {nextBillingLoading ? (
            <>
              <Skeleton className="h-7 w-20 mb-1" />
              <Skeleton className="h-3 w-32" />
            </>
          ) : isTerminalStatus || !nextBillingDate ? (
            <>
              <div className="text-2xl font-bold text-muted-foreground">&mdash;</div>
              <p className="text-xs text-muted-foreground mt-1">
                {isTerminalStatus ? `Subscription ${subscription?.status}` : 'Not available'}
              </p>
            </>
          ) : (
            <>
              <div className="text-2xl font-bold">
                {nextBillingDate.days_until_next_billing}
                <span className="text-sm font-normal text-muted-foreground ml-1">days</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {format(new Date(nextBillingDate.next_billing_date), 'MMM d, yyyy')}
              </p>
            </>
          )}
        </CardContent>
      </Card>

      {/* Current Usage */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Current Usage</CardTitle>
          <Calendar className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          {usageLoading ? (
            <>
              <Skeleton className="h-7 w-20 mb-1" />
              <Skeleton className="h-3 w-32" />
            </>
          ) : !usage ? (
            <>
              <div className="text-2xl font-bold text-muted-foreground">&mdash;</div>
              <p className="text-xs text-muted-foreground mt-1">No usage data</p>
            </>
          ) : (
            <>
              <div className="text-2xl font-bold">
                {formatCents(parseInt(usage.current_usage_amount_cents))}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {format(new Date(usage.billing_period_start), 'MMM d')} &ndash;{' '}
                {format(new Date(usage.billing_period_end), 'MMM d, yyyy')}
              </p>
            </>
          )}
        </CardContent>
      </Card>

      {/* Invoices */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Invoices</CardTitle>
          <FileText className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          {invoicesLoading ? (
            <>
              <Skeleton className="h-7 w-20 mb-1" />
              <Skeleton className="h-3 w-32" />
            </>
          ) : (
            <>
              <div className="text-2xl font-bold">{invoices?.length ?? 0}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Total invoices
              </p>
            </>
          )}
        </CardContent>
      </Card>

      {/* MRR / Plan Price */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Plan Price</CardTitle>
          <DollarSign className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          {!plan ? (
            <>
              <Skeleton className="h-7 w-20 mb-1" />
              <Skeleton className="h-3 w-32" />
            </>
          ) : (
            <>
              <div className="text-2xl font-bold">
                {formatCents(plan.amount_cents, plan.currency)}
              </div>
              <p className="text-xs text-muted-foreground mt-1 capitalize">
                {plan.interval}
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
