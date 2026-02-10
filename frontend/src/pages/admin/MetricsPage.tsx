import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, MoreHorizontal, Pencil, Trash2, Code, Hash, ArrowUp, CircleDot } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { billableMetricsApi, ApiError } from '@/lib/api'
import type { BillableMetric, BillableMetricCreate, BillableMetricUpdate, AggregationType } from '@/types/billing'

const aggregationTypes: { value: AggregationType; label: string; description: string; icon: React.ElementType }[] = [
  { value: 'count', label: 'Count', description: 'Count total events', icon: Hash },
  { value: 'sum', label: 'Sum', description: 'Sum a numeric field', icon: ArrowUp },
  { value: 'max', label: 'Max', description: 'Maximum value of a field', icon: ArrowUp },
  { value: 'unique_count', label: 'Unique Count', description: 'Count unique values', icon: CircleDot },
]

function AggregationBadge({ type }: { type: AggregationType }) {
  const config = aggregationTypes.find((a) => a.value === type)
  const Icon = config?.icon ?? Hash

  const colorClass = {
    count: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
    sum: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
    max: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300',
    unique_count: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
  }[type]

  return (
    <Badge variant="outline" className={colorClass}>
      <Icon className="mr-1 h-3 w-3" />
      {config?.label ?? type}
    </Badge>
  )
}

function MetricFormDialog({
  open,
  onOpenChange,
  metric,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  metric?: BillableMetric | null
  onSubmit: (data: BillableMetricCreate | BillableMetricUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<BillableMetricCreate>({
    code: metric?.code ?? '',
    name: metric?.name ?? '',
    description: metric?.description ?? undefined,
    aggregation_type: metric?.aggregation_type ?? 'count',
    field_name: metric?.field_name ?? undefined,
  })

  const needsFieldName = formData.aggregation_type !== 'count'

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      ...formData,
      field_name: needsFieldName ? formData.field_name : null,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {metric ? 'Edit Billable Metric' : 'Create Billable Metric'}
            </DialogTitle>
            <DialogDescription>
              {metric
                ? 'Update metric configuration'
                : 'Define a new billable metric for usage tracking'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="code">Code *</Label>
                <Input
                  id="code"
                  value={formData.code}
                  onChange={(e) =>
                    setFormData({ ...formData, code: e.target.value })
                  }
                  placeholder="api_requests"
                  required
                  disabled={!!metric}
                />
                <p className="text-xs text-muted-foreground">
                  Unique identifier for this metric
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="API Requests"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={formData.description ?? ''}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value || undefined })
                }
                placeholder="Number of API calls made"
              />
            </div>

            <div className="space-y-2">
              <Label>Aggregation Type *</Label>
              <Select
                value={formData.aggregation_type}
                onValueChange={(value: AggregationType) =>
                  setFormData({ ...formData, aggregation_type: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {aggregationTypes.map((agg) => (
                    <SelectItem key={agg.value} value={agg.value}>
                      <div className="flex items-center gap-2">
                        <agg.icon className="h-4 w-4" />
                        <span>{agg.label}</span>
                        <span className="text-muted-foreground">
                          — {agg.description}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {needsFieldName && (
              <div className="space-y-2">
                <Label htmlFor="field_name">Field Name *</Label>
                <Input
                  id="field_name"
                  value={formData.field_name ?? ''}
                  onChange={(e) =>
                    setFormData({ ...formData, field_name: e.target.value || undefined })
                  }
                  placeholder="bytes_transferred"
                  required={needsFieldName}
                />
                <p className="text-xs text-muted-foreground">
                  The property name in event payloads to aggregate
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Saving...' : metric ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function MetricsPage() {
  const queryClient = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editingMetric, setEditingMetric] = useState<BillableMetric | null>(null)
  const [deleteMetric, setDeleteMetric] = useState<BillableMetric | null>(null)

  // Fetch metrics from API
  const { data: metrics, isLoading, error } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: () => billableMetricsApi.list(),
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: BillableMetricCreate) => billableMetricsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billable-metrics'] })
      setFormOpen(false)
      toast.success('Billable metric created successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create billable metric'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: BillableMetricUpdate }) =>
      billableMetricsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billable-metrics'] })
      setEditingMetric(null)
      setFormOpen(false)
      toast.success('Billable metric updated successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update billable metric'
      toast.error(message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => billableMetricsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billable-metrics'] })
      setDeleteMetric(null)
      toast.success('Billable metric deleted successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete billable metric'
      toast.error(message)
    },
  })

  const handleSubmit = (data: BillableMetricCreate | BillableMetricUpdate) => {
    if (editingMetric) {
      updateMutation.mutate({ id: editingMetric.id, data })
    } else {
      createMutation.mutate(data as BillableMetricCreate)
    }
  }

  const handleEdit = (metric: BillableMetric) => {
    setEditingMetric(metric)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingMetric(null)
    }
    setFormOpen(open)
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load billable metrics. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Billable Metrics</h2>
          <p className="text-muted-foreground">
            Define how usage events are aggregated for billing
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Metric
        </Button>
      </div>

      {/* Metrics Grid */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-48" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-6 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : !metrics || metrics.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Code className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No billable metrics</h3>
            <p className="text-muted-foreground text-center max-w-sm mt-1">
              Create your first billable metric to start tracking usage
            </p>
            <Button onClick={() => setFormOpen(true)} className="mt-4">
              <Plus className="mr-2 h-4 w-4" />
              Create Metric
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {metrics.map((metric) => (
            <Card key={metric.id}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-base">{metric.name}</CardTitle>
                    <code className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                      {metric.code}
                    </code>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleEdit(metric)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => setDeleteMetric(metric)}
                        className="text-destructive"
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                {metric.description && (
                  <CardDescription>{metric.description}</CardDescription>
                )}
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <AggregationBadge type={metric.aggregation_type} />
                  {metric.field_name && (
                    <Badge variant="secondary">
                      <Code className="mr-1 h-3 w-3" />
                      {metric.field_name}
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Dialog */}
      <MetricFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        metric={editingMetric}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteMetric}
        onOpenChange={(open) => !open && setDeleteMetric(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Billable Metric</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deleteMetric?.name}"? This will
              affect any plans using this metric.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMetric && deleteMutation.mutate(deleteMetric.id)}
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
