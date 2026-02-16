import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Search,
  Filter,
  MoreHorizontal,
  Pencil,
  Trash2,
  RefreshCw,
  Radio,
  Eye,
  CheckCircle,
  XCircle,
  Clock,
  Webhook,
  AlertTriangle,
  Loader2,
} from 'lucide-react'
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TablePagination } from '@/components/TablePagination'
import { SortableTableHead, useSortState } from '@/components/SortableTableHead'
import PageHeader from '@/components/PageHeader'
import { webhookEndpointsApi, ApiError } from '@/lib/api'

const PAGE_SIZE = 20
import type {
  WebhookEndpoint,
  WebhookEndpointCreate,
  WebhookEndpointUpdate,
  Webhook as WebhookType,
  WebhookDeliveryAttempt,
  EndpointDeliveryStats,
} from '@/types/billing'

const WEBHOOK_EVENT_TYPE_CATEGORIES: Record<string, string[]> = {
  Invoice: [
    'invoice.created',
    'invoice.finalized',
    'invoice.paid',
    'invoice.voided',
  ],
  Payment: [
    'payment.created',
    'payment.succeeded',
    'payment.failed',
  ],
  Subscription: [
    'subscription.created',
    'subscription.terminated',
    'subscription.canceled',
    'subscription.started',
    'subscription.paused',
    'subscription.resumed',
    'subscription.plan_changed',
    'subscription.trial_ended',
  ],
  Customer: [
    'customer.created',
    'customer.updated',
  ],
  'Credit Note': [
    'credit_note.created',
    'credit_note.finalized',
    'credit_note.refund.succeeded',
    'credit_note.refund.failed',
  ],
  Wallet: [
    'wallet.created',
    'wallet.terminated',
    'wallet.transaction.created',
  ],
  Usage: [
    'usage_threshold.crossed',
    'usage_alert.triggered',
  ],
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'succeeded':
      return (
        <Badge className="bg-green-600">
          <CheckCircle className="mr-1 h-3 w-3" />
          Succeeded
        </Badge>
      )
    case 'failed':
      return (
        <Badge variant="destructive">
          <XCircle className="mr-1 h-3 w-3" />
          Failed
        </Badge>
      )
    case 'pending':
      return (
        <Badge className="bg-yellow-600">
          <Clock className="mr-1 h-3 w-3" />
          Pending
        </Badge>
      )
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

function getEndpointStatusBadge(status: string) {
  switch (status) {
    case 'active':
      return (
        <Badge className="bg-green-600">
          <CheckCircle className="mr-1 h-3 w-3" />
          Active
        </Badge>
      )
    case 'inactive':
      return (
        <Badge variant="secondary">
          <XCircle className="mr-1 h-3 w-3" />
          Inactive
        </Badge>
      )
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

// --- Create/Edit Endpoint Dialog ---
function EndpointFormDialog({
  open,
  onOpenChange,
  endpoint,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  endpoint?: WebhookEndpoint | null
  onSubmit: (data: WebhookEndpointCreate | WebhookEndpointUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<{
    url: string
    signature_algo: string
    status: string
  }>({
    url: endpoint?.url ?? '',
    signature_algo: endpoint?.signature_algo ?? 'hmac',
    status: endpoint?.status ?? 'active',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (endpoint) {
      const update: WebhookEndpointUpdate = {}
      if (formData.url !== endpoint.url) update.url = formData.url
      if (formData.signature_algo !== endpoint.signature_algo)
        update.signature_algo = formData.signature_algo
      if (formData.status !== endpoint.status) update.status = formData.status
      onSubmit(update)
    } else {
      const create: WebhookEndpointCreate = {
        url: formData.url,
        signature_algo: formData.signature_algo,
      }
      onSubmit(create)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {endpoint ? 'Edit Endpoint' : 'Create Webhook Endpoint'}
            </DialogTitle>
            <DialogDescription>
              {endpoint
                ? 'Update webhook endpoint settings'
                : 'Add a new URL to receive webhook events'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="url">URL *</Label>
              <Input
                id="url"
                type="url"
                value={formData.url}
                onChange={(e) =>
                  setFormData({ ...formData, url: e.target.value })
                }
                placeholder="https://example.com/webhooks"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="signature_algo">Signature Algorithm</Label>
              <Select
                value={formData.signature_algo}
                onValueChange={(value) =>
                  setFormData({ ...formData, signature_algo: value })
                }
              >
                <SelectTrigger id="signature_algo">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="hmac">HMAC-SHA256</SelectItem>
                  <SelectItem value="jwt">JWT</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {endpoint && (
              <div className="space-y-2">
                <Label htmlFor="status">Status</Label>
                <Select
                  value={formData.status}
                  onValueChange={(value) =>
                    setFormData({ ...formData, status: value })
                  }
                >
                  <SelectTrigger id="status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter className="flex-col-reverse sm:flex-row">
            <Button
              type="button"
              variant="outline"
              className="w-full sm:w-auto"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="w-full sm:w-auto"
              disabled={isLoading || !formData.url}
            >
              {isLoading ? 'Saving...' : endpoint ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- Retry History Timeline ---
function RetryHistoryTimeline({ webhookId }: { webhookId: string }) {
  const { data: attempts = [], isLoading } = useQuery({
    queryKey: ['webhook-delivery-attempts', webhookId],
    queryFn: () => webhookEndpointsApi.deliveryAttempts(webhookId),
  })

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="flex gap-3">
            <Skeleton className="h-6 w-6 rounded-full shrink-0" />
            <div className="flex-1 space-y-1">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-48" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (attempts.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No delivery attempts recorded yet.</p>
    )
  }

  return (
    <div className="relative space-y-0">
      {attempts.map((attempt: WebhookDeliveryAttempt, index: number) => (
        <div key={attempt.id} className="relative flex gap-3 pb-4 last:pb-0">
          {/* Connector line */}
          {index < attempts.length - 1 && (
            <div className="absolute left-3 top-6 bottom-0 w-px bg-border" />
          )}

          {/* Status dot */}
          <div
            className={`relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
              attempt.success
                ? 'bg-green-100 text-green-600 dark:bg-green-950 dark:text-green-400'
                : 'bg-red-100 text-red-600 dark:bg-red-950 dark:text-red-400'
            }`}
          >
            {attempt.success ? (
              <CheckCircle className="h-3.5 w-3.5" />
            ) : attempt.error_message ? (
              <AlertTriangle className="h-3.5 w-3.5" />
            ) : (
              <XCircle className="h-3.5 w-3.5" />
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">
                {attempt.attempt_number === 0 ? 'Initial delivery' : `Retry #${attempt.attempt_number}`}
              </span>
              {attempt.success ? (
                <Badge className="bg-green-600 text-xs">Succeeded</Badge>
              ) : (
                <Badge variant="destructive" className="text-xs">Failed</Badge>
              )}
              {attempt.http_status != null && (
                <span
                  className={`text-xs font-mono ${
                    attempt.http_status >= 200 && attempt.http_status < 300
                      ? 'text-green-600'
                      : 'text-red-600'
                  }`}
                >
                  HTTP {attempt.http_status}
                </span>
              )}
            </div>

            <p className="text-xs text-muted-foreground mt-0.5">
              {format(new Date(attempt.attempted_at), 'MMM d, yyyy HH:mm:ss')}
            </p>

            {attempt.error_message && (
              <p className="text-xs text-red-600 mt-1 font-mono truncate" title={attempt.error_message}>
                {attempt.error_message}
              </p>
            )}
            {attempt.response_body && !attempt.success && (
              <p className="text-xs text-muted-foreground mt-1 font-mono truncate" title={attempt.response_body}>
                {attempt.response_body}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// --- Webhook Detail Dialog ---
function WebhookDetailDialog({
  open,
  onOpenChange,
  webhook,
  onRetry,
  isRetrying,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  webhook: WebhookType | null
  onRetry: (id: string) => void
  isRetrying: boolean
}) {
  if (!webhook) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Webhook Detail</DialogTitle>
          <DialogDescription>
            {webhook.webhook_type} — {format(new Date(webhook.created_at), 'MMM d, yyyy HH:mm:ss')}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {/* Status info */}
          <div className="rounded-md bg-muted p-3 text-sm space-y-2">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Status</span>
              {getStatusBadge(webhook.status)}
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Event Type</span>
              <code className="text-sm bg-background px-1.5 py-0.5 rounded font-medium">
                {webhook.webhook_type}
              </code>
            </div>
            {webhook.http_status !== null && webhook.http_status !== undefined && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">HTTP Status</span>
                <span className="font-medium">{webhook.http_status}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-muted-foreground">Retries</span>
              <span className="font-medium">
                {webhook.retries} / {webhook.max_retries}
              </span>
            </div>
            {webhook.last_retried_at && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Last Retry</span>
                <span className="font-medium">
                  {format(new Date(webhook.last_retried_at), 'MMM d, yyyy HH:mm:ss')}
                </span>
              </div>
            )}
            {webhook.object_type && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Object Type</span>
                <span className="font-medium">{webhook.object_type}</span>
              </div>
            )}
            {webhook.object_id && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Object ID</span>
                <code className="text-xs bg-background px-1.5 py-0.5 rounded">
                  {webhook.object_id}
                </code>
              </div>
            )}
          </div>

          {/* Delivery Attempts Timeline */}
          {webhook.retries > 0 || webhook.status !== 'pending' ? (
            <div className="space-y-2">
              <Label>Delivery Attempts</Label>
              <RetryHistoryTimeline webhookId={webhook.id} />
            </div>
          ) : null}

          {/* Payload */}
          <div className="space-y-2">
            <Label>Payload</Label>
            <pre className="rounded-md bg-muted p-3 text-xs overflow-x-auto max-h-[200px] overflow-y-auto">
              {JSON.stringify(webhook.payload, null, 2)}
            </pre>
          </div>

          {/* Response body */}
          {webhook.response && (
            <div className="space-y-2">
              <Label>Response Body</Label>
              <pre className="rounded-md bg-muted p-3 text-xs overflow-x-auto max-h-[150px] overflow-y-auto">
                {webhook.response}
              </pre>
            </div>
          )}
        </div>
        <DialogFooter>
          {webhook.status === 'failed' && (
            <Button
              onClick={() => onRetry(webhook.id)}
              disabled={isRetrying}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              {isRetrying ? 'Retrying...' : 'Retry'}
            </Button>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function WebhooksPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [webhookStatusFilter, setWebhookStatusFilter] = useState<string>('all')
  const [webhookEventTypeFilter, setWebhookEventTypeFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)
  const [editingEndpoint, setEditingEndpoint] = useState<WebhookEndpoint | null>(null)
  const [deleteEndpoint, setDeleteEndpoint] = useState<WebhookEndpoint | null>(null)
  const [selectedWebhook, setSelectedWebhook] = useState<WebhookType | null>(null)
  const [endpointsPage, setEndpointsPage] = useState(1)
  const [endpointsPageSize, setEndpointsPageSize] = useState(PAGE_SIZE)
  const { sort: endpointSort, setSort: setEndpointSort, orderBy: endpointOrderBy } = useSortState()
  const { sort: webhookSort, setSort: setWebhookSort, orderBy: webhookOrderBy } = useSortState()
  const [webhooksPage, setWebhooksPage] = useState(1)
  const [webhooksPageSize, setWebhooksPageSize] = useState(PAGE_SIZE)

  // Fetch webhook endpoints
  const {
    data: endpointsData,
    isLoading: endpointsLoading,
    error: endpointsError,
  } = useQuery({
    queryKey: ['webhook-endpoints', endpointsPage, endpointsPageSize, endpointOrderBy],
    queryFn: () => webhookEndpointsApi.listPaginated({ skip: (endpointsPage - 1) * endpointsPageSize, limit: endpointsPageSize, order_by: endpointOrderBy }),
  })

  const endpoints = endpointsData?.data ?? []
  const endpointsTotalCount = endpointsData?.totalCount ?? 0

  // Fetch recent webhooks
  const {
    data: webhooksData,
    isLoading: webhooksLoading,
  } = useQuery({
    queryKey: ['webhooks', webhooksPage, webhooksPageSize, webhookOrderBy],
    queryFn: () => webhookEndpointsApi.listWebhooksPaginated({ skip: (webhooksPage - 1) * webhooksPageSize, limit: webhooksPageSize, order_by: webhookOrderBy }),
  })

  const webhooks = webhooksData?.data ?? []
  const webhooksTotalCount = webhooksData?.totalCount ?? 0

  // Fetch delivery stats per endpoint
  const { data: deliveryStats = [] } = useQuery({
    queryKey: ['webhook-delivery-stats'],
    queryFn: () => webhookEndpointsApi.deliveryStats(),
  })

  const deliveryStatsMap = Object.fromEntries(
    deliveryStats.map((s: EndpointDeliveryStats) => [s.endpoint_id, s])
  )

  // Filter endpoints
  const filteredEndpoints = endpoints.filter((ep) => {
    const matchesSearch =
      !search || ep.url.toLowerCase().includes(search.toLowerCase())
    const matchesStatus =
      statusFilter === 'all' || ep.status === statusFilter
    return matchesSearch && matchesStatus
  })

  // Filter webhooks
  const filteredWebhooks = webhooks.filter((wh) => {
    const matchesStatus =
      webhookStatusFilter === 'all' || wh.status === webhookStatusFilter
    const matchesEventType =
      webhookEventTypeFilter === 'all' ||
      wh.webhook_type === webhookEventTypeFilter
    return matchesStatus && matchesEventType
  })

  // Stats
  const stats = {
    totalEndpoints: endpoints.length,
    activeEndpoints: endpoints.filter((ep) => ep.status === 'active').length,
    totalWebhooks: webhooks.length,
    failedWebhooks: webhooks.filter((wh) => wh.status === 'failed').length,
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: WebhookEndpointCreate) => webhookEndpointsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhook-endpoints'] })
      setFormOpen(false)
      toast.success('Webhook endpoint created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to create endpoint'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: WebhookEndpointUpdate }) =>
      webhookEndpointsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhook-endpoints'] })
      setEditingEndpoint(null)
      setFormOpen(false)
      toast.success('Webhook endpoint updated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to update endpoint'
      toast.error(message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => webhookEndpointsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhook-endpoints'] })
      queryClient.invalidateQueries({ queryKey: ['webhooks'] })
      setDeleteEndpoint(null)
      toast.success('Webhook endpoint deleted successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to delete endpoint'
      toast.error(message)
    },
  })

  // Retry mutation
  const retryMutation = useMutation({
    mutationFn: (webhookId: string) => webhookEndpointsApi.retryWebhook(webhookId),
    onSuccess: (updatedWebhook) => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] })
      queryClient.invalidateQueries({ queryKey: ['webhook-delivery-attempts', updatedWebhook.id] })
      setSelectedWebhook(updatedWebhook)
      toast.success('Webhook retry initiated')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to retry webhook'
      toast.error(message)
    },
  })

  const handleSubmit = (data: WebhookEndpointCreate | WebhookEndpointUpdate) => {
    if (editingEndpoint) {
      updateMutation.mutate({ id: editingEndpoint.id, data: data as WebhookEndpointUpdate })
    } else {
      createMutation.mutate(data as WebhookEndpointCreate)
    }
  }

  const handleEdit = (endpoint: WebhookEndpoint) => {
    setEditingEndpoint(endpoint)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingEndpoint(null)
    }
    setFormOpen(open)
  }

  if (endpointsError) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load webhooks. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Webhooks"
        description="Manage webhook endpoints and monitor delivery status"
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create Endpoint
          </Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Endpoints
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalEndpoints}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Endpoints
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats.activeEndpoints}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Recent Webhooks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalWebhooks}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Failed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {stats.failedWebhooks}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs for Endpoints and Recent Webhooks */}
      <Tabs defaultValue="endpoints">
        <TabsList>
          <TabsTrigger value="endpoints">
            Endpoints{!endpointsLoading && ` (${endpoints.length})`}
          </TabsTrigger>
          <TabsTrigger value="webhooks">
            Recent Webhooks{!webhooksLoading && ` (${webhooks.length})`}
          </TabsTrigger>
        </TabsList>

        {/* Endpoints Tab */}
        <TabsContent value="endpoints" className="space-y-4">
          {/* Filters */}
          <div className="flex flex-col md:flex-row md:items-center gap-4">
            <div className="relative flex-1 md:max-w-sm">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by URL..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full md:w-[180px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Endpoints Table */}
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableTableHead label="URL" sortKey="url" sort={endpointSort} onSort={setEndpointSort} />
                  <TableHead className="hidden md:table-cell">Signature Algorithm</TableHead>
                  <SortableTableHead label="Status" sortKey="status" sort={endpointSort} onSort={setEndpointSort} />
                  <TableHead className="hidden md:table-cell">Delivery Rate</TableHead>
                  <SortableTableHead className="hidden md:table-cell" label="Created" sortKey="created_at" sort={endpointSort} onSort={setEndpointSort} />
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {endpointsLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><Skeleton className="h-5 w-48" /></TableCell>
                      <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-24" /></TableCell>
                      <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                      <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-24" /></TableCell>
                      <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-20" /></TableCell>
                      <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                    </TableRow>
                  ))
                ) : filteredEndpoints.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="h-24 text-center text-muted-foreground"
                    >
                      <Radio className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                      No webhook endpoints found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredEndpoints.map((endpoint) => (
                    <TableRow key={endpoint.id}>
                      <TableCell>
                        <code className="text-sm bg-muted px-1.5 py-0.5 rounded font-medium break-all">
                          {endpoint.url}
                        </code>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <Badge variant="outline">
                          {endpoint.signature_algo === 'hmac'
                            ? 'HMAC-SHA256'
                            : endpoint.signature_algo.toUpperCase()}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {getEndpointStatusBadge(endpoint.status)}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {(() => {
                          const epStats = deliveryStatsMap[endpoint.id]
                          if (!epStats || epStats.total === 0) {
                            return (
                              <span className="text-sm text-muted-foreground">
                                No deliveries
                              </span>
                            )
                          }
                          const rate = epStats.success_rate
                          const color =
                            rate >= 95
                              ? 'text-green-600'
                              : rate >= 80
                                ? 'text-yellow-600'
                                : 'text-red-600'
                          return (
                            <div className="flex items-center gap-2">
                              <div className="flex-1 max-w-[80px]">
                                <div className="h-2 rounded-full bg-muted overflow-hidden">
                                  <div
                                    className={`h-full rounded-full ${
                                      rate >= 95
                                        ? 'bg-green-600'
                                        : rate >= 80
                                          ? 'bg-yellow-600'
                                          : 'bg-red-600'
                                    }`}
                                    style={{ width: `${rate}%` }}
                                  />
                                </div>
                              </div>
                              <span className={`text-sm font-medium ${color}`}>
                                {rate}%
                              </span>
                              <span className="text-xs text-muted-foreground">
                                ({epStats.succeeded}/{epStats.total})
                              </span>
                            </div>
                          )
                        })()}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-muted-foreground text-sm">
                        {format(new Date(endpoint.created_at), 'MMM d, yyyy')}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleEdit(endpoint)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => setDeleteEndpoint(endpoint)}
                              className="text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
            <TablePagination
              page={endpointsPage}
              pageSize={endpointsPageSize}
              totalCount={endpointsTotalCount}
              onPageChange={setEndpointsPage}
              onPageSizeChange={(size) => { setEndpointsPageSize(size); setEndpointsPage(1) }}
            />
          </div>
        </TabsContent>

        {/* Recent Webhooks Tab */}
        <TabsContent value="webhooks" className="space-y-4">
          {/* Filters */}
          <div className="flex flex-col md:flex-row md:items-center gap-4">
            <Select value={webhookStatusFilter} onValueChange={setWebhookStatusFilter}>
              <SelectTrigger className="w-full md:w-[180px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="succeeded">Succeeded</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
              </SelectContent>
            </Select>
            <Select value={webhookEventTypeFilter} onValueChange={setWebhookEventTypeFilter}>
              <SelectTrigger className="w-full md:w-[260px]">
                <Filter className="mr-2 h-4 w-4 text-muted-foreground" />
                <SelectValue placeholder="Event Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Event Types</SelectItem>
                {Object.entries(WEBHOOK_EVENT_TYPE_CATEGORIES).map(
                  ([category, types]) => (
                    <div key={category}>
                      <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                        {category}
                      </div>
                      {types.map((type) => (
                        <SelectItem key={type} value={type}>
                          {type}
                        </SelectItem>
                      ))}
                    </div>
                  )
                )}
              </SelectContent>
            </Select>
          </div>

          {/* Webhooks Table */}
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableTableHead label="Event Type" sortKey="webhook_type" sort={webhookSort} onSort={setWebhookSort} />
                  <SortableTableHead label="Status" sortKey="status" sort={webhookSort} onSort={setWebhookSort} />
                  <TableHead className="hidden md:table-cell">HTTP Status</TableHead>
                  <TableHead className="hidden md:table-cell">Retries</TableHead>
                  <SortableTableHead label="Timestamp" sortKey="created_at" sort={webhookSort} onSort={setWebhookSort} />
                  <TableHead className="w-[80px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {webhooksLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                      <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                      <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-12" /></TableCell>
                      <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-12" /></TableCell>
                      <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                      <TableCell><Skeleton className="h-8 w-16" /></TableCell>
                    </TableRow>
                  ))
                ) : filteredWebhooks.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="h-24 text-center text-muted-foreground"
                    >
                      <Webhook className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                      {webhookStatusFilter !== 'all' || webhookEventTypeFilter !== 'all'
                        ? 'No webhooks match your filters'
                        : 'No webhooks found'}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredWebhooks.map((wh) => (
                    <TableRow key={wh.id}>
                      <TableCell>
                        <code className="text-sm bg-muted px-1.5 py-0.5 rounded font-medium">
                          {wh.webhook_type}
                        </code>
                      </TableCell>
                      <TableCell>{getStatusBadge(wh.status)}</TableCell>
                      <TableCell className="hidden md:table-cell text-sm">
                        {wh.http_status !== null && wh.http_status !== undefined ? (
                          <span
                            className={
                              wh.http_status >= 200 && wh.http_status < 300
                                ? 'text-green-600 font-medium'
                                : 'text-red-600 font-medium'
                            }
                          >
                            {wh.http_status}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm">
                        {wh.retries} / {wh.max_retries}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {format(new Date(wh.created_at), 'MMM d, yyyy HH:mm')}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setSelectedWebhook(wh)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          {wh.status === 'failed' && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => retryMutation.mutate(wh.id)}
                              disabled={retryMutation.isPending}
                            >
                              <RefreshCw className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
            <TablePagination
              page={webhooksPage}
              pageSize={webhooksPageSize}
              totalCount={webhooksTotalCount}
              onPageChange={setWebhooksPage}
              onPageSizeChange={(size) => { setWebhooksPageSize(size); setWebhooksPage(1) }}
            />
          </div>
        </TabsContent>
      </Tabs>

      {/* Create/Edit Dialog */}
      <EndpointFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        endpoint={editingEndpoint}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Webhook Detail Dialog */}
      <WebhookDetailDialog
        open={!!selectedWebhook}
        onOpenChange={(open) => !open && setSelectedWebhook(null)}
        webhook={selectedWebhook}
        onRetry={(id) => retryMutation.mutate(id)}
        isRetrying={retryMutation.isPending}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteEndpoint}
        onOpenChange={(open) => !open && setDeleteEndpoint(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Webhook Endpoint</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the endpoint at &quot;
              {deleteEndpoint?.url}&quot;? This will stop all webhook
              deliveries to this URL. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteEndpoint && deleteMutation.mutate(deleteEndpoint.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
