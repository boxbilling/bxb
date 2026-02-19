import { ScrollText } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AuditTrailTimeline } from '@/components/AuditTrailTimeline'

interface SubscriptionActivityTabProps {
  subscriptionId: string
}

export function SubscriptionActivityTab({
  subscriptionId,
}: SubscriptionActivityTabProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <ScrollText className="h-4 w-4" />
          Activity Log
        </CardTitle>
      </CardHeader>
      <CardContent>
        <AuditTrailTimeline
          resourceType="subscription"
          resourceId={subscriptionId}
          limit={20}
          showViewAll
        />
      </CardContent>
    </Card>
  )
}
