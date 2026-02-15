import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Megaphone,
  Clock,
  Mail,
  Shield,
  BarChart3,
  Play,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  FileText,
  User,
  DollarSign,
  Eye,
  ChevronRight,
} from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { AuditTrailTimeline } from '@/components/AuditTrailTimeline'
import { dunningCampaignsApi, ApiError } from '@/lib/api'
import type {
  CampaignTimelineEvent,
  ExecutionHistoryEntry,
  CampaignPreviewInvoiceGroup,
} from '@/types/billing'
import { formatCents } from '@/lib/utils'

function StatusBadge({ status }: { status: string }) {
  if (status === 'active') return <Badge className="bg-green-600">Active</Badge>
  if (status === 'inactive') return <Badge variant="secondary">Inactive</Badge>
  return <Badge variant="outline">{status}</Badge>
}

function PaymentStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'succeeded':
      return <Badge className="bg-green-600">Succeeded</Badge>
    case 'failed':
      return <Badge variant="destructive">Failed</Badge>
    case 'pending':
      return <Badge variant="outline">Pending</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}


// --- Execution History Tab ---
function ExecutionHistoryTab({ campaignId }: { campaignId: string }) {
  const { data: history = [], isLoading } = useQuery({
    queryKey: ['dunning-campaign-history', campaignId],
    queryFn: () => dunningCampaignsApi.executionHistory(campaignId),
    enabled: !!campaignId,
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    )
  }

  if (history.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
        <FileText className="h-8 w-8 mb-2" />
        <p>No payment requests generated yet</p>
      </div>
    )
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Customer</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Attempts</TableHead>
            <TableHead>Invoices</TableHead>
            <TableHead>Created</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {history.map((entry: ExecutionHistoryEntry) => (
            <TableRow key={entry.id}>
              <TableCell>
                <Link
                  to={`/admin/customers/${entry.customer_id}`}
                  className="flex items-center gap-1.5 text-primary hover:underline"
                >
                  <User className="h-3.5 w-3.5" />
                  {entry.customer_name || entry.customer_id.substring(0, 8)}
                </Link>
              </TableCell>
              <TableCell className="font-medium">
                {formatCents(entry.amount_cents, entry.amount_currency)}
              </TableCell>
              <TableCell>
                <PaymentStatusBadge status={entry.payment_status} />
              </TableCell>
              <TableCell>{entry.payment_attempts}</TableCell>
              <TableCell>
                <div className="flex flex-col gap-0.5">
                  {entry.invoices.map((inv) => (
                    <Link
                      key={inv.id}
                      to={`/admin/invoices/${inv.id}`}
                      className="text-xs text-primary hover:underline inline-flex items-center gap-1"
                    >
                      <FileText className="h-3 w-3" />
                      {inv.invoice_number}
                      <span className="text-muted-foreground">
                        ({formatCents(inv.amount_cents, inv.currency)})
                      </span>
                    </Link>
                  ))}
                  {entry.invoices.length === 0 && (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </div>
              </TableCell>
              <TableCell className="text-muted-foreground text-sm">
                {format(new Date(entry.created_at), 'MMM d, yyyy HH:mm')}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

// --- Timeline Tab ---
function TimelineTab({ campaignId }: { campaignId: string }) {
  const { data: timelineData, isLoading } = useQuery({
    queryKey: ['dunning-campaign-timeline', campaignId],
    queryFn: () => dunningCampaignsApi.timeline(campaignId),
    enabled: !!campaignId,
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    )
  }

  const events = timelineData?.events ?? []
  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
        <Clock className="h-8 w-8 mb-2" />
        <p>No timeline events</p>
      </div>
    )
  }

  return (
    <div className="border-l-2 border-border ml-1">
      {events.map((event: CampaignTimelineEvent, index: number) => {
        const dotColor =
          event.event_type === 'campaign_created'
            ? 'bg-blue-500'
            : event.event_type === 'payment_succeeded'
              ? 'bg-green-500'
              : event.event_type === 'payment_failed'
                ? 'bg-red-500'
                : event.event_type === 'payment_request_created'
                  ? 'bg-orange-500'
                  : 'bg-gray-400'

        const EventIcon =
          event.event_type === 'campaign_created'
            ? Megaphone
            : event.event_type === 'payment_succeeded'
              ? CheckCircle
              : event.event_type === 'payment_failed'
                ? XCircle
                : event.event_type === 'payment_request_created'
                  ? FileText
                  : Clock

        return (
          <div key={index} className="relative pl-6 pb-4 last:pb-0">
            <div className={`absolute left-0 top-1.5 h-2.5 w-2.5 rounded-full ${dotColor} -translate-x-[5px]`} />
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <EventIcon className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-sm font-medium">{event.description}</span>
                {event.payment_status && (
                  <PaymentStatusBadge status={event.payment_status} />
                )}
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>{format(new Date(event.timestamp), 'MMM d, yyyy HH:mm:ss')}</span>
                {event.amount_cents != null && event.amount_currency && (
                  <span className="font-medium text-foreground">
                    {formatCents(event.amount_cents, event.amount_currency)}
                  </span>
                )}
                {event.attempt_number != null && event.attempt_number > 0 && (
                  <Badge variant="outline" className="text-xs">
                    Attempt #{event.attempt_number}
                  </Badge>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// --- Preview Tab ---
function PreviewTab({ campaignId }: { campaignId: string }) {
  const queryClient = useQueryClient()
  const [hasRun, setHasRun] = useState(false)

  const previewMutation = useMutation({
    mutationFn: () => dunningCampaignsApi.preview(campaignId),
    onSuccess: () => {
      setHasRun(true)
      queryClient.invalidateQueries({ queryKey: ['dunning-campaign-preview', campaignId] })
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to run preview'
      toast.error(message)
    },
  })

  const { data: previewData } = useQuery({
    queryKey: ['dunning-campaign-preview', campaignId],
    queryFn: () => dunningCampaignsApi.preview(campaignId),
    enabled: hasRun,
  })

  const data = previewMutation.data ?? previewData

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            Simulate what this campaign would do if executed right now.
            No payment requests will be created.
          </p>
        </div>
        <Button
          onClick={() => previewMutation.mutate()}
          disabled={previewMutation.isPending}
        >
          {previewMutation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Simulating...
            </>
          ) : (
            <>
              <Play className="mr-2 h-4 w-4" />
              Run Preview
            </>
          )}
        </Button>
      </div>

      {data && (
        <div className="space-y-4">
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  Overdue Invoices
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{data.total_overdue_invoices}</div>
                <p className="text-xs text-muted-foreground">
                  {formatCents(data.total_overdue_amount_cents)} total
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5" />
                  New Requests
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-orange-600">
                  {data.payment_requests_to_create}
                </div>
                <p className="text-xs text-muted-foreground">
                  would be created
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  Existing Pending
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{data.existing_pending_requests}</div>
                <p className="text-xs text-muted-foreground">
                  already in progress
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                  <Shield className="h-3.5 w-3.5" />
                  Campaign Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                <StatusBadge status={data.status} />
              </CardContent>
            </Card>
          </div>

          {/* Groups Detail */}
          {data.groups.length > 0 ? (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Payment Requests to Create</h3>
              {data.groups.map((group: CampaignPreviewInvoiceGroup, index: number) => (
                <Card key={index}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">
                          {group.customer_name || group.customer_id.substring(0, 8)}
                        </span>
                        <Badge variant="outline">{group.currency}</Badge>
                      </div>
                      <div className="text-right">
                        <span className="font-bold text-lg">
                          {formatCents(group.total_outstanding_cents, group.currency)}
                        </span>
                        <p className="text-xs text-muted-foreground">
                          Threshold: {formatCents(group.matching_threshold_cents, group.currency)}
                        </p>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-1">
                      {group.invoices.map((inv) => (
                        <div key={inv.id} className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2">
                            <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                            <code className="text-xs bg-muted px-1 py-0.5 rounded">
                              {inv.invoice_number}
                            </code>
                            <Badge variant={inv.status === 'finalized' ? 'outline' : 'secondary'} className="text-xs">
                              {inv.status}
                            </Badge>
                          </div>
                          <span className="font-medium">
                            {formatCents(inv.amount_cents, inv.currency)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : data.total_overdue_invoices === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <CheckCircle className="h-8 w-8 mb-2 text-green-500" />
              <p className="font-medium">No overdue invoices</p>
              <p className="text-sm">All invoices are paid or not yet due</p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <CheckCircle className="h-8 w-8 mb-2 text-green-500" />
              <p className="font-medium">No new payment requests needed</p>
              <p className="text-sm">
                Overdue amounts are below thresholds or already covered by pending requests
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// --- Main Detail Page ---
export default function DunningCampaignDetailPage() {
  const { id } = useParams<{ id: string }>()

  const { data: campaign, isLoading, error } = useQuery({
    queryKey: ['dunning-campaign', id],
    queryFn: () => dunningCampaignsApi.get(id!),
    enabled: !!id,
  })

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load campaign. Please try again.</p>
      </div>
    )
  }

  if (isLoading || !campaign) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/admin/dunning-campaigns">Dunning Campaigns</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>{campaign.name}</BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/admin/dunning-campaigns">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-2xl font-bold tracking-tight">{campaign.name}</h2>
              <StatusBadge status={campaign.status} />
            </div>
            <p className="text-muted-foreground">
              <code className="text-sm bg-muted px-1.5 py-0.5 rounded">{campaign.code}</code>
              {campaign.description && (
                <span className="ml-2">{campaign.description}</span>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
              <BarChart3 className="h-3.5 w-3.5" />
              Max Attempts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{campaign.max_attempts}</div>
            <p className="text-xs text-muted-foreground">
              per payment request
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" />
              Days Between
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{campaign.days_between_attempts}</div>
            <p className="text-xs text-muted-foreground">
              between retry attempts
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
              <Mail className="h-3.5 w-3.5" />
              BCC Emails
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{campaign.bcc_emails.length}</div>
            <p className="text-xs text-muted-foreground truncate" title={campaign.bcc_emails.join(', ')}>
              {campaign.bcc_emails.length > 0 ? campaign.bcc_emails.join(', ') : 'None configured'}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
              <DollarSign className="h-3.5 w-3.5" />
              Thresholds
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{campaign.thresholds?.length ?? 0}</div>
            <div className="text-xs text-muted-foreground space-y-0.5">
              {(campaign.thresholds ?? []).map((t) => (
                <div key={t.id}>
                  {t.currency}: {formatCents(t.amount_cents, t.currency)}
                </div>
              ))}
              {(!campaign.thresholds || campaign.thresholds.length === 0) && (
                <span>No thresholds set</span>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="execution-history">
        <TabsList>
          <TabsTrigger value="execution-history">
            <FileText className="mr-1.5 h-3.5 w-3.5" />
            Execution History
          </TabsTrigger>
          <TabsTrigger value="timeline">
            <Clock className="mr-1.5 h-3.5 w-3.5" />
            Timeline
          </TabsTrigger>
          <TabsTrigger value="preview">
            <Eye className="mr-1.5 h-3.5 w-3.5" />
            Preview
          </TabsTrigger>
          <TabsTrigger value="activity">
            <BarChart3 className="mr-1.5 h-3.5 w-3.5" />
            Activity
          </TabsTrigger>
        </TabsList>

        <TabsContent value="execution-history" className="mt-4">
          <ExecutionHistoryTab campaignId={id!} />
        </TabsContent>

        <TabsContent value="timeline" className="mt-4">
          <TimelineTab campaignId={id!} />
        </TabsContent>

        <TabsContent value="preview" className="mt-4">
          <PreviewTab campaignId={id!} />
        </TabsContent>

        <TabsContent value="activity" className="mt-4">
          <AuditTrailTimeline
            resourceType="dunning_campaign"
            resourceId={id!}
            limit={20}
            showViewAll
          />
        </TabsContent>
      </Tabs>

      {/* Campaign Details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Campaign Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Created</span>
              <p className="font-medium">{format(new Date(campaign.created_at), 'MMM d, yyyy HH:mm')}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Updated</span>
              <p className="font-medium">{format(new Date(campaign.updated_at), 'MMM d, yyyy HH:mm')}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Campaign ID</span>
              <p className="font-mono text-xs">{campaign.id}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Organization ID</span>
              <p className="font-mono text-xs">{campaign.organization_id}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
