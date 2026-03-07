import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { SubscriptionUsageCards } from '@/components/shared/SubscriptionUsageCards'
import { subscriptionsApi } from '@/lib/api'

export function CustomerUsageSection({ customerId, externalId }: { customerId: string; externalId: string }) {
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string>('')

  const { data: subscriptions, isLoading: subsLoading } = useQuery({
    queryKey: ['customer-subscriptions', customerId],
    queryFn: () => subscriptionsApi.list({ customer_id: customerId }),
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
        <SubscriptionUsageCards customerExternalId={externalId} subscriptionExternalId={selectedSubscriptionId} />
      )}
    </div>
  )
}
