import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Hash, ArrowUp, CircleDot, Sigma, Clock, Code } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { billableMetricsApi, ApiError } from '@/lib/api'
import type { BillableMetricCreate, BillableMetricUpdate, AggregationType } from '@/lib/api'

const aggregationTypes: { value: AggregationType; label: string; description: string; icon: React.ElementType }[] = [
  { value: 'count', label: 'Count', description: 'Count total events', icon: Hash },
  { value: 'sum', label: 'Sum', description: 'Sum a numeric field', icon: ArrowUp },
  { value: 'max', label: 'Max', description: 'Maximum value of a field', icon: ArrowUp },
  { value: 'unique_count', label: 'Unique Count', description: 'Count unique values', icon: CircleDot },
  { value: 'weighted_sum', label: 'Weighted Sum', description: 'Weighted sum of a field', icon: Sigma },
  { value: 'latest', label: 'Latest', description: 'Latest value of a field', icon: Clock },
  { value: 'custom', label: 'Custom', description: 'Custom aggregation expression', icon: Code },
]

interface FormState {
  code: string
  name: string
  description: string
  aggregation_type: AggregationType
  field_name: string
  recurring: boolean
  rounding_function: string
  rounding_precision: string
  expression: string
}

const defaultFormState: FormState = {
  code: '',
  name: '',
  description: '',
  aggregation_type: 'count',
  field_name: '',
  recurring: false,
  rounding_function: '',
  rounding_precision: '',
  expression: '',
}

export default function MetricFormPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { id } = useParams<{ id: string }>()
  const isEdit = !!id

  const [form, setForm] = useState<FormState>(defaultFormState)
  const [initialized, setInitialized] = useState(false)

  const { data: metric, isLoading: loadingMetric } = useQuery({
    queryKey: ['billable-metric', id],
    queryFn: () => billableMetricsApi.get(id!),
    enabled: isEdit,
  })

  useEffect(() => {
    if (metric && !initialized) {
      setForm({
        code: metric.code,
        name: metric.name,
        description: metric.description || '',
        aggregation_type: metric.aggregation_type,
        field_name: metric.field_name || '',
        recurring: metric.recurring,
        rounding_function: metric.rounding_function || '',
        rounding_precision: metric.rounding_precision != null ? String(metric.rounding_precision) : '',
        expression: metric.expression || '',
      })
      setInitialized(true)
    }
  }, [metric, initialized])

  const createMutation = useMutation({
    mutationFn: (data: BillableMetricCreate) => billableMetricsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billable-metrics'] })
      queryClient.invalidateQueries({ queryKey: ['billable-metrics-stats'] })
      queryClient.invalidateQueries({ queryKey: ['billable-metrics-plan-counts'] })
      toast.success('Billable metric created successfully')
      navigate('/admin/metrics')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create billable metric'
      toast.error(message)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: BillableMetricUpdate }) =>
      billableMetricsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billable-metrics'] })
      queryClient.invalidateQueries({ queryKey: ['billable-metrics-stats'] })
      queryClient.invalidateQueries({ queryKey: ['billable-metrics-plan-counts'] })
      toast.success('Billable metric updated successfully')
      navigate('/admin/metrics')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update billable metric'
      toast.error(message)
    },
  })

  const needsFieldName = form.aggregation_type !== 'count'

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const roundingFunction = form.rounding_function || null
    const roundingPrecision = form.rounding_precision ? Number(form.rounding_precision) : null

    if (isEdit) {
      const data: BillableMetricUpdate = {
        name: form.name,
        description: form.description || null,
        field_name: needsFieldName ? (form.field_name || null) : null,
        recurring: form.recurring,
        rounding_function: roundingFunction as BillableMetricUpdate['rounding_function'],
        rounding_precision: roundingPrecision,
        expression: form.expression || null,
      }
      updateMutation.mutate({ id: id!, data })
    } else {
      const data: BillableMetricCreate = {
        code: form.code,
        name: form.name,
        description: form.description || undefined,
        aggregation_type: form.aggregation_type,
        field_name: needsFieldName ? (form.field_name || undefined) : undefined,
        recurring: form.recurring,
        rounding_function: roundingFunction as BillableMetricCreate['rounding_function'],
        rounding_precision: roundingPrecision,
        expression: form.expression || undefined,
      }
      createMutation.mutate(data)
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  if (isEdit && loadingMetric) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/admin/metrics')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">
            {isEdit ? 'Edit Billable Metric' : 'Create Billable Metric'}
          </h2>
          <p className="text-muted-foreground">
            {isEdit ? 'Update metric configuration.' : 'Define a new billable metric for usage tracking.'}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>The metric identifier and display name.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="code">Code *</Label>
                  <Input
                    id="code"
                    value={form.code}
                    onChange={(e) => setForm({ ...form, code: e.target.value })}
                    required
                    disabled={isEdit}
                    placeholder="api_requests"
                  />
                  <p className="text-xs text-muted-foreground">Unique identifier for this metric</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="name">Name *</Label>
                  <Input
                    id="name"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required
                    placeholder="API Requests"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Number of API calls made"
                  rows={3}
                />
              </div>
            </CardContent>
          </Card>

          {/* Aggregation */}
          <Card>
            <CardHeader>
              <CardTitle>Aggregation</CardTitle>
              <CardDescription>How usage events are aggregated for billing.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Aggregation Type *</Label>
                <Select
                  value={form.aggregation_type}
                  onValueChange={(value: AggregationType) =>
                    setForm({ ...form, aggregation_type: value })
                  }
                  disabled={isEdit}
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
                          <span className="text-muted-foreground">— {agg.description}</span>
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
                    value={form.field_name}
                    onChange={(e) => setForm({ ...form, field_name: e.target.value })}
                    placeholder="bytes_transferred"
                    required={needsFieldName}
                  />
                  <p className="text-xs text-muted-foreground">
                    The property name in event payloads to aggregate
                  </p>
                </div>
              )}

              <div className="flex items-center space-x-2">
                <Switch
                  id="recurring"
                  checked={form.recurring}
                  onCheckedChange={(checked) => setForm({ ...form, recurring: checked })}
                />
                <Label htmlFor="recurring">Recurring</Label>
              </div>
              <p className="text-xs text-muted-foreground">
                When enabled, the metric value persists across billing periods
              </p>
            </CardContent>
          </Card>

          {/* Advanced Settings */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Advanced Settings</CardTitle>
              <CardDescription>Rounding and custom expression configuration.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Rounding Function</Label>
                  <Select
                    value={form.rounding_function}
                    onValueChange={(value) => setForm({ ...form, rounding_function: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="None" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="round">Round</SelectItem>
                      <SelectItem value="ceil">Ceil</SelectItem>
                      <SelectItem value="floor">Floor</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {form.rounding_function && (
                  <div className="space-y-2">
                    <Label htmlFor="rounding_precision">Rounding Precision</Label>
                    <Input
                      id="rounding_precision"
                      type="number"
                      min={0}
                      value={form.rounding_precision}
                      onChange={(e) => setForm({ ...form, rounding_precision: e.target.value })}
                      placeholder="0"
                    />
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="expression">Expression</Label>
                <Textarea
                  id="expression"
                  value={form.expression}
                  onChange={(e) => setForm({ ...form, expression: e.target.value })}
                  placeholder="Custom aggregation expression..."
                  rows={4}
                  className="font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  Optional expression for custom aggregation logic
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-4 mt-6">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate('/admin/metrics')}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={isPending || !form.code || !form.name}>
            {isPending
              ? (isEdit ? 'Saving...' : 'Creating...')
              : (isEdit ? 'Save Changes' : 'Create Metric')}
          </Button>
        </div>
      </form>
    </div>
  )
}
