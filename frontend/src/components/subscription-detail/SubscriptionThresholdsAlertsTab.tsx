import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Plus, Trash2, Target, AlertTriangle, X } from 'lucide-react'
import { toast } from 'sonner'

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
import { usageThresholdsApi, usageAlertsApi, billableMetricsApi, ApiError } from '@/lib/api'
import { formatCents } from '@/lib/utils'
import type { UsageThresholdCreateAPI, UsageAlertCreate } from '@/types/billing'

interface SubscriptionThresholdsAlertsTabProps {
  subscriptionId: string
}

export function SubscriptionThresholdsAlertsTab({
  subscriptionId,
}: SubscriptionThresholdsAlertsTabProps) {
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

  const { data: thresholds, isLoading: thresholdsLoading } = useQuery({
    queryKey: ['usage-thresholds', subscriptionId],
    queryFn: () => usageThresholdsApi.listForSubscription(subscriptionId),
    enabled: !!subscriptionId,
  })

  const { data: usageAlerts, isLoading: alertsLoading } = useQuery({
    queryKey: ['usage-alerts', subscriptionId],
    queryFn: () => usageAlertsApi.list({ subscription_id: subscriptionId }),
    enabled: !!subscriptionId,
  })

  const { data: allMetrics } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: () => billableMetricsApi.list(),
    enabled: !!usageAlerts && usageAlerts.length > 0 || showAlertForm,
  })

  const metricMap = new Map(allMetrics?.map((m) => [m.id, m]) ?? [])

  const createMutation = useMutation({
    mutationFn: (data: UsageThresholdCreateAPI) =>
      usageThresholdsApi.createForSubscription(subscriptionId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-thresholds', subscriptionId] })
      toast.success('Threshold created')
      setShowAddForm(false)
      setThresholdForm({ amount_cents: '', currency: 'USD', recurring: false, threshold_display_name: null })
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create threshold'
      toast.error(message)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (thresholdId: string) => usageThresholdsApi.delete(thresholdId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-thresholds', subscriptionId] })
      toast.success('Threshold deleted')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete threshold'
      toast.error(message)
    },
  })

  const createAlertMutation = useMutation({
    mutationFn: (data: UsageAlertCreate) => usageAlertsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-alerts', subscriptionId] })
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
      queryClient.invalidateQueries({ queryKey: ['usage-alerts', subscriptionId] })
      setDeleteAlertId(null)
      toast.success('Usage alert deleted')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete usage alert'
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

  const handleCreateAlert = (e: React.FormEvent) => {
    e.preventDefault()
    createAlertMutation.mutate({
      subscription_id: subscriptionId,
      billable_metric_id: alertForm.billable_metric_id,
      threshold_value: Number(alertForm.threshold_value),
      recurring: alertForm.recurring,
      name: alertForm.name || null,
    })
  }

  return (
    <>
      <div className="space-y-6">
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
                    <TableHead className="hidden md:table-cell">Name</TableHead>
                    <TableHead className="w-[40px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {thresholds.map((t) => (
                    <TableRow key={t.id}>
                      <TableCell className="font-mono">
                        {formatCents(parseInt(t.amount_cents), t.currency)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={t.recurring ? 'default' : 'secondary'}>
                          {t.recurring ? 'Yes' : 'No'}
                        </Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">{t.threshold_display_name ?? '\u2014'}</TableCell>
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
      </div>

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
    </>
  )
}
