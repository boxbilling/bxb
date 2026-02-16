import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { useQuery, useMutation, useInfiniteQuery } from '@tanstack/react-query'
import { Search, Activity, Pause, Play, X, Calculator, Loader2, CalendarIcon, BarChart2, RefreshCw, MoreHorizontal } from 'lucide-react'
import { format, subDays, subMonths, startOfDay, endOfDay } from 'date-fns'
import { toast } from 'sonner'
import { useVirtualizer } from '@tanstack/react-virtual'
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip } from 'recharts'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import PageHeader from '@/components/PageHeader'
import { eventsApi, subscriptionsApi, billableMetricsApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'
import type { EstimateFeesResponse } from '@/types/billing'
import type { DateRange } from 'react-day-picker'

function FeeEstimatorPanel({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [subscriptionId, setSubscriptionId] = useState('')
  const [metricCode, setMetricCode] = useState('')
  const [propertiesJson, setPropertiesJson] = useState('{}')
  const [estimateResult, setEstimateResult] = useState<EstimateFeesResponse | null>(null)

  const { data: subscriptions = [] } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => subscriptionsApi.list(),
    enabled: open,
  })

  const { data: metrics = [] } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: () => billableMetricsApi.list(),
    enabled: open,
  })

  const estimateMutation = useMutation({
    mutationFn: () => {
      let properties: Record<string, unknown> = {}
      try {
        properties = JSON.parse(propertiesJson)
      } catch {
        // use empty object if invalid JSON
      }
      return eventsApi.estimateFees({
        subscription_id: subscriptionId,
        code: metricCode,
        properties,
      })
    },
    onSuccess: (data) => {
      setEstimateResult(data)
    },
    onError: () => {
      toast.error('Failed to estimate fees')
    },
  })

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setSubscriptionId('')
      setMetricCode('')
      setPropertiesJson('{}')
      setEstimateResult(null)
    }
    onOpenChange(nextOpen)
  }

  return (
    <Sheet open={open} onOpenChange={handleOpenChange} modal={false}>
      <SheetContent side="right" className="sm:max-w-md overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Fee Estimator</SheetTitle>
          <SheetDescription>
            Estimate fees for an event while viewing the event stream
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-4 px-4 pb-4">
          <div className="space-y-2">
            <Label>Subscription</Label>
            <Select value={subscriptionId} onValueChange={setSubscriptionId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a subscription" />
              </SelectTrigger>
              <SelectContent>
                {subscriptions.map((sub) => (
                  <SelectItem key={sub.id} value={sub.id}>
                    {sub.external_id} ({sub.status})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Metric Code</Label>
            <Select value={metricCode} onValueChange={setMetricCode}>
              <SelectTrigger>
                <SelectValue placeholder="Select a metric" />
              </SelectTrigger>
              <SelectContent>
                {metrics.map((metric) => (
                  <SelectItem key={metric.id} value={metric.code}>
                    {metric.name} ({metric.code})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Properties (JSON)</Label>
            <Textarea
              value={propertiesJson}
              onChange={(e) => setPropertiesJson(e.target.value)}
              placeholder='{"key": "value"}'
              className="font-mono text-sm"
            />
          </div>

          <Button
            className="w-full"
            disabled={!subscriptionId || !metricCode || estimateMutation.isPending}
            onClick={() => estimateMutation.mutate()}
          >
            {estimateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Estimate
          </Button>

          {estimateResult && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Estimation Result</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-muted-foreground">Estimated Amount</p>
                    <p className="text-lg font-bold">
                      {formatCents(estimateResult.amount_cents)}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Units</p>
                    <p className="text-lg font-bold">{estimateResult.units}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Unit Price</p>
                    <p className="font-medium">{formatCents(estimateResult.unit_amount_cents)}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Charge Model</p>
                    <p className="font-medium capitalize">{estimateResult.charge_model ?? '—'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

const POLLING_INTERVAL = 5000
const PAGE_SIZE = 100

type DatePreset = 'all' | '1h' | '24h' | '7d' | '30d' | 'custom'

const DATE_PRESET_LABELS: Record<DatePreset, string> = {
  all: 'All time',
  '1h': 'Last hour',
  '24h': 'Last 24 hours',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  custom: 'Custom range',
}

function getPresetTimestamps(preset: DatePreset): { from?: string; to?: string } {
  if (preset === 'all' || preset === 'custom') return {}
  const now = new Date()
  let from: Date
  switch (preset) {
    case '1h':
      from = new Date(now.getTime() - 60 * 60 * 1000)
      break
    case '24h':
      from = subDays(now, 1)
      break
    case '7d':
      from = startOfDay(subDays(now, 7))
      break
    case '30d':
      from = startOfDay(subMonths(now, 1))
      break
  }
  return { from: from.toISOString(), to: now.toISOString() }
}

const ROW_HEIGHT = 41
const EXPANDED_ROW_HEIGHT = 160

export default function EventsPage() {
  const [customerFilter, setCustomerFilter] = useState('')
  const [codeFilter, setCodeFilter] = useState('')
  const [isPolling, setIsPolling] = useState(true)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [feeEstimatorOpen, setFeeEstimatorOpen] = useState(false)
  const [datePreset, setDatePreset] = useState<DatePreset>('all')
  const [customRange, setCustomRange] = useState<DateRange | undefined>(undefined)
  const [calendarOpen, setCalendarOpen] = useState(false)

  const scrollContainerRef = useRef<HTMLDivElement>(null)

  // Debounce filter values
  const [debouncedCustomer, setDebouncedCustomer] = useState('')
  const [debouncedCode, setDebouncedCode] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedCustomer(customerFilter), 300)
    return () => clearTimeout(timer)
  }, [customerFilter])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedCode(codeFilter), 300)
    return () => clearTimeout(timer)
  }, [codeFilter])

  const dateParams = useMemo(() => {
    if (datePreset === 'custom' && customRange?.from) {
      return {
        from_timestamp: startOfDay(customRange.from).toISOString(),
        to_timestamp: customRange.to
          ? endOfDay(customRange.to).toISOString()
          : endOfDay(customRange.from).toISOString(),
      }
    }
    if (datePreset !== 'all' && datePreset !== 'custom') {
      const { from, to } = getPresetTimestamps(datePreset)
      return { from_timestamp: from, to_timestamp: to }
    }
    return {}
  }, [datePreset, customRange])

  const filterParams = useMemo(() => ({
    external_customer_id: debouncedCustomer || undefined,
    code: debouncedCode || undefined,
    ...dateParams,
  }), [debouncedCustomer, debouncedCode, dateParams])

  const {
    data,
    isLoading,
    error,
    dataUpdatedAt,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['events', filterParams],
    queryFn: ({ pageParam = 0 }) =>
      eventsApi.listPaginated({
        skip: pageParam,
        limit: PAGE_SIZE,
        ...filterParams,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, _allPages, lastPageParam) => {
      const nextSkip = lastPageParam + PAGE_SIZE
      if (nextSkip >= lastPage.totalCount) return undefined
      return nextSkip
    },
    refetchInterval: isPolling ? POLLING_INTERVAL : false,
  })

  const allEvents = useMemo(
    () => data?.pages.flatMap((page) => page.data) ?? [],
    [data],
  )

  const totalCount = data?.pages[0]?.totalCount ?? 0

  const { data: volumeData } = useQuery({
    queryKey: ['event-volume', dateParams],
    queryFn: () =>
      eventsApi.getVolume({
        from_timestamp: dateParams.from_timestamp,
        to_timestamp: dateParams.to_timestamp,
      }),
    refetchInterval: isPolling ? POLLING_INTERVAL : false,
  })

  const reprocessMutation = useMutation({
    mutationFn: (eventId: string) => eventsApi.reprocess(eventId),
    onSuccess: (data) => {
      if (data.status === 'no_active_subscriptions') {
        toast.info('No active subscriptions found for this event\'s customer')
      } else {
        toast.success(`Reprocessing event across ${data.subscriptions_checked} subscription${data.subscriptions_checked === 1 ? '' : 's'}`)
      }
    },
    onError: () => {
      toast.error('Failed to reprocess event')
    },
  })

  const rowVirtualizer = useVirtualizer({
    count: allEvents.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: (index) => {
      const event = allEvents[index]
      if (event && expandedRow === event.id) {
        return ROW_HEIGHT + EXPANDED_ROW_HEIGHT
      }
      return ROW_HEIGHT
    },
    overscan: 20,
  })

  // Trigger fetch when scrolling near the bottom
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current
    if (!container) return
    const { scrollTop, scrollHeight, clientHeight } = container
    if (scrollHeight - scrollTop - clientHeight < 300 && hasNextPage && !isFetchingNextPage) {
      fetchNextPage()
    }
  }, [fetchNextPage, hasNextPage, isFetchingNextPage])

  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return
    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [handleScroll])

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load events. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Events Stream"
        description="Monitor incoming billing events in real-time"
        actions={
          <>
            {isPolling ? (
              <Badge variant="outline" className="gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
                </span>
                Live
              </Badge>
            ) : (
              <Badge variant="outline" className="gap-1.5 text-muted-foreground">
                <Pause className="h-3 w-3" />
                Paused
              </Badge>
            )}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => setIsPolling(!isPolling)}
                  >
                    {isPolling ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {isPolling ? 'Pause live updates' : 'Resume live updates'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <Button onClick={() => setFeeEstimatorOpen(true)}>
              <Calculator className="mr-2 h-4 w-4" />
              Fee Estimator
            </Button>
          </>
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter by customer ID..."
            value={customerFilter}
            onChange={(e) => setCustomerFilter(e.target.value)}
            className="pl-9"
          />
          {customerFilter && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1/2 h-6 w-6 -translate-y-1/2"
              onClick={() => setCustomerFilter('')}
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter by event code..."
            value={codeFilter}
            onChange={(e) => setCodeFilter(e.target.value)}
            className="pl-9"
          />
          {codeFilter && (
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-1 top-1/2 h-6 w-6 -translate-y-1/2"
              onClick={() => setCodeFilter('')}
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={datePreset}
            onValueChange={(v) => {
              const p = v as DatePreset
              setDatePreset(p)
              if (p === 'custom') setCalendarOpen(true)
              if (p !== 'custom') setCustomRange(undefined)
            }}
          >
            <SelectTrigger className="w-[160px]">
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
                      ? `${format(customRange.from, 'MMM d, yyyy')} – ${format(customRange.to, 'MMM d, yyyy')}`
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

      {/* Status bar */}
      <div className="flex items-center justify-between">
        {dataUpdatedAt > 0 && (
          <p className="text-xs text-muted-foreground">
            Last updated: {format(new Date(dataUpdatedAt), 'HH:mm:ss')}
          </p>
        )}
        {!isLoading && allEvents.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Showing {allEvents.length.toLocaleString()} of {totalCount.toLocaleString()} events
          </p>
        )}
      </div>

      {/* Event Volume Chart */}
      {volumeData && volumeData.data_points.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <BarChart2 className="h-4 w-4 text-muted-foreground" />
              Event Volume (events/hour)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[120px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={volumeData.data_points}>
                  <defs>
                    <linearGradient id="volumeFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="timestamp"
                    tick={{ fontSize: 11 }}
                    className="text-muted-foreground"
                    tickFormatter={(v: string) => {
                      const parts = v.split(' ')
                      return parts.length > 1 ? parts[1] : v
                    }}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    className="text-muted-foreground"
                    allowDecimals={false}
                    width={40}
                  />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--background))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '6px',
                      fontSize: '12px',
                    }}
                    formatter={(value: number) => [value.toLocaleString(), 'Events']}
                    labelFormatter={(label: string) => label}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="hsl(var(--primary))"
                    strokeWidth={1.5}
                    fill="url(#volumeFill)"
                    dot={false}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Virtualized Table */}
      <div className="rounded-md border">
        {/* Fixed table header */}
        <div className="border-b">
          <table className="w-full caption-bottom text-sm">
            <thead className="[&_tr]:border-b">
              <tr className="border-b transition-colors hover:bg-muted/50">
                <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground w-[180px]">Timestamp</th>
                <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">Transaction ID</th>
                <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">Customer ID</th>
                <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">Code</th>
                <th className="h-10 px-4 text-left align-middle font-medium text-muted-foreground">Properties</th>
                <th className="h-10 px-4 text-right align-middle font-medium text-muted-foreground w-[80px]">Actions</th>
              </tr>
            </thead>
          </table>
        </div>

        {/* Scrollable virtual body */}
        <div
          ref={scrollContainerRef}
          className="overflow-auto"
          style={{ maxHeight: 'calc(100vh - 380px)', minHeight: '200px' }}
        >
          {isLoading ? (
            <table className="w-full caption-bottom text-sm">
              <tbody>
                {[...Array(10)].map((_, i) => (
                  <tr key={i} className="border-b transition-colors">
                    <td className="p-4 align-middle w-[180px]"><Skeleton className="h-5 w-36" /></td>
                    <td className="p-4 align-middle"><Skeleton className="h-5 w-48" /></td>
                    <td className="p-4 align-middle"><Skeleton className="h-5 w-28" /></td>
                    <td className="p-4 align-middle"><Skeleton className="h-5 w-24" /></td>
                    <td className="p-4 align-middle"><Skeleton className="h-5 w-32" /></td>
                    <td className="p-4 align-middle text-right"><Skeleton className="h-7 w-7 ml-auto" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : allEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 text-muted-foreground h-24">
              <Activity className="h-8 w-8" />
              <p>No events found</p>
            </div>
          ) : (
            <div
              style={{
                height: `${rowVirtualizer.getTotalSize()}px`,
                width: '100%',
                position: 'relative',
              }}
            >
              {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                const event = allEvents[virtualRow.index]
                const isExpanded = expandedRow === event.id
                return (
                  <div
                    key={event.id}
                    data-index={virtualRow.index}
                    ref={rowVirtualizer.measureElement}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    <table className="w-full caption-bottom text-sm">
                      <tbody>
                        <tr
                          className="border-b transition-colors hover:bg-muted/50 cursor-pointer"
                          onClick={() => setExpandedRow(isExpanded ? null : event.id)}
                        >
                          <td className="p-4 align-middle w-[180px]">
                            <span className="text-sm">
                              {format(new Date(event.timestamp), 'MMM d, yyyy HH:mm:ss')}
                            </span>
                          </td>
                          <td className="p-4 align-middle">
                            <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
                              {event.transaction_id}
                            </code>
                          </td>
                          <td className="p-4 align-middle">
                            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                              {event.external_customer_id}
                            </code>
                          </td>
                          <td className="p-4 align-middle">
                            <Badge variant="outline">{event.code}</Badge>
                          </td>
                          <td className="p-4 align-middle">
                            {Object.keys(event.properties).length > 0 ? (
                              <div className="flex flex-wrap gap-1 max-w-[300px]">
                                {Object.entries(event.properties).slice(0, 3).map(([key, value]) => (
                                  <Badge key={key} variant="outline" className="text-xs font-normal gap-0.5 py-0">
                                    <span className="font-medium">{key}:</span>{' '}
                                    <span className="text-muted-foreground truncate max-w-[80px]">
                                      {String(value)}
                                    </span>
                                  </Badge>
                                ))}
                                {Object.keys(event.properties).length > 3 && (
                                  <Badge variant="secondary" className="text-xs font-normal py-0">
                                    +{Object.keys(event.properties).length - 3}
                                  </Badge>
                                )}
                              </div>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                          <td className="p-4 align-middle text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <MoreHorizontal className="h-3.5 w-3.5" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  disabled={reprocessMutation.isPending}
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    reprocessMutation.mutate(event.id)
                                  }}
                                >
                                  <RefreshCw className={`mr-2 h-4 w-4 ${reprocessMutation.isPending && reprocessMutation.variables === event.id ? 'animate-spin' : ''}`} />
                                  Reprocess
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr className="border-b">
                            <td colSpan={6} className="bg-muted/50 p-4">
                              {Object.keys(event.properties).length > 0 ? (
                                <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 max-w-lg">
                                  {Object.entries(event.properties).map(([key, value]) => (
                                    <div key={key} className="contents">
                                      <span className="text-xs font-medium text-muted-foreground">{key}</span>
                                      <span className="text-xs font-mono break-all">
                                        {typeof value === 'object' && value !== null
                                          ? JSON.stringify(value)
                                          : String(value)}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <span className="text-xs text-muted-foreground">No properties</span>
                              )}
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )
              })}
            </div>
          )}

          {/* Loading more indicator */}
          {isFetchingNextPage && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">Loading more events...</span>
            </div>
          )}

          {/* End of list indicator */}
          {!hasNextPage && allEvents.length > 0 && !isLoading && (
            <div className="flex items-center justify-center py-3">
              <span className="text-xs text-muted-foreground">
                All {totalCount.toLocaleString()} events loaded
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Fee Estimator Panel */}
      <FeeEstimatorPanel open={feeEstimatorOpen} onOpenChange={setFeeEstimatorOpen} />
    </div>
  )
}
