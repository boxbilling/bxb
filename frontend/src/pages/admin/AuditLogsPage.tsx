import { Fragment, useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Search, ScrollText, X, Copy, ChevronRight, ArrowRight } from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
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
    <Badge variant="outline" className={styles[action] ?? ''}>
      {action.replace(/_/g, ' ')}
    </Badge>
  )
}

function ResourceTypeBadge({ resourceType }: { resourceType: string }) {
  return (
    <Badge variant="secondary" className="capitalize">
      {resourceType.replace(/_/g, ' ')}
    </Badge>
  )
}

function CopyableId({ id }: { id: string }) {
  const truncated = id.substring(0, 8) + '...'

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            className="inline-flex items-center gap-1 font-mono text-xs hover:text-primary transition-colors"
            onClick={(e) => {
              e.stopPropagation()
              navigator.clipboard.writeText(id)
              toast.success('Copied to clipboard')
            }}
          >
            {truncated}
            <Copy className="h-3 w-3" />
          </button>
        </TooltipTrigger>
        <TooltipContent>{id}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function ChangesDisplay({ changes }: { changes: Record<string, unknown> }) {
  const entries = Object.entries(changes)
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">No changes recorded</p>
  }

  return (
    <div className="space-y-2">
      {entries.map(([key, value]) => {
        const change = value as { old?: unknown; new?: unknown } | undefined
        return (
          <div key={key} className="flex items-start gap-2 text-sm font-mono">
            <span className="font-medium text-foreground min-w-[120px]">{key}:</span>
            <span className="text-red-600 dark:text-red-400 line-through">
              {change?.old !== undefined ? String(change.old) : 'null'}
            </span>
            <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground mt-0.5" />
            <span className="text-green-600 dark:text-green-400">
              {change?.new !== undefined ? String(change.new) : 'null'}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default function AuditLogsPage() {
  const [searchParams] = useSearchParams()
  const [resourceTypeFilter, setResourceTypeFilter] = useState(searchParams.get('resource_type') || 'all')
  const [actionFilter, setActionFilter] = useState('all')
  const [resourceIdSearch, setResourceIdSearch] = useState(searchParams.get('resource_id') || '')
  const [debouncedResourceId, setDebouncedResourceId] = useState(resourceIdSearch)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedResourceId(resourceIdSearch), 300)
    return () => clearTimeout(timer)
  }, [resourceIdSearch])

  const { data: auditLogs, isLoading } = useQuery({
    queryKey: ['audit-logs', { resourceTypeFilter, actionFilter, debouncedResourceId }],
    queryFn: () =>
      auditLogsApi.list({
        resource_type: resourceTypeFilter !== 'all' ? resourceTypeFilter : undefined,
        action: actionFilter !== 'all' ? actionFilter : undefined,
        resource_id: debouncedResourceId || undefined,
      }),
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Audit Logs</h2>
        <p className="text-muted-foreground">
          Track changes across all resources
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by resource ID..."
            value={resourceIdSearch}
            onChange={(e) => setResourceIdSearch(e.target.value)}
            className="pl-9"
          />
          {resourceIdSearch && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1/2 h-6 w-6 -translate-y-1/2"
              onClick={() => setResourceIdSearch('')}
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
        <Select value={resourceTypeFilter} onValueChange={setResourceTypeFilter}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Resource type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All resources</SelectItem>
            <SelectItem value="invoice">Invoice</SelectItem>
            <SelectItem value="payment">Payment</SelectItem>
            <SelectItem value="subscription">Subscription</SelectItem>
            <SelectItem value="customer">Customer</SelectItem>
            <SelectItem value="credit_note">Credit Note</SelectItem>
          </SelectContent>
        </Select>
        <Select value={actionFilter} onValueChange={setActionFilter}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Action" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All actions</SelectItem>
            <SelectItem value="created">Created</SelectItem>
            <SelectItem value="updated">Updated</SelectItem>
            <SelectItem value="status_changed">Status Changed</SelectItem>
            <SelectItem value="deleted">Deleted</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[30px]"></TableHead>
              <TableHead>Timestamp</TableHead>
              <TableHead>Resource Type</TableHead>
              <TableHead>Resource ID</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>Actor</TableHead>
              <TableHead>Changes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(8)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-4" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-36" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                </TableRow>
              ))
            ) : !auditLogs || auditLogs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center">
                  <ScrollText className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No audit logs found
                </TableCell>
              </TableRow>
            ) : (
              auditLogs.map((log) => {
                const changeCount = Object.keys(log.changes).length
                return (
                  <Fragment key={log.id}>
                    <TableRow
                      className="cursor-pointer"
                      onClick={() => setExpandedRow(expandedRow === log.id ? null : log.id)}
                    >
                      <TableCell>
                        <ChevronRight
                          className={`h-4 w-4 transition-transform ${expandedRow === log.id ? 'rotate-90' : ''}`}
                        />
                      </TableCell>
                      <TableCell className="text-sm">
                        {format(new Date(log.created_at), 'MMM d, yyyy HH:mm:ss')}
                      </TableCell>
                      <TableCell>
                        <ResourceTypeBadge resourceType={log.resource_type} />
                      </TableCell>
                      <TableCell>
                        <CopyableId id={log.resource_id} />
                      </TableCell>
                      <TableCell>
                        <ActionBadge action={log.action} />
                      </TableCell>
                      <TableCell className="text-sm">
                        <span className="capitalize">{log.actor_type.replace(/_/g, ' ')}</span>
                        {log.actor_id && (
                          <span className="text-muted-foreground ml-1 font-mono text-xs">
                            ({log.actor_id.substring(0, 8)})
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-muted-foreground">
                          {changeCount} {changeCount === 1 ? 'field' : 'fields'}
                        </span>
                      </TableCell>
                    </TableRow>
                    {expandedRow === log.id && (
                      <TableRow>
                        <TableCell colSpan={7} className="bg-muted/50 p-4">
                          <ChangesDisplay changes={log.changes} />
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
