import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, MoreHorizontal, Pencil, Trash2, Code, Hash, ArrowUp, CircleDot, Clock } from 'lucide-react'
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { BillableMetric, BillableMetricCreate, BillableMetricUpdate, AggregationType } from '@/types/billing'

// Mock data
const mockMetrics: BillableMetric[] = [
  {
    id: '1',
    code: 'api_requests',
    name: 'API Requests',
    description: 'Number of API calls made',
    aggregation_type: 'count',
    field_name: null,
    recurring: false,
    created_at: '2024-01-10T10:00:00Z',
    updated_at: '2024-01-10T10:00:00Z',
  },
  {
    id: '2',
    code: 'storage_gb',
    name: 'Storage Usage',
    description: 'Total storage used in gigabytes',
    aggregation_type: 'max',
    field_name: 'gb_used',
    recurring: true,
    created_at: '2024-01-12T14:30:00Z',
    updated_at: '2024-01-12T14:30:00Z',
  },
  {
    id: '3',
    code: 'active_users',
    name: 'Active Users',
    description: 'Unique active users in the billing period',
    aggregation_type: 'unique_count',
    field_name: 'user_id',
    recurring: false,
    created_at: '2024-01-15T09:00:00Z',
    updated_at: '2024-01-15T09:00:00Z',
  },
  {
    id: '4',
    code: 'bandwidth_gb',
    name: 'Bandwidth',
    description: 'Total bandwidth consumed in GB',
    aggregation_type: 'sum',
    field_name: 'bytes_transferred',
    recurring: false,
    created_at: '2024-01-20T11:00:00Z',
    updated_at: '2024-01-20T11:00:00Z',
  },
]

const aggregationTypes: { value: AggregationType; label: string; description: string; icon: React.ElementType }[] = [
  { value: 'count', label: 'Count', description: 'Count total events', icon: Hash },
  { value: 'sum', label: 'Sum', description: 'Sum a numeric field', icon: ArrowUp },
  { value: 'max', label: 'Max', description: 'Maximum value of a field', icon: ArrowUp },
  { value: 'unique_count', label: 'Unique Count', description: 'Count unique values', icon: CircleDot },
  { value: 'latest', label: 'Latest', description: 'Most recent value', icon: Clock },
]

function AggregationBadge({ type }: { type: AggregationType }) {
  const config = aggregationTypes.find((a) => a.value === type)
  const Icon = config?.icon ?? Hash

  const colorClass = {
    count: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
    sum: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
    max: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300',
    unique_count: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
    latest: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300',
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
    description: metric?.description ?? '',
    aggregation_type: metric?.aggregation_type ?? 'count',
    field_name: metric?.field_name ?? '',
    recurring: metric?.recurring ?? false,
  })

  const needsFieldName = formData.aggregation_type !== 'count'

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const data = {
      ...formData,
      field_name: needsFieldName ? formData.field_name : null,
    }
    onSubmit(data)
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
                  setFormData({ ...formData, description: e.target.value })
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
                    setFormData({ ...formData, field_name: e.target.value })
                  }
                  placeholder="bytes_transferred"
                  required={needsFieldName}
                />
                <p className="text-xs text-muted-foreground">
                  The property name in event payloads to aggregate
                </p>
              </div>
            )}

            <div className="flex items-center space-x-2">
              <Checkbox
                id="recurring"
                checked={formData.recurring}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, recurring: checked as boolean })
                }
              />
              <div className="grid gap-1.5 leading-none">
                <Label htmlFor="recurring">Recurring metric</Label>
                <p className="text-xs text-muted-foreground">
                  Value persists across billing periods (e.g., storage)
                </p>
              </div>
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

  // Fetch metrics
  const { data, isLoading } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: async () => {
      // TODO: Replace with actual API call
      // return billableMetricsApi.list()
      await new Promise((r) => setTimeout(r, 500))
      return {
        data: mockMetrics,
        meta: { total: mockMetrics.length, page: 1, per_page: 10, total_pages: 1 },
      }
    },
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: async (data: BillableMetricCreate) => {
      await new Promise((r) => setTimeout(r, 500))
      return { ...data, id: String(Date.now()) } as BillableMetric
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billable-metrics'] })
      setFormOpen(false)
      toast.success('Billable metric created successfully')
    },
    onError: () => {
      toast.error('Failed to create billable metric')
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async ({
      code,
      data,
    }: {
      code: string
      data: BillableMetricUpdate
    }) => {
      await new Promise((r) => setTimeout(r, 500))
      return { code, ...data } as BillableMetric
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billable-metrics'] })
      setEditingMetric(null)
      setFormOpen(false)
      toast.success('Billable metric updated successfully')
    },
    onError: () => {
      toast.error('Failed to update billable metric')
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (code: string) => {
      await new Promise((r) => setTimeout(r, 500))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billable-metrics'] })
      setDeleteMetric(null)
      toast.success('Billable metric deleted successfully')
    },
    onError: () => {
      toast.error('Failed to delete billable metric')
    },
  })

  const handleSubmit = (data: BillableMetricCreate | BillableMetricUpdate) => {
    if (editingMetric) {
      updateMutation.mutate({ code: editingMetric.code, data })
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

      {/* Metrics Grid/Table */}
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
      ) : data?.data.length === 0 ? (
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
          {data?.data.map((metric) => (
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
                  {metric.recurring && (
                    <Badge variant="outline">Recurring</Badge>
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
              onClick={() =>
                deleteMetric && deleteMutation.mutate(deleteMetric.code)
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
