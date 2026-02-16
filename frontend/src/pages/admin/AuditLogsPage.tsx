import { Fragment, useState, useEffect, useMemo } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Search, ScrollText, X, Copy, ChevronRight, CalendarIcon, ExternalLink, Download } from 'lucide-react'
import { format, subDays, subMonths } from 'date-fns'
import { toast } from 'sonner'
import type { DateRange } from 'react-day-picker'

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
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import { ChangesDisplay } from '@/components/JsonDiffDisplay'
import { TablePagination } from '@/components/TablePagination'
import { auditLogsApi, dataExportsApi, ApiError } from '@/lib/api'
import type { AuditLog } from '@/types/billing'

const PAGE_SIZE = 20

const RESOURCE_TYPE_ROUTES: Record<string, string> = {
  customer: '/admin/customers',
  invoice: '/admin/invoices',
  subscription: '/admin/subscriptions',
  plan: '/admin/plans',
  wallet: '/admin/wallets',
  credit_note: '/admin/credit-notes',
  dunning_campaign: '/admin/dunning-campaigns',
  integration: '/admin/integrations',
}

function getResourceUrl(resourceType: string, resourceId: string): string | null {
  const base = RESOURCE_TYPE_ROUTES[resourceType]
  if (!base) return null
  return `${base}/${resourceId}`
}

type DatePreset = 'all' | '24h' | '7d' | '30d' | '90d' | 'custom'

const DATE_PRESET_LABELS: Record<DatePreset, string> = {
  all: 'All time',
  '24h': 'Last 24 hours',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  '90d': 'Last 90 days',
  custom: 'Custom range',
}

function getPresetDates(preset: DatePreset): { start: Date; end: Date } | null {
  if (preset === 'all') return null
  const end = new Date()
  switch (preset) {
    case '24h':
      return { start: subDays(end, 1), end }
    case '7d':
      return { start: subDays(end, 7), end }
    case '30d':
      return { start: subDays(end, 30), end }
    case '90d':
      return { start: subDays(end, 90), end }
    default:
      return null
  }
}

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

export default function AuditLogsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [resourceTypeFilter, setResourceTypeFilter] = useState(searchParams.get('resource_type') || 'all')
  const [actionFilter, setActionFilter] = useState('all')
  const [actorTypeFilter, setActorTypeFilter] = useState('all')
  const [resourceIdSearch, setResourceIdSearch] = useState(searchParams.get('resource_id') || '')
  const [debouncedResourceId, setDebouncedResourceId] = useState(resourceIdSearch)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [datePreset, setDatePreset] = useState<DatePreset>('all')
  const [customRange, setCustomRange] = useState<DateRange | undefined>()
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedResourceId(resourceIdSearch), 300)
    return () => clearTimeout(timer)
  }, [resourceIdSearch])

  // Reset to first page when filters change
  useEffect(() => {
    setPage(1)
  }, [resourceTypeFilter, actionFilter, actorTypeFilter, debouncedResourceId, datePreset, customRange])

  const dateParams = useMemo(() => {
    if (datePreset === 'custom' && customRange?.from) {
      return {
        start_date: customRange.from.toISOString(),
        end_date: customRange.to ? customRange.to.toISOString() : new Date().toISOString(),
      }
    }
    const dates = getPresetDates(datePreset)
    if (!dates) return {}
    return {
      start_date: dates.start.toISOString(),
      end_date: dates.end.toISOString(),
    }
  }, [datePreset, customRange])

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', page, pageSize, { resourceTypeFilter, actionFilter, actorTypeFilter, debouncedResourceId, dateParams }],
    queryFn: () =>
      auditLogsApi.listPaginated({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        resource_type: resourceTypeFilter !== 'all' ? resourceTypeFilter : undefined,
        action: actionFilter !== 'all' ? actionFilter : undefined,
        actor_type: actorTypeFilter !== 'all' ? actorTypeFilter : undefined,
        resource_id: debouncedResourceId || undefined,
        ...dateParams,
      }),
  })

  const auditLogs = data?.data
  const totalCount = data?.totalCount ?? 0

  const exportMutation = useMutation({
    mutationFn: () => {
      const filters: Record<string, string> = {}
      if (resourceTypeFilter !== 'all') filters.resource_type = resourceTypeFilter
      if (actionFilter !== 'all') filters.action = actionFilter
      if (actorTypeFilter !== 'all') filters.actor_type = actorTypeFilter
      return dataExportsApi.create({
        export_type: 'audit_logs' as const,
        filters: Object.keys(filters).length > 0 ? filters : undefined,
      })
    },
    onSuccess: () => {
      toast.success('Audit log export created')
      navigate('/admin/data-exports')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to create export'
      toast.error(message)
    },
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Audit Logs</h2>
          <p className="text-muted-foreground">
            Track changes across all resources
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => exportMutation.mutate()}
          disabled={exportMutation.isPending}
        >
          <Download className="mr-2 h-4 w-4" />
          {exportMutation.isPending ? 'Exporting...' : 'Export to CSV'}
        </Button>
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
        <Select value={actorTypeFilter} onValueChange={setActorTypeFilter}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Actor type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All actors</SelectItem>
            <SelectItem value="system">System</SelectItem>
            <SelectItem value="api_key">API Key</SelectItem>
            <SelectItem value="webhook">Webhook</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2">
          <Select
            value={datePreset}
            onValueChange={(v) => {
              const p = v as DatePreset
              setDatePreset(p)
              if (p === 'custom') setCalendarOpen(true)
            }}
          >
            <SelectTrigger className="w-44">
              <CalendarIcon className="mr-1 h-3.5 w-3.5" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(DATE_PRESET_LABELS).map(([key, label]) => (
                <SelectItem key={key} value={key}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {datePreset === 'custom' && (
            <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="font-normal">
                  {customRange?.from
                    ? customRange.to
                      ? `${format(customRange.from, 'MMM d, yyyy')} - ${format(customRange.to, 'MMM d, yyyy')}`
                      : format(customRange.from, 'MMM d, yyyy')
                    : 'Pick dates'}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="end">
                <Calendar
                  mode="range"
                  selected={customRange}
                  onSelect={setCustomRange}
                  numberOfMonths={2}
                  disabled={{ after: new Date() }}
                />
              </PopoverContent>
            </Popover>
          )}
        </div>
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
                        <div className="flex items-center gap-1.5">
                          <CopyableId id={log.resource_id} />
                          {getResourceUrl(log.resource_type, log.resource_id) && (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <Link
                                    to={getResourceUrl(log.resource_type, log.resource_id)!}
                                    className="inline-flex items-center text-muted-foreground hover:text-primary transition-colors"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <ExternalLink className="h-3 w-3" />
                                  </Link>
                                </TooltipTrigger>
                                <TooltipContent>View {log.resource_type.replace(/_/g, ' ')}</TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}
                        </div>
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
                          {getResourceUrl(log.resource_type, log.resource_id) && (
                            <div className="mt-3 pt-3 border-t">
                              <Link
                                to={getResourceUrl(log.resource_type, log.resource_id)!}
                                className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                              >
                                View {log.resource_type.replace(/_/g, ' ')}
                                <ExternalLink className="h-3.5 w-3.5" />
                              </Link>
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                )
              })
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          pageSize={pageSize}
          totalCount={totalCount}
          onPageChange={setPage}
          onPageSizeChange={(size) => { setPageSize(size); setPage(1) }}
        />
      </div>
    </div>
  )
}
