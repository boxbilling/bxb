import { AuditTrailTimeline } from '@/components/AuditTrailTimeline'

export function CustomerActivityTab({ customerId }: { customerId: string }) {
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
