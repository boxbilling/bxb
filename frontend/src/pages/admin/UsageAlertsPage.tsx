import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  MoreHorizontal,
  Pencil,
  Trash2,
  AlertTriangle,
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
import { Checkbox } from '@/components/ui/checkbox'
import { usageAlertsApi, subscriptionsApi, billableMetricsApi, ApiError } from '@/lib/api'
import type { UsageAlert, UsageAlertCreate, UsageAlertUpdate } from '@/types/billing'

function UsageAlertFormDialog({
  open,
  onOpenChange,
  alert,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  alert?: UsageAlert | null
  onSubmit: (data: UsageAlertCreate | UsageAlertUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<{
    subscription_id: string
    billable_metric_id: string
    threshold_value: string
    recurring: boolean
    name: string
  }>({
    subscription_id: alert?.subscription_id ?? '',
    billable_metric_id: alert?.billable_metric_id ?? '',
    threshold_value: alert?.threshold_value ?? '',
    recurring: alert?.recurring ?? false,
    name: alert?.name ?? '',
  })

  const { data: subscriptions = [] } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => subscriptionsApi.list(),
  })

  const { data: metrics = [] } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: () => billableMetricsApi.list(),
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (alert) {
      const update: UsageAlertUpdate = {
        threshold_value: Number(formData.threshold_value),
        name: formData.name || null,
        recurring: formData.recurring,
      }
      onSubmit(update)
    } else {
      const create: UsageAlertCreate = {
        subscription_id: formData.subscription_id,
        billable_metric_id: formData.billable_metric_id,
        threshold_value: Number(formData.threshold_value),
        recurring: formData.recurring,
        name: formData.name || null,
      }
      onSubmit(create)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {alert ? 'Edit Usage Alert' : 'Create Alert'}
            </DialogTitle>
            <DialogDescription>
              {alert
                ? 'Update usage alert settings'
                : 'Create a new usage monitoring alert for a subscription'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="subscription_id">Subscription *</Label>
              <Select
                value={formData.subscription_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, subscription_id: value })
                }
                disabled={!!alert}
              >
                <SelectTrigger id="subscription_id">
                  <SelectValue placeholder="Select a subscription" />
                </SelectTrigger>
                <SelectContent>
                  {subscriptions.map((sub) => (
                    <SelectItem key={sub.id} value={sub.id}>
                      {sub.external_id} ({sub.id.slice(0, 8)}...)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="billable_metric_id">Billable Metric *</Label>
              <Select
                value={formData.billable_metric_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, billable_metric_id: value })
                }
                disabled={!!alert}
              >
                <SelectTrigger id="billable_metric_id">
                  <SelectValue placeholder="Select a metric" />
                </SelectTrigger>
                <SelectContent>
                  {metrics.map((metric) => (
                    <SelectItem key={metric.id} value={metric.id}>
                      {metric.name} ({metric.code})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="threshold_value">Threshold Value *</Label>
              <Input
                id="threshold_value"
                type="number"
                value={formData.threshold_value}
                onChange={(e) =>
                  setFormData({ ...formData, threshold_value: e.target.value })
                }
                placeholder="e.g. 1000"
                required
              />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="recurring"
                checked={formData.recurring}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, recurring: checked === true })
                }
              />
              <Label htmlFor="recurring">Recurring</Label>
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="Optional alert name"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={
                isLoading ||
                (!alert &&
                  (!formData.subscription_id ||
                    !formData.billable_metric_id ||
                    !formData.threshold_value))
              }
            >
              {isLoading
                ? 'Saving...'
                : alert
                  ? 'Update'
                  : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function UsageAlertsPage() {
  const queryClient = useQueryClient()
  const [subscriptionFilter, setSubscriptionFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)
  const [editingAlert, setEditingAlert] = useState<UsageAlert | null>(null)
  const [deleteAlert, setDeleteAlert] = useState<UsageAlert | null>(null)

  const {
    data: alerts = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['usage-alerts'],
    queryFn: () => usageAlertsApi.list(),
  })

  const { data: subscriptions = [] } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => subscriptionsApi.list(),
  })

  const { data: metrics = [] } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: () => billableMetricsApi.list(),
  })

  const metricMap = new Map(metrics.map((m) => [m.id, m]))

  const filteredAlerts = alerts.filter((a) => {
    return (
      subscriptionFilter === 'all' ||
      a.subscription_id === subscriptionFilter
    )
  })

  const createMutation = useMutation({
    mutationFn: (data: UsageAlertCreate) => usageAlertsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-alerts'] })
      setFormOpen(false)
      toast.success('Usage alert created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to create usage alert'
      toast.error(message)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UsageAlertUpdate }) =>
      usageAlertsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-alerts'] })
      setEditingAlert(null)
      setFormOpen(false)
      toast.success('Usage alert updated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to update usage alert'
      toast.error(message)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => usageAlertsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-alerts'] })
      setDeleteAlert(null)
      toast.success('Usage alert deleted successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to delete usage alert'
      toast.error(message)
    },
  })

  const handleSubmit = (data: UsageAlertCreate | UsageAlertUpdate) => {
    if (editingAlert) {
      updateMutation.mutate({
        id: editingAlert.id,
        data: data as UsageAlertUpdate,
      })
    } else {
      createMutation.mutate(data as UsageAlertCreate)
    }
  }

  const handleEdit = (alert: UsageAlert) => {
    setEditingAlert(alert)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingAlert(null)
    }
    setFormOpen(open)
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load usage alerts. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Usage Alerts</h2>
          <p className="text-muted-foreground">
            Monitor usage thresholds for subscription metrics
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Alert
        </Button>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-4">
        <Select value={subscriptionFilter} onValueChange={setSubscriptionFilter}>
          <SelectTrigger className="w-[280px]">
            <SelectValue placeholder="Filter by subscription" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Subscriptions</SelectItem>
            {subscriptions.map((sub) => (
              <SelectItem key={sub.id} value={sub.id}>
                {sub.external_id} ({sub.id.slice(0, 8)}...)
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Subscription</TableHead>
              <TableHead>Metric</TableHead>
              <TableHead>Threshold</TableHead>
              <TableHead>Recurring</TableHead>
              <TableHead>Last Triggered</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : filteredAlerts.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="h-24 text-center text-muted-foreground"
                >
                  <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No usage alerts found
                </TableCell>
              </TableRow>
            ) : (
              filteredAlerts.map((alert) => {
                const metric = metricMap.get(alert.billable_metric_id)
                return (
                  <TableRow key={alert.id}>
                    <TableCell className="font-medium">
                      {alert.name || 'Unnamed'}
                    </TableCell>
                    <TableCell>
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                        {alert.subscription_id.slice(0, 8)}...
                      </code>
                    </TableCell>
                    <TableCell>
                      {metric?.name ?? alert.billable_metric_id.slice(0, 8) + '...'}
                    </TableCell>
                    <TableCell className="font-mono">
                      {Number(alert.threshold_value).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant={alert.recurring ? 'default' : 'secondary'}>
                        {alert.recurring ? 'Yes' : 'No'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {alert.triggered_at
                        ? format(new Date(alert.triggered_at), 'MMM d, yyyy HH:mm')
                        : 'Never'}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleEdit(alert)}>
                            <Pencil className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => setDeleteAlert(alert)}
                            className="text-destructive"
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create/Edit Dialog */}
      <UsageAlertFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        alert={editingAlert}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteAlert}
        onOpenChange={(open) => !open && setDeleteAlert(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-destructive" />
                Delete Usage Alert
              </div>
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this usage alert
              {deleteAlert?.name ? ` "${deleteAlert.name}"` : ''}? This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteAlert && deleteMutation.mutate(deleteAlert.id)
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
