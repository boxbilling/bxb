import { Fragment, useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Activity, Pause, Play, X } from 'lucide-react'
import { format } from 'date-fns'

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
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { eventsApi } from '@/lib/api'

const POLLING_INTERVAL = 5000

export default function EventsPage() {
  const [customerFilter, setCustomerFilter] = useState('')
  const [codeFilter, setCodeFilter] = useState('')
  const [isPolling, setIsPolling] = useState(true)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

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

  const { data: events, isLoading, error, dataUpdatedAt } = useQuery({
    queryKey: ['events', { external_customer_id: debouncedCustomer || undefined, code: debouncedCode || undefined }],
    queryFn: () =>
      eventsApi.list({
        limit: 100,
        external_customer_id: debouncedCustomer || undefined,
        code: debouncedCode || undefined,
      }),
    refetchInterval: isPolling ? POLLING_INTERVAL : false,
  })

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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Events Stream</h2>
          <p className="text-muted-foreground">
            Monitor incoming billing events in real-time
          </p>
        </div>
        <div className="flex items-center gap-3">
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
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
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
        <div className="relative flex-1 max-w-sm">
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
      </div>

      {/* Last updated */}
      {dataUpdatedAt > 0 && (
        <p className="text-xs text-muted-foreground">
          Last updated: {format(new Date(dataUpdatedAt), 'HH:mm:ss')}
        </p>
      )}

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[180px]">Timestamp</TableHead>
              <TableHead>Transaction ID</TableHead>
              <TableHead>Customer ID</TableHead>
              <TableHead>Code</TableHead>
              <TableHead>Properties</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(10)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-36" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                </TableRow>
              ))
            ) : !events || events.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <Activity className="h-8 w-8" />
                    <p>No events found</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              events.map((event) => (
                <Fragment key={event.id}>
                  <TableRow
                    className="cursor-pointer"
                    onClick={() => setExpandedRow(expandedRow === event.id ? null : event.id)}
                  >
                    <TableCell>
                      <span className="text-sm">
                        {format(new Date(event.timestamp), 'MMM d, yyyy HH:mm:ss')}
                      </span>
                    </TableCell>
                    <TableCell>
                      <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
                        {event.transaction_id}
                      </code>
                    </TableCell>
                    <TableCell>
                      <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                        {event.external_customer_id}
                      </code>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{event.code}</Badge>
                    </TableCell>
                    <TableCell>
                      {Object.keys(event.properties).length > 0 ? (
                        <code className="text-xs text-muted-foreground">
                          {JSON.stringify(event.properties).length > 50
                            ? JSON.stringify(event.properties).slice(0, 50) + '...'
                            : JSON.stringify(event.properties)}
                        </code>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                  {expandedRow === event.id && (
                    <TableRow key={`${event.id}-details`}>
                      <TableCell colSpan={5} className="bg-muted/50 p-4">
                        <pre className="whitespace-pre-wrap break-all text-xs font-mono">
                          {JSON.stringify(event.properties, null, 2)}
                        </pre>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
