import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Plus, Trash2, Target, TrendingUp, Calendar, BarChart3, ScrollText, ToggleLeft, AlertTriangle, X, Pencil, GitBranch } from 'lucide-react'
import { toast } from 'sonner'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { AuditTrailTimeline } from '@/components/AuditTrailTimeline'
import { EditSubscriptionDialog } from '@/components/EditSubscriptionDialog'
import { SubscriptionLifecycleTimeline } from '@/components/SubscriptionLifecycleTimeline'
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
import { subscriptionsApi, customersApi, plansApi, usageThresholdsApi, usageAlertsApi, billableMetricsApi, featuresApi, ApiError } from '@/lib/api'
import type { UsageThresholdCreateAPI, UsageAlertCreate, SubscriptionUpdate } from '@/types/billing'

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(cents / 100)
}

export default function SubscriptionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [thresholdForm, setThresholdForm] = useState<UsageThresholdCreateAPI>({
    amount_cents: '',
    currency: 'USD',
    recurring: false,
    threshold_display_name: null,
  })
  const [showAlertForm, setShowAlertForm] = useState(false)
  const [alertForm, setAlertForm] = useState<{
    billable_metric_id: string
    threshold_value: string
    recurring: boolean
    name: string
  }>({ billable_metric_id: '', threshold_value: '', recurring: false, name: '' })
  const [deleteAlertId, setDeleteAlertId] = useState<string | null>(null)
  const [editOpen, setEditOpen] = useState(false)

  const { data: subscription, isLoading, error } = useQuery({
    queryKey: ['subscription', id],
    queryFn: () => subscriptionsApi.get(id!),
    enabled: !!id,
  })

  const { data: customer } = useQuery({
    queryKey: ['customer', subscription?.customer_id],
    queryFn: () => customersApi.get(subscription!.customer_id),
    enabled: !!subscription?.customer_id,
  })

  const { data: plan } = useQuery({
    queryKey: ['plan', subscription?.plan_id],
    queryFn: () => plansApi.get(subscription!.plan_id),
    enabled: !!subscription?.plan_id,
  })

  const { data: usage, isLoading: usageLoading, isError: usageError } = useQuery({
    queryKey: ['current-usage', id],
    queryFn: () => usageThresholdsApi.getCurrentUsage(id!),
    enabled: !!id,
  })

  const { data: customerUsage, isLoading: customerUsageLoading } = useQuery({
    queryKey: ['customer-usage', customer?.external_id, subscription?.external_id],
    queryFn: () => customersApi.getCurrentUsage(customer!.external_id, subscription!.external_id),
    enabled: !!customer?.external_id && !!subscription?.external_id,
  })

  const { data: thresholds, isLoading: thresholdsLoading } = useQuery({
    queryKey: ['usage-thresholds', id],
    queryFn: () => usageThresholdsApi.listForSubscription(id!),
    enabled: !!id,
  })

  const { data: entitlements, isLoading: entitlementsLoading } = useQuery({
    queryKey: ['subscription-entitlements', subscription?.external_id],
    queryFn: () => subscriptionsApi.getEntitlements(subscription!.external_id),
    enabled: !!subscription?.external_id,
  })

  const { data: features } = useQuery({
    queryKey: ['features'],
    queryFn: () => featuresApi.list(),
    enabled: !!entitlements && entitlements.length > 0,
  })

  const featureMap = new Map(features?.map((f) => [f.id, f]) ?? [])

  const { data: usageAlerts, isLoading: alertsLoading } = useQuery({
    queryKey: ['usage-alerts', id],
    queryFn: () => usageAlertsApi.list({ subscription_id: id! }),
    enabled: !!id,
  })

  const { data: allMetrics } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: () => billableMetricsApi.list(),
    enabled: !!usageAlerts && usageAlerts.length > 0 || showAlertForm,
  })

  const metricMap = new Map(allMetrics?.map((m) => [m.id, m]) ?? [])

  const updateMutation = useMutation({
    mutationFn: (data: SubscriptionUpdate) => subscriptionsApi.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription', id] })
      setEditOpen(false)
      toast.success('Subscription updated')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update subscription'
      toast.error(message)
    },
  })

  const createAlertMutation = useMutation({
    mutationFn: (data: UsageAlertCreate) => usageAlertsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-alerts', id] })
      toast.success('Usage alert created')
      setShowAlertForm(false)
      setAlertForm({ billable_metric_id: '', threshold_value: '', recurring: false, name: '' })
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create usage alert'
      toast.error(message)
    },
  })

  const deleteAlertMutation = useMutation({
    mutationFn: (alertId: string) => usageAlertsApi.delete(alertId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-alerts', id] })
      setDeleteAlertId(null)
      toast.success('Usage alert deleted')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete usage alert'
      toast.error(message)
    },
  })

  const handleCreateAlert = (e: React.FormEvent) => {
    e.preventDefault()
    createAlertMutation.mutate({
      subscription_id: id!,
      billable_metric_id: alertForm.billable_metric_id,
      threshold_value: Number(alertForm.threshold_value),
      recurring: alertForm.recurring,
      name: alertForm.name || null,
    })
  }

  const deleteMutation = useMutation({
    mutationFn: (thresholdId: string) => usageThresholdsApi.delete(thresholdId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-thresholds', id] })
      toast.success('Threshold deleted')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete threshold'
      toast.error(message)
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: UsageThresholdCreateAPI) =>
      usageThresholdsApi.createForSubscription(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-thresholds', id] })
      toast.success('Threshold created')
      setShowAddForm(false)
      setThresholdForm({ amount_cents: '', currency: 'USD', recurring: false, threshold_display_name: null })
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create threshold'
      toast.error(message)
    },
  })

  const handleCreateThreshold = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({
      ...thresholdForm,
      amount_cents: Number(thresholdForm.amount_cents),
      threshold_display_name: thresholdForm.threshold_display_name || null,
    })
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load subscription. Please try again.</p>
      </div>
    )
  }

  const customerName = customer?.name ?? 'Loading...'
  const planName = plan?.name ?? 'Loading...'

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/admin/subscriptions">Subscriptions</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>
              {isLoading ? (
                <Skeleton className="h-4 w-48 inline-block" />
              ) : (
                `${customerName} \u2014 ${planName}`
              )}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {isLoading ? (
        <div className="space-y-6">
          <div>
            <Skeleton className="h-7 w-64 mb-1" />
            <Skeleton className="h-4 w-48" />
          </div>
          <Skeleton className="h-48 w-full" />
        </div>
      ) : subscription ? (
        <>
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold tracking-tight">Subscription Details</h2>
              <p className="text-sm text-muted-foreground mt-0.5">
                {customerName} \u2014 {planName}
              </p>
            </div>
            {(subscription.status === 'active' || subscription.status === 'pending') && (
              <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                <Pencil className="mr-1 h-3.5 w-3.5" />
                Edit
              </Button>
            )}
          </div>

          {/* Subscription Info */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Subscription Information</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">External ID</span>
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{subscription.external_id}</code>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Status</span>
                  <Badge variant={subscription.status === 'active' ? 'default' : subscription.status === 'terminated' ? 'destructive' : 'secondary'}>
                    {subscription.status}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Customer</span>
                  <Link to={`/admin/customers/${subscription.customer_id}`} className="hover:underline">
                    {customerName}
                  </Link>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Plan</span>
                  <span>{planName}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Billing Time</span>
                  <span className="capitalize">{subscription.billing_time}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Pay in Advance</span>
                  <span>{subscription.pay_in_advance ? 'Yes' : 'No'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">On Termination</span>
                  <span className="capitalize">{subscription.on_termination_action.replace(/_/g, ' ')}</span>
                </div>
                {subscription.trial_period_days > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Trial Period</span>
                    <span>{subscription.trial_period_days} days</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Started At</span>
                  <span>{subscription.started_at ? format(new Date(subscription.started_at), 'MMM d, yyyy HH:mm') : '\u2014'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Created</span>
                  <span>{format(new Date(subscription.created_at), 'MMM d, yyyy HH:mm')}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Lifecycle Timeline */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <GitBranch className="h-4 w-4" />
                Lifecycle Timeline
              </CardTitle>
            </CardHeader>
            <CardContent>
              <SubscriptionLifecycleTimeline subscriptionId={id!} />
            </CardContent>
          </Card>

          {/* Current Usage */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <TrendingUp className="h-4 w-4" />
                Current Usage
              </CardTitle>
            </CardHeader>
            <CardContent>
              {usageLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-8 w-32" />
                  <Skeleton className="h-4 w-48" />
                </div>
              ) : usageError || !usage ? (
                <p className="text-sm text-muted-foreground">No usage data available</p>
              ) : (
                <div className="space-y-2">
                  <p className="text-3xl font-semibold font-mono">
                    {formatCurrency(parseInt(usage.current_usage_amount_cents))}
                  </p>
                  <p className="text-sm text-muted-foreground flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    Billing Period: {format(new Date(usage.billing_period_start), 'MMM d, yyyy')} \u2014 {format(new Date(usage.billing_period_end), 'MMM d, yyyy')}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Per-Metric Usage Breakdown */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Usage Breakdown
                </CardTitle>
                {customer && (
                  <Link
                    to={`/admin/customers/${subscription.customer_id}?tab=usage`}
                    className="text-sm text-primary hover:underline"
                  >
                    View Full Usage
                  </Link>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {customerUsageLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : !customerUsage?.charges?.length ? (
                <p className="text-sm text-muted-foreground">No per-metric usage data available</p>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Metric</TableHead>
                        <TableHead>Units</TableHead>
                        <TableHead>Amount</TableHead>
                        <TableHead>Charge Model</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {customerUsage.charges.map((charge, idx) => (
                        <TableRow key={`${charge.billable_metric.code}-${idx}`}>
                          <TableCell>
                            <div>{charge.billable_metric.name}</div>
                            <div className="text-xs text-muted-foreground">{charge.billable_metric.code}</div>
                          </TableCell>
                          <TableCell className="font-mono">{charge.units}</TableCell>
                          <TableCell className="font-mono">
                            {formatCurrency(Number(charge.amount_cents), customerUsage.currency)}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{charge.charge_model}</Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          <Separator />

          {/* Usage Thresholds */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium flex items-center gap-2">
                <Target className="h-4 w-4" />
                Usage Thresholds
              </h3>
              {!showAddForm && (
                <Button size="sm" variant="outline" onClick={() => setShowAddForm(true)}>
                  <Plus className="mr-1 h-3 w-3" />
                  Add Threshold
                </Button>
              )}
            </div>

            {thresholdsLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : !thresholds || thresholds.length === 0 ? (
              <p className="text-sm text-muted-foreground">No usage thresholds configured</p>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Amount</TableHead>
                      <TableHead>Recurring</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead className="w-[40px]"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {thresholds.map((t) => (
                      <TableRow key={t.id}>
                        <TableCell className="font-mono">
                          {formatCurrency(parseInt(t.amount_cents), t.currency)}
                        </TableCell>
                        <TableCell>
                          <Badge variant={t.recurring ? 'default' : 'secondary'}>
                            {t.recurring ? 'Yes' : 'No'}
                          </Badge>
                        </TableCell>
                        <TableCell>{t.threshold_display_name ?? '\u2014'}</TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => deleteMutation.mutate(t.id)}
                            disabled={deleteMutation.isPending}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            {/* Add Threshold Form */}
            {showAddForm && (
              <form onSubmit={handleCreateThreshold} className="space-y-3 rounded-md border p-4">
                <div className="space-y-2">
                  <Label htmlFor="threshold_amount">Amount (cents) *</Label>
                  <Input
                    id="threshold_amount"
                    type="number"
                    value={thresholdForm.amount_cents}
                    onChange={(e) => setThresholdForm({ ...thresholdForm, amount_cents: e.target.value })}
                    placeholder="10000"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Currency</Label>
                  <Select
                    value={thresholdForm.currency}
                    onValueChange={(value) => setThresholdForm({ ...thresholdForm, currency: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="USD">USD</SelectItem>
                      <SelectItem value="EUR">EUR</SelectItem>
                      <SelectItem value="GBP">GBP</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="threshold_recurring"
                    checked={thresholdForm.recurring}
                    onCheckedChange={(checked) =>
                      setThresholdForm({ ...thresholdForm, recurring: checked === true })
                    }
                  />
                  <Label htmlFor="threshold_recurring">Recurring</Label>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="threshold_name">Display Name</Label>
                  <Input
                    id="threshold_name"
                    value={thresholdForm.threshold_display_name ?? ''}
                    onChange={(e) => setThresholdForm({ ...thresholdForm, threshold_display_name: e.target.value })}
                    placeholder="Optional display name"
                  />
                </div>
                <div className="flex gap-2">
                  <Button type="submit" size="sm" disabled={createMutation.isPending}>
                    {createMutation.isPending ? 'Creating...' : 'Create'}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setShowAddForm(false)
                      setThresholdForm({ amount_cents: '', currency: 'USD', recurring: false, threshold_display_name: null })
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}
          </div>

          <Separator />

          {/* Usage Alerts */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  Usage Alerts
                </CardTitle>
                {!showAlertForm && (
                  <Button size="sm" variant="outline" onClick={() => setShowAlertForm(true)}>
                    <Plus className="mr-1 h-3 w-3" />
                    Add Alert
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {alertsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : !usageAlerts?.length && !showAlertForm ? (
                <div className="text-center py-4">
                  <p className="text-sm text-muted-foreground mb-2">No usage alerts configured</p>
                  <Button size="sm" variant="outline" onClick={() => setShowAlertForm(true)}>
                    <Plus className="mr-1 h-3 w-3" />
                    Create Alert
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {usageAlerts?.map((alert) => {
                    const metric = metricMap.get(alert.billable_metric_id)
                    return (
                      <div key={alert.id} className="flex items-center justify-between rounded-md border px-3 py-2">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">
                              {alert.name || metric?.name || 'Unnamed alert'}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              Threshold: <span className="font-mono">{Number(alert.threshold_value).toLocaleString()}</span>
                              {' \u00b7 '}
                              <Badge variant={alert.recurring ? 'default' : 'secondary'} className="text-[10px] px-1 py-0">
                                {alert.recurring ? 'Recurring' : 'One-time'}
                              </Badge>
                              {alert.triggered_at && (
                                <>
                                  {' \u00b7 Last triggered: '}
                                  {format(new Date(alert.triggered_at), 'MMM d, yyyy HH:mm')}
                                </>
                              )}
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="shrink-0"
                          onClick={() => setDeleteAlertId(alert.id)}
                        >
                          <X className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Add Alert Form */}
              {showAlertForm && (
                <form onSubmit={handleCreateAlert} className="space-y-3 rounded-md border p-4 mt-3">
                  <div className="space-y-2">
                    <Label htmlFor="alert_metric">Billable Metric *</Label>
                    <Select
                      value={alertForm.billable_metric_id}
                      onValueChange={(value) => setAlertForm({ ...alertForm, billable_metric_id: value })}
                    >
                      <SelectTrigger id="alert_metric">
                        <SelectValue placeholder="Select a metric" />
                      </SelectTrigger>
                      <SelectContent>
                        {allMetrics?.map((metric) => (
                          <SelectItem key={metric.id} value={metric.id}>
                            {metric.name} ({metric.code})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="alert_threshold">Threshold Value *</Label>
                    <Input
                      id="alert_threshold"
                      type="number"
                      value={alertForm.threshold_value}
                      onChange={(e) => setAlertForm({ ...alertForm, threshold_value: e.target.value })}
                      placeholder="e.g. 1000"
                      required
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="alert_recurring"
                      checked={alertForm.recurring}
                      onCheckedChange={(checked) =>
                        setAlertForm({ ...alertForm, recurring: checked === true })
                      }
                    />
                    <Label htmlFor="alert_recurring">Recurring</Label>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="alert_name">Name</Label>
                    <Input
                      id="alert_name"
                      value={alertForm.name}
                      onChange={(e) => setAlertForm({ ...alertForm, name: e.target.value })}
                      placeholder="Optional alert name"
                    />
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="submit"
                      size="sm"
                      disabled={createAlertMutation.isPending || !alertForm.billable_metric_id || !alertForm.threshold_value}
                    >
                      {createAlertMutation.isPending ? 'Creating...' : 'Create'}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setShowAlertForm(false)
                        setAlertForm({ billable_metric_id: '', threshold_value: '', recurring: false, name: '' })
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>

          {/* Delete Alert Confirmation */}
          <AlertDialog
            open={!!deleteAlertId}
            onOpenChange={(open) => !open && setDeleteAlertId(null)}
          >
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Usage Alert</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete this usage alert? This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => deleteAlertId && deleteAlertMutation.mutate(deleteAlertId)}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {deleteAlertMutation.isPending ? 'Deleting...' : 'Delete'}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>

          <Separator />

          {/* Entitlements */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <ToggleLeft className="h-4 w-4" />
                  Entitlements
                </CardTitle>
                <Link
                  to="/admin/features"
                  className="text-sm text-primary hover:underline"
                >
                  Manage Features
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {entitlementsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : !entitlements?.length ? (
                <p className="text-sm text-muted-foreground">No features configured for this plan.</p>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Feature</TableHead>
                        <TableHead>Code</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Value</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {entitlements.map((entitlement) => {
                        const feature = featureMap.get(entitlement.feature_id)
                        return (
                          <TableRow key={entitlement.id}>
                            <TableCell className="font-medium">{feature?.name ?? 'Unknown'}</TableCell>
                            <TableCell>
                              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                {feature?.code ?? entitlement.feature_id}
                              </code>
                            </TableCell>
                            <TableCell>
                              {feature ? (
                                <Badge variant={feature.feature_type === 'boolean' ? 'default' : feature.feature_type === 'quantity' ? 'secondary' : 'outline'}>
                                  {feature.feature_type}
                                </Badge>
                              ) : (
                                '\u2014'
                              )}
                            </TableCell>
                            <TableCell>
                              {feature?.feature_type === 'boolean'
                                ? entitlement.value === 'true' ? 'Enabled' : 'Disabled'
                                : entitlement.value}
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          <Separator />

          {/* Activity Log */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <ScrollText className="h-4 w-4" />
                Activity Log
              </CardTitle>
            </CardHeader>
            <CardContent>
              <AuditTrailTimeline
                resourceType="subscription"
                resourceId={id!}
                limit={20}
                showViewAll
              />
            </CardContent>
          </Card>

          {/* Edit Subscription Dialog */}
          <EditSubscriptionDialog
            open={editOpen}
            onOpenChange={setEditOpen}
            subscription={subscription}
            onSubmit={(data) => updateMutation.mutate(data)}
            isLoading={updateMutation.isPending}
          />
        </>
      ) : null}
    </div>
  )
}
