import { Fragment, useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Search, Activity, Pause, Play, X, Calculator, Loader2 } from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { eventsApi, subscriptionsApi, billableMetricsApi } from '@/lib/api'
import type { EstimateFeesResponse } from '@/types/billing'

function formatCurrency(amount: string | number, currency: string = 'USD') {
  const value = typeof amount === 'number' ? amount / 100 : parseFloat(amount)
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(value)
}

function FeeEstimatorDialog({
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
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Fee Estimator</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
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
                      {formatCurrency(estimateResult.amount_cents)}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Units</p>
                    <p className="text-lg font-bold">{estimateResult.units}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Unit Price</p>
                    <p className="font-medium">{formatCurrency(estimateResult.unit_amount_cents)}</p>
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
      </DialogContent>
    </Dialog>
  )
}

const POLLING_INTERVAL = 5000

export default function EventsPage() {
  const [customerFilter, setCustomerFilter] = useState('')
  const [codeFilter, setCodeFilter] = useState('')
  const [isPolling, setIsPolling] = useState(true)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [feeEstimatorOpen, setFeeEstimatorOpen] = useState(false)

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
          <Button onClick={() => setFeeEstimatorOpen(true)}>
            <Calculator className="mr-2 h-4 w-4" />
            Fee Estimator
          </Button>
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

      {/* Fee Estimator Dialog */}
      <FeeEstimatorDialog open={feeEstimatorOpen} onOpenChange={setFeeEstimatorOpen} />
    </div>
  )
}
