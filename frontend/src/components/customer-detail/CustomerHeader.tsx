import { Pencil } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CustomerAvatar } from '@/components/CustomerAvatar'
import { CustomerHealthBadge } from '@/components/CustomerHealthBadge'
import { PortalLinkDialog } from './PortalLinkDialog'
import type { Customer } from '@/lib/api'

export function CustomerHeader({ customer, onEdit }: { customer: Customer; onEdit: () => void }) {
  return (
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
        <Button variant="outline" size="sm" className="w-full md:w-auto" onClick={onEdit}>
          <Pencil className="mr-2 h-3.5 w-3.5" />
          Edit
        </Button>
        <PortalLinkDialog externalId={customer.external_id} />
      </div>
    </div>
  )
}
