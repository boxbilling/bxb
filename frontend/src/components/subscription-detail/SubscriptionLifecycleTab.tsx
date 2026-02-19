import { GitBranch } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SubscriptionLifecycleTimeline } from '@/components/SubscriptionLifecycleTimeline'

interface SubscriptionLifecycleTabProps {
  subscriptionId: string
}

export function SubscriptionLifecycleTab({
  subscriptionId,
}: SubscriptionLifecycleTabProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <GitBranch className="h-4 w-4" />
          Lifecycle Timeline
        </CardTitle>
      </CardHeader>
      <CardContent>
        <SubscriptionLifecycleTimeline subscriptionId={subscriptionId} />
      </CardContent>
    </Card>
  )
}
