import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Plus, Trash2, Target, TrendingUp, Calendar, BarChart3, ScrollText } from 'lucide-react'
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
import { subscriptionsApi, customersApi, plansApi, usageThresholdsApi, ApiError } from '@/lib/api'
import type { UsageThresholdCreateAPI } from '@/types/billing'

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
          <div>
            <h2 className="text-xl font-semibold tracking-tight">Subscription Details</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              {customerName} \u2014 {planName}
            </p>
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
        </>
      ) : null}
    </div>
  )
}
