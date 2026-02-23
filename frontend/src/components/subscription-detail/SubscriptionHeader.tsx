import { AlertTriangle } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'

import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { plansApi } from '@/lib/api'
import type { Subscription, Customer, Plan } from '@/lib/api'

interface SubscriptionHeaderProps {
  subscription?: Subscription
  customer?: Customer
  plan?: Plan
  isLoading?: boolean
}

const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  active: 'default',
  pending: 'secondary',
  paused: 'outline',
  canceled: 'secondary',
  terminated: 'destructive',
}

export function SubscriptionHeader({
  subscription,
  customer,
  plan,
  isLoading,
}: SubscriptionHeaderProps) {
  const { data: previousPlan } = useQuery({
    queryKey: ['plan', subscription?.previous_plan_id],
    queryFn: () => plansApi.get(subscription!.previous_plan_id!),
    enabled: !!subscription?.previous_plan_id && !!subscription?.downgraded_at,
  })

  if (isLoading || !subscription) {
    return (
      <div>
        <Skeleton className="h-7 w-64 mb-1" />
        <Skeleton className="h-4 w-48" />
      </div>
    )
  }

  const customerName = customer?.name ?? 'Loading...'
  const planName = plan?.name ?? 'Loading...'

  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-semibold tracking-tight">
            {customerName} &mdash; {planName}
          </h2>
          <Badge variant={statusVariant[subscription.status] ?? 'outline'}>
            {subscription.status}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground mt-0.5">
          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{subscription.external_id}</code>
        </p>
        {subscription.downgraded_at && (
          <div className="flex items-center gap-1.5 mt-2">
            <Badge variant="outline" className="text-yellow-600 border-yellow-400 bg-yellow-50">
              <AlertTriangle className="mr-1 h-3 w-3" />
              Pending downgrade{previousPlan ? ` from ${previousPlan.name}` : ''}
            </Badge>
          </div>
        )}
      </div>
    </div>
  )
}
