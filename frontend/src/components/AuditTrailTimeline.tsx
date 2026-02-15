import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { ArrowRight, ExternalLink, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { auditLogsApi } from '@/lib/api'
import type { AuditLog } from '@/types/billing'

function ActionBadge({ action }: { action: string }) {
  const styles: Record<string, string> = {
    created: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
    updated: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
    status_changed: 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300',
    deleted: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  }

  return (
    <Badge variant="outline" className={`text-xs ${styles[action] ?? ''}`}>
      {action.replace(/_/g, ' ')}
    </Badge>
  )
}

function ChangesSummary({ changes }: { changes: Record<string, unknown> }) {
  const entries = Object.entries(changes)
  if (entries.length === 0) return null

  return (
    <div className="mt-1 space-y-0.5">
      {entries.map(([key, value]) => {
        const change = value as { old?: unknown; new?: unknown } | undefined
        return (
          <div key={key} className="flex items-center gap-1 text-xs font-mono">
            <span className="text-muted-foreground">{key}:</span>
            <span className="text-red-600 dark:text-red-400 line-through">
              {change?.old !== undefined ? String(change.old) : 'null'}
            </span>
            <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="text-green-600 dark:text-green-400">
              {change?.new !== undefined ? String(change.new) : 'null'}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function TimelineEntry({ log }: { log: AuditLog }) {
  return (
    <div className="relative pl-6 pb-4 last:pb-0">
      {/* Dot */}
      <div className="absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full border-2 border-primary bg-background" />
      {/* Connecting line */}
      <div className="absolute left-[4.5px] top-4 bottom-0 w-px bg-border last:hidden" />

      <div className="space-y-0.5">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {format(new Date(log.created_at), 'MMM d, yyyy HH:mm:ss')}
          </span>
          <ActionBadge action={log.action} />
        </div>
        <div className="text-xs text-muted-foreground">
          <span className="capitalize">{log.actor_type.replace(/_/g, ' ')}</span>
          {log.actor_id && (
            <span className="font-mono ml-1">({log.actor_id.substring(0, 8)})</span>
          )}
        </div>
        <ChangesSummary changes={log.changes} />
      </div>
    </div>
  )
}

export function AuditTrailTimeline({
  resourceType,
  resourceId,
  limit = 20,
  showViewAll = false,
}: {
  resourceType: string
  resourceId: string
  limit?: number
  showViewAll?: boolean
}) {
  const { data: auditLogs, isLoading } = useQuery({
    queryKey: ['audit-trail', resourceType, resourceId],
    queryFn: () => auditLogsApi.getForResource(resourceType, resourceId),
    enabled: !!resourceId,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">Loading audit trail...</span>
      </div>
    )
  }

  if (!auditLogs || auditLogs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-2">No audit trail entries found</p>
    )
  }

  const displayLogs = auditLogs.slice(0, limit)

  return (
    <div>
      <div className="border-l-2 border-border ml-1">
        {displayLogs.map((log) => (
          <TimelineEntry key={log.id} log={log} />
        ))}
      </div>
      {showViewAll && auditLogs.length > limit && (
        <div className="mt-2">
          <Link
            to={`/admin/audit-logs?resource_type=${resourceType}&resource_id=${resourceId}`}
            className="text-sm text-primary hover:underline inline-flex items-center gap-1"
          >
            View all in Audit Logs
            <ExternalLink className="h-3 w-3" />
          </Link>
        </div>
      )}
    </div>
  )
}
