import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import {
  Calendar,
  CreditCard,
  FileText,
  Loader2,
  Play,
  Square,
  XCircle,
  Clock,
  ArrowRightLeft,
  CheckCircle2,
  AlertCircle,
  Pause,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { subscriptionsApi } from '@/lib/api'
import type { LifecycleEvent } from '@/types/billing'

const EVENT_CONFIG: Record<string, {
  icon: typeof Calendar
  dotColor: string
}> = {
  subscription: { icon: Play, dotColor: 'bg-green-500' },
  status_change: { icon: ArrowRightLeft, dotColor: 'bg-orange-500' },
  invoice: { icon: FileText, dotColor: 'bg-blue-500' },
  payment: { icon: CreditCard, dotColor: 'bg-purple-500' },
}

const STATUS_BADGE: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; className?: string }> = {
  created: { variant: 'outline', className: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' },
  active: { variant: 'outline', className: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' },
  pending: { variant: 'outline', className: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300' },
  changed: { variant: 'outline', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' },
  draft: { variant: 'secondary' },
  finalized: { variant: 'outline', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' },
  paid: { variant: 'outline', className: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' },
  voided: { variant: 'outline', className: 'bg-gray-100 text-gray-700 dark:bg-gray-900 dark:text-gray-300' },
  succeeded: { variant: 'outline', className: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' },
  failed: { variant: 'destructive' },
  refunded: { variant: 'outline', className: 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300' },
  paused: { variant: 'outline', className: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300' },
  canceled: { variant: 'outline', className: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' },
  terminated: { variant: 'destructive' },
}

function getEventIcon(event: LifecycleEvent) {
  const config = EVENT_CONFIG[event.event_type]
  if (!config) return Clock

  // Use more specific icons for certain statuses
  if (event.status === 'terminated') return Square
  if (event.status === 'canceled') return XCircle
  if (event.status === 'paused') return Pause
  if (event.status === 'succeeded' || event.status === 'paid') return CheckCircle2
  if (event.status === 'failed') return AlertCircle

  return config.icon
}

function getDotColor(event: LifecycleEvent): string {
  if (event.status === 'terminated' || event.status === 'failed') return 'bg-red-500'
  if (event.status === 'canceled') return 'bg-orange-500'
  if (event.status === 'paused') return 'bg-yellow-500'
  if (event.status === 'succeeded' || event.status === 'paid' || event.status === 'active') return 'bg-green-500'
  return EVENT_CONFIG[event.event_type]?.dotColor ?? 'bg-gray-400'
}

function getResourceLink(event: LifecycleEvent): string | null {
  if (!event.resource_id || !event.resource_type) return null
  if (event.resource_type === 'invoice') return `/admin/invoices`
  return null
}

function TimelineEventCard({ event }: { event: LifecycleEvent }) {
  const Icon = getEventIcon(event)
  const dotColor = getDotColor(event)
  const badgeConfig = STATUS_BADGE[event.status ?? '']
  const link = getResourceLink(event)

  return (
    <div className="relative pl-8 pb-6 last:pb-0 group">
      {/* Dot */}
      <div className={`absolute left-0 top-1 h-3 w-3 rounded-full ${dotColor} ring-2 ring-background`} />
      {/* Connecting line */}
      <div className="absolute left-[5px] top-4 bottom-0 w-0.5 bg-border group-last:hidden" />

      <div className="space-y-1">
        {/* Header row: timestamp + icon + title + status badge */}
        <div className="flex items-center gap-2 flex-wrap">
          <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className="text-sm font-medium">
            {link ? (
              <Link to={link} className="hover:underline text-primary">
                {event.title}
              </Link>
            ) : (
              event.title
            )}
          </span>
          {event.status && badgeConfig && (
            <Badge variant={badgeConfig.variant} className={`text-xs ${badgeConfig.className ?? ''}`}>
              {event.status}
            </Badge>
          )}
        </div>

        {/* Description */}
        {event.description && (
          <p className="text-xs text-muted-foreground pl-5">{event.description}</p>
        )}

        {/* Timestamp */}
        <p className="text-xs text-muted-foreground pl-5">
          {format(new Date(event.timestamp), 'MMM d, yyyy HH:mm:ss')}
        </p>
      </div>
    </div>
  )
}

export function SubscriptionLifecycleTimeline({
  subscriptionId,
}: {
  subscriptionId: string
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['subscription-lifecycle', subscriptionId],
    queryFn: () => subscriptionsApi.getLifecycle(subscriptionId),
    enabled: !!subscriptionId,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">Loading lifecycle timeline...</span>
      </div>
    )
  }

  if (!data?.events?.length) {
    return (
      <p className="text-sm text-muted-foreground py-2">No lifecycle events found</p>
    )
  }

  return (
    <div className="border-l-2 border-border ml-1">
      {data.events.map((event, idx) => (
        <TimelineEventCard key={`${event.event_type}-${event.timestamp}-${idx}`} event={event} />
      ))}
    </div>
  )
}
