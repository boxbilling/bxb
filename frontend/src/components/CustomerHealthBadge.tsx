import { useQuery } from '@tanstack/react-query'
import { Circle } from 'lucide-react'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { customersApi } from '@/lib/api'
import type { CustomerHealthResponse } from '@/types/billing'

const healthConfig: Record<
  string,
  { color: string; label: string }
> = {
  good: {
    color: 'text-emerald-500 dark:text-emerald-400',
    label: 'Good',
  },
  warning: {
    color: 'text-yellow-500 dark:text-yellow-400',
    label: 'Warning',
  },
  critical: {
    color: 'text-red-500 dark:text-red-400',
    label: 'Critical',
  },
}

export function CustomerHealthBadge({ customerId }: { customerId: string }) {
  const { data: health } = useQuery({
    queryKey: ['customer-health', customerId],
    queryFn: () => customersApi.getHealth(customerId),
  })

  if (!health) return null

  const config = healthConfig[health.status] ?? healthConfig.good

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex items-center cursor-default">
          <Circle className={`h-3 w-3 fill-current ${config.color}`} />
        </span>
      </TooltipTrigger>
      <TooltipContent side="top">
        <div className="space-y-1">
          <div className="font-medium">Health: {config.label}</div>
          {health.overdue_invoices > 0 && (
            <div>{health.overdue_invoices} overdue invoice(s)</div>
          )}
          {health.failed_payments > 0 && (
            <div>{health.failed_payments} failed payment(s)</div>
          )}
          {health.total_invoices > 0 && health.overdue_invoices === 0 && health.failed_payments === 0 && (
            <div>{health.paid_invoices}/{health.total_invoices} invoices paid</div>
          )}
          {health.total_invoices === 0 && health.total_payments === 0 && (
            <div>No billing history yet</div>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  )
}
