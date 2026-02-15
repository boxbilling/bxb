import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import {
  Plus,
  Pencil,
  Trash2,
  Target,
  ScrollText,
  ToggleLeft,
  Users,
  Copy,
  Calendar,
  Layers,
} from 'lucide-react'
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
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
import { AuditTrailTimeline } from '@/components/AuditTrailTimeline'
import {
  plansApi,
  billableMetricsApi,
  commitmentsApi,
  usageThresholdsApi,
  entitlementsApi,
  featuresApi,
  subscriptionsApi,
  customersApi,
  ApiError,
} from '@/lib/api'
import type {
  Plan,
  PlanCreate,
  PlanUpdate,
  ChargeModel,
  ChargeInput,
  BillableMetric,
  Commitment,
  CommitmentCreateAPI,
  CommitmentUpdate,
  UsageThreshold,
  UsageThresholdCreateAPI,
  Entitlement,
  Feature,
  Subscription,
  Customer,
} from '@/types/billing'

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}

function intervalLabel(interval: string) {
  return (
    {
      weekly: 'week',
      monthly: 'month',
      quarterly: 'quarter',
      yearly: 'year',
    }[interval] ?? interval
  )
}

function ChargeModelBadge({ model }: { model: ChargeModel }) {
  const colors: Record<string, string> = {
    standard: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
    graduated:
      'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
    volume: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
    package:
      'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300',
    percentage:
      'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-300',
  }

  return (
    <Badge variant="outline" className={colors[model] ?? ''}>
      {model}
    </Badge>
  )
}

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === 'active'
      ? 'default'
      : status === 'terminated'
        ? 'destructive'
        : 'secondary'
  return <Badge variant={variant}>{status}</Badge>
}

export default function PlanDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Commitments state
  const [showAddCommitment, setShowAddCommitment] = useState(false)
  const [editingCommitment, setEditingCommitment] = useState<Commitment | null>(
    null
  )
  const [deleteCommitment, setDeleteCommitment] = useState<Commitment | null>(
    null
  )
  const [commitmentForm, setCommitmentForm] = useState({
    commitment_type: 'minimum_commitment',
    amount_cents: '',
    invoice_display_name: '',
  })

  // Usage threshold state
  const [thresholdForm, setThresholdForm] = useState({
    amount_cents: '',
    currency: 'USD',
    recurring: false,
    threshold_display_name: '',
  })
  const [deleteThreshold, setDeleteThreshold] = useState<UsageThreshold | null>(
    null
  )

  // Fetch plan
  const {
    data: plan,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['plan', id],
    queryFn: () => plansApi.get(id!),
    enabled: !!id,
  })

  // Fetch metrics for charge names
  const { data: metrics } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: () => billableMetricsApi.list(),
  })

  const metricMap = new Map(metrics?.map((m: BillableMetric) => [m.id, m]) ?? [])

  // Fetch commitments
  const { data: commitments, isLoading: commitmentsLoading } = useQuery({
    queryKey: ['commitments', plan?.code],
    queryFn: () => commitmentsApi.listForPlan(plan!.code),
    enabled: !!plan?.code,
  })

  // Fetch usage thresholds
  const { data: thresholds, isLoading: thresholdsLoading } = useQuery({
    queryKey: ['plan-thresholds', plan?.code],
    queryFn: () => usageThresholdsApi.listForPlan(plan!.code),
    enabled: !!plan?.code,
  })

  // Fetch entitlements for this plan
  const { data: entitlements, isLoading: entitlementsLoading } = useQuery({
    queryKey: ['plan-entitlements', plan?.id],
    queryFn: () => entitlementsApi.list({ plan_id: plan!.id }),
    enabled: !!plan?.id,
  })

  // Fetch features for entitlement display
  const { data: features } = useQuery({
    queryKey: ['features'],
    queryFn: () => featuresApi.list(),
    enabled: !!entitlements && entitlements.length > 0,
  })

  const featureMap = new Map(
    features?.map((f: Feature) => [f.id, f]) ?? []
  )

  // Fetch subscriptions for this plan
  const { data: allSubscriptions, isLoading: subscriptionsLoading } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => subscriptionsApi.list({ limit: 1000 }),
  })

  const planSubscriptions = allSubscriptions?.filter(
    (s: Subscription) => s.plan_id === plan?.id
  )

  // Fetch customers for subscription display
  const customerIds = [
    ...new Set(planSubscriptions?.map((s: Subscription) => s.customer_id) ?? []),
  ]
  const { data: customers } = useQuery({
    queryKey: ['customers-for-plan', plan?.id],
    queryFn: async () => {
      const results: Customer[] = []
      for (const cid of customerIds) {
        try {
          const customer = await customersApi.get(cid)
          results.push(customer)
        } catch {
          // skip
        }
      }
      return results
    },
    enabled: customerIds.length > 0,
  })

  const customerMap = new Map(
    customers?.map((c: Customer) => [c.id, c]) ?? []
  )

  // Commitment mutations
  const createCommitmentMutation = useMutation({
    mutationFn: (data: CommitmentCreateAPI) =>
      commitmentsApi.createForPlan(plan!.code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['commitments', plan?.code] })
      setShowAddCommitment(false)
      setCommitmentForm({
        commitment_type: 'minimum_commitment',
        amount_cents: '',
        invoice_display_name: '',
      })
      toast.success('Commitment created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to create commitment'
      toast.error(message)
    },
  })

  const updateCommitmentMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CommitmentUpdate }) =>
      commitmentsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['commitments', plan?.code] })
      setEditingCommitment(null)
      toast.success('Commitment updated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to update commitment'
      toast.error(message)
    },
  })

  const deleteCommitmentMutation = useMutation({
    mutationFn: (id: string) => commitmentsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['commitments', plan?.code] })
      setDeleteCommitment(null)
      toast.success('Commitment deleted successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to delete commitment'
      toast.error(message)
    },
  })

  // Usage threshold mutations
  const createThresholdMutation = useMutation({
    mutationFn: (data: UsageThresholdCreateAPI) =>
      usageThresholdsApi.createForPlan(plan!.code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['plan-thresholds', plan?.code],
      })
      setThresholdForm({
        amount_cents: '',
        currency: 'USD',
        recurring: false,
        threshold_display_name: '',
      })
      toast.success('Usage threshold created')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to create usage threshold'
      toast.error(message)
    },
  })

  const deleteThresholdMutation = useMutation({
    mutationFn: (id: string) => usageThresholdsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['plan-thresholds', plan?.code],
      })
      setDeleteThreshold(null)
      toast.success('Usage threshold deleted')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to delete usage threshold'
      toast.error(message)
    },
  })

  // Clone plan mutation
  const cloneMutation = useMutation({
    mutationFn: (data: PlanCreate) => plansApi.create(data),
    onSuccess: (newPlan: Plan) => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      toast.success('Plan cloned successfully')
      navigate(`/admin/plans/${newPlan.id}`)
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to clone plan'
      toast.error(message)
    },
  })

  const handleClone = () => {
    if (!plan) return
    const charges: ChargeInput[] = (plan.charges ?? []).map((c) => ({
      billable_metric_id: c.billable_metric_id,
      charge_model: c.charge_model as ChargeModel,
      properties: c.properties ?? {},
    }))
    cloneMutation.mutate({
      code: `${plan.code}_copy`,
      name: `${plan.name} (Copy)`,
      description: plan.description ?? undefined,
      amount_cents: plan.amount_cents,
      currency: plan.currency,
      interval: plan.interval,
      trial_period_days: plan.trial_period_days,
      charges,
    })
  }

  const handleCreateCommitment = (e: React.FormEvent) => {
    e.preventDefault()
    createCommitmentMutation.mutate({
      commitment_type: commitmentForm.commitment_type,
      amount_cents: parseInt(commitmentForm.amount_cents) || 0,
      invoice_display_name: commitmentForm.invoice_display_name || undefined,
    })
  }

  const handleUpdateCommitment = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingCommitment) return
    updateCommitmentMutation.mutate({
      id: editingCommitment.id,
      data: {
        commitment_type: commitmentForm.commitment_type,
        amount_cents: parseInt(commitmentForm.amount_cents) || 0,
        invoice_display_name: commitmentForm.invoice_display_name || undefined,
      },
    })
  }

  const handleCreateThreshold = (e: React.FormEvent) => {
    e.preventDefault()
    createThresholdMutation.mutate({
      amount_cents: parseInt(thresholdForm.amount_cents) || 0,
      currency: thresholdForm.currency,
      recurring: thresholdForm.recurring,
      threshold_display_name:
        thresholdForm.threshold_display_name || undefined,
    })
  }

  const startEditCommitment = (c: Commitment) => {
    setEditingCommitment(c)
    setCommitmentForm({
      commitment_type: c.commitment_type,
      amount_cents: c.amount_cents,
      invoice_display_name: c.invoice_display_name ?? '',
    })
  }

  const cancelEditCommitment = () => {
    setEditingCommitment(null)
    setCommitmentForm({
      commitment_type: 'minimum_commitment',
      amount_cents: '',
      invoice_display_name: '',
    })
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load plan. Please try again.
        </p>
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
              <Link to="/admin/plans">Plans</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>
              {isLoading ? (
                <Skeleton className="h-4 w-48 inline-block" />
              ) : (
                plan?.name ?? 'Plan'
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
      ) : plan ? (
        <>
          {/* Header */}
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-semibold tracking-tight">
                  {plan.name}
                </h2>
                <code className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                  {plan.code}
                </code>
              </div>
              {plan.description && (
                <p className="text-sm text-muted-foreground mt-1">
                  {plan.description}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleClone}
                disabled={cloneMutation.isPending}
              >
                <Copy className="mr-2 h-4 w-4" />
                {cloneMutation.isPending ? 'Cloning...' : 'Clone Plan'}
              </Button>
            </div>
          </div>

          {/* Overview Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">
                Plan Overview
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <span className="text-muted-foreground">Base Price</span>
                  <p className="text-lg font-semibold">
                    {formatCurrency(plan.amount_cents, plan.currency)}
                    <span className="text-sm font-normal text-muted-foreground">
                      /{intervalLabel(plan.interval)}
                    </span>
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Interval</span>
                  <p className="font-medium capitalize">{plan.interval}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Trial Period</span>
                  <p className="font-medium flex items-center gap-1">
                    {plan.trial_period_days > 0 ? (
                      <>
                        <Calendar className="h-3.5 w-3.5" />
                        {plan.trial_period_days} days
                      </>
                    ) : (
                      'None'
                    )}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">Currency</span>
                  <p className="font-medium">{plan.currency}</p>
                </div>
              </div>
              <div className="flex gap-4 mt-4 text-xs text-muted-foreground">
                <span>
                  Created {format(new Date(plan.created_at), 'MMM d, yyyy')}
                </span>
                <span>
                  Updated {format(new Date(plan.updated_at), 'MMM d, yyyy')}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Tabs */}
          <Tabs defaultValue="charges">
            <TabsList>
              <TabsTrigger value="charges">
                Charges{' '}
                {plan.charges && plan.charges.length > 0
                  ? `(${plan.charges.length})`
                  : ''}
              </TabsTrigger>
              <TabsTrigger value="commitments">
                Commitments{' '}
                {commitments && commitments.length > 0
                  ? `(${commitments.length})`
                  : ''}
              </TabsTrigger>
              <TabsTrigger value="thresholds">
                Thresholds{' '}
                {thresholds && thresholds.length > 0
                  ? `(${thresholds.length})`
                  : ''}
              </TabsTrigger>
              <TabsTrigger value="entitlements">
                Entitlements{' '}
                {entitlements && entitlements.length > 0
                  ? `(${entitlements.length})`
                  : ''}
              </TabsTrigger>
              <TabsTrigger value="subscriptions">
                Subscriptions{' '}
                {planSubscriptions && planSubscriptions.length > 0
                  ? `(${planSubscriptions.length})`
                  : ''}
              </TabsTrigger>
              <TabsTrigger value="activity">Activity</TabsTrigger>
            </TabsList>

            {/* Charges Tab */}
            <TabsContent value="charges" className="space-y-4">
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                      <Layers className="h-4 w-4" />
                      Usage Charges
                    </CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  {!plan.charges || plan.charges.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No usage charges configured for this plan.
                    </p>
                  ) : (
                    <div className="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Metric</TableHead>
                            <TableHead>Code</TableHead>
                            <TableHead>Charge Model</TableHead>
                            <TableHead>Properties</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {plan.charges.map((charge) => {
                            const metric = metricMap.get(
                              charge.billable_metric_id
                            )
                            return (
                              <TableRow key={charge.id}>
                                <TableCell className="font-medium">
                                  {metric?.name ?? 'Unknown'}
                                </TableCell>
                                <TableCell>
                                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                    {metric?.code ??
                                      charge.billable_metric_id.slice(0, 8)}
                                  </code>
                                </TableCell>
                                <TableCell>
                                  <ChargeModelBadge
                                    model={charge.charge_model}
                                  />
                                </TableCell>
                                <TableCell>
                                  {charge.properties &&
                                  Object.keys(charge.properties).length > 0 ? (
                                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                      {JSON.stringify(charge.properties)}
                                    </code>
                                  ) : (
                                    <span className="text-muted-foreground">
                                      —
                                    </span>
                                  )}
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
            </TabsContent>

            {/* Commitments Tab */}
            <TabsContent value="commitments" className="space-y-4">
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                      <Target className="h-4 w-4" />
                      Commitments
                    </CardTitle>
                    {!showAddCommitment && !editingCommitment && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setShowAddCommitment(true)
                          setCommitmentForm({
                            commitment_type: 'minimum_commitment',
                            amount_cents: '',
                            invoice_display_name: '',
                          })
                        }}
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Add Commitment
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {commitmentsLoading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-10 w-full" />
                      <Skeleton className="h-10 w-full" />
                    </div>
                  ) : commitments && commitments.length > 0 ? (
                    <div className="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Type</TableHead>
                            <TableHead>Amount</TableHead>
                            <TableHead>Display Name</TableHead>
                            <TableHead className="w-[100px]">
                              Actions
                            </TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {commitments.map((c: Commitment) =>
                            editingCommitment?.id === c.id ? (
                              <TableRow key={c.id}>
                                <TableCell colSpan={4}>
                                  <form
                                    onSubmit={handleUpdateCommitment}
                                    className="flex items-end gap-2"
                                  >
                                    <div className="space-y-1">
                                      <Label className="text-xs">Type</Label>
                                      <Select
                                        value={
                                          commitmentForm.commitment_type
                                        }
                                        onValueChange={(value) =>
                                          setCommitmentForm({
                                            ...commitmentForm,
                                            commitment_type: value,
                                          })
                                        }
                                      >
                                        <SelectTrigger className="w-[180px]">
                                          <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                          <SelectItem value="minimum_commitment">
                                            Minimum Commitment
                                          </SelectItem>
                                        </SelectContent>
                                      </Select>
                                    </div>
                                    <div className="space-y-1">
                                      <Label className="text-xs">
                                        Amount (cents)
                                      </Label>
                                      <Input
                                        type="number"
                                        value={commitmentForm.amount_cents}
                                        onChange={(e) =>
                                          setCommitmentForm({
                                            ...commitmentForm,
                                            amount_cents: e.target.value,
                                          })
                                        }
                                        className="w-[120px]"
                                        required
                                      />
                                    </div>
                                    <div className="space-y-1">
                                      <Label className="text-xs">
                                        Display Name
                                      </Label>
                                      <Input
                                        value={
                                          commitmentForm.invoice_display_name
                                        }
                                        onChange={(e) =>
                                          setCommitmentForm({
                                            ...commitmentForm,
                                            invoice_display_name:
                                              e.target.value,
                                          })
                                        }
                                        className="w-[140px]"
                                      />
                                    </div>
                                    <Button
                                      type="submit"
                                      size="sm"
                                      disabled={
                                        updateCommitmentMutation.isPending
                                      }
                                    >
                                      {updateCommitmentMutation.isPending
                                        ? 'Saving...'
                                        : 'Save'}
                                    </Button>
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="outline"
                                      onClick={cancelEditCommitment}
                                    >
                                      Cancel
                                    </Button>
                                  </form>
                                </TableCell>
                              </TableRow>
                            ) : (
                              <TableRow key={c.id}>
                                <TableCell>
                                  <Badge variant="outline">
                                    {c.commitment_type}
                                  </Badge>
                                </TableCell>
                                <TableCell className="font-mono">
                                  {formatCurrency(
                                    parseInt(c.amount_cents)
                                  )}
                                </TableCell>
                                <TableCell className="text-muted-foreground">
                                  {c.invoice_display_name || '—'}
                                </TableCell>
                                <TableCell>
                                  <div className="flex items-center gap-1">
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-7 w-7"
                                      onClick={() => startEditCommitment(c)}
                                    >
                                      <Pencil className="h-3 w-3" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="h-7 w-7 text-destructive"
                                      onClick={() => setDeleteCommitment(c)}
                                    >
                                      <Trash2 className="h-3 w-3" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                            )
                          )}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No commitments configured for this plan.
                    </p>
                  )}

                  {/* Add Commitment Inline Form */}
                  {showAddCommitment && (
                    <form
                      onSubmit={handleCreateCommitment}
                      className="border rounded-lg p-3 bg-muted/50 space-y-3 mt-3"
                    >
                      <div className="flex items-end gap-3">
                        <div className="space-y-1">
                          <Label className="text-xs">Commitment Type</Label>
                          <Select
                            value={commitmentForm.commitment_type}
                            onValueChange={(value) =>
                              setCommitmentForm({
                                ...commitmentForm,
                                commitment_type: value,
                              })
                            }
                          >
                            <SelectTrigger className="w-[180px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="minimum_commitment">
                                Minimum Commitment
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Amount (cents) *</Label>
                          <Input
                            type="number"
                            value={commitmentForm.amount_cents}
                            onChange={(e) =>
                              setCommitmentForm({
                                ...commitmentForm,
                                amount_cents: e.target.value,
                              })
                            }
                            className="w-[120px]"
                            required
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Display Name</Label>
                          <Input
                            value={commitmentForm.invoice_display_name}
                            onChange={(e) =>
                              setCommitmentForm({
                                ...commitmentForm,
                                invoice_display_name: e.target.value,
                              })
                            }
                            className="w-[140px]"
                          />
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          type="submit"
                          size="sm"
                          disabled={createCommitmentMutation.isPending}
                        >
                          {createCommitmentMutation.isPending
                            ? 'Creating...'
                            : 'Submit'}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setShowAddCommitment(false)
                            setCommitmentForm({
                              commitment_type: 'minimum_commitment',
                              amount_cents: '',
                              invoice_display_name: '',
                            })
                          }}
                        >
                          Cancel
                        </Button>
                      </div>
                    </form>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Usage Thresholds Tab */}
            <TabsContent value="thresholds" className="space-y-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <Target className="h-4 w-4" />
                    Usage Thresholds
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {thresholdsLoading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-10 w-full" />
                    </div>
                  ) : thresholds && thresholds.length > 0 ? (
                    <div className="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Amount</TableHead>
                            <TableHead>Currency</TableHead>
                            <TableHead>Recurring</TableHead>
                            <TableHead>Display Name</TableHead>
                            <TableHead className="w-[60px]">Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {thresholds.map((t: UsageThreshold) => (
                            <TableRow key={t.id}>
                              <TableCell className="font-mono">
                                {formatCurrency(parseInt(t.amount_cents))}
                              </TableCell>
                              <TableCell>{t.currency}</TableCell>
                              <TableCell>
                                <Badge
                                  variant={
                                    t.recurring ? 'default' : 'secondary'
                                  }
                                >
                                  {t.recurring ? 'Yes' : 'No'}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-muted-foreground">
                                {t.threshold_display_name || '—'}
                              </TableCell>
                              <TableCell>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 text-destructive"
                                  onClick={() => setDeleteThreshold(t)}
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No usage thresholds configured for this plan.
                    </p>
                  )}

                  {/* Add Threshold Form */}
                  <form
                    onSubmit={handleCreateThreshold}
                    className="border rounded-lg p-3 bg-muted/50 space-y-3 mt-3"
                  >
                    <p className="text-xs font-medium">
                      Add Usage Threshold
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">Amount (cents) *</Label>
                        <Input
                          type="number"
                          value={thresholdForm.amount_cents}
                          onChange={(e) =>
                            setThresholdForm({
                              ...thresholdForm,
                              amount_cents: e.target.value,
                            })
                          }
                          required
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">Currency</Label>
                        <Select
                          value={thresholdForm.currency}
                          onValueChange={(value) =>
                            setThresholdForm({
                              ...thresholdForm,
                              currency: value,
                            })
                          }
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
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Display Name</Label>
                      <Input
                        value={thresholdForm.threshold_display_name}
                        onChange={(e) =>
                          setThresholdForm({
                            ...thresholdForm,
                            threshold_display_name: e.target.value,
                          })
                        }
                        placeholder="Optional display name"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="threshold-recurring"
                        checked={thresholdForm.recurring}
                        onChange={(e) =>
                          setThresholdForm({
                            ...thresholdForm,
                            recurring: e.target.checked,
                          })
                        }
                      />
                      <Label htmlFor="threshold-recurring" className="text-sm">
                        Recurring
                      </Label>
                    </div>
                    <Button
                      type="submit"
                      size="sm"
                      disabled={createThresholdMutation.isPending}
                    >
                      {createThresholdMutation.isPending
                        ? 'Creating...'
                        : 'Add Threshold'}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Entitlements Tab */}
            <TabsContent value="entitlements" className="space-y-4">
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
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No features configured for this plan.
                    </p>
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
                          {entitlements.map((entitlement: Entitlement) => {
                            const feature = featureMap.get(
                              entitlement.feature_id
                            )
                            return (
                              <TableRow key={entitlement.id}>
                                <TableCell className="font-medium">
                                  {feature?.name ?? 'Unknown'}
                                </TableCell>
                                <TableCell>
                                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                    {feature?.code ??
                                      entitlement.feature_id}
                                  </code>
                                </TableCell>
                                <TableCell>
                                  {feature ? (
                                    <Badge
                                      variant={
                                        feature.feature_type === 'boolean'
                                          ? 'default'
                                          : feature.feature_type ===
                                              'quantity'
                                            ? 'secondary'
                                            : 'outline'
                                      }
                                    >
                                      {feature.feature_type}
                                    </Badge>
                                  ) : (
                                    '—'
                                  )}
                                </TableCell>
                                <TableCell>
                                  {feature?.feature_type === 'boolean'
                                    ? entitlement.value === 'true'
                                      ? 'Enabled'
                                      : 'Disabled'
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
            </TabsContent>

            {/* Subscriptions Tab */}
            <TabsContent value="subscriptions" className="space-y-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    Subscriptions Using This Plan
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {subscriptionsLoading ? (
                    <div className="space-y-2">
                      <Skeleton className="h-10 w-full" />
                      <Skeleton className="h-10 w-full" />
                      <Skeleton className="h-10 w-full" />
                    </div>
                  ) : !planSubscriptions?.length ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No subscriptions are using this plan.
                    </p>
                  ) : (
                    <div className="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>External ID</TableHead>
                            <TableHead>Customer</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Started</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {planSubscriptions.map((sub: Subscription) => {
                            const customer = customerMap.get(sub.customer_id)
                            return (
                              <TableRow key={sub.id}>
                                <TableCell>
                                  <Link
                                    to={`/admin/subscriptions/${sub.id}`}
                                    className="hover:underline font-medium"
                                  >
                                    {sub.external_id}
                                  </Link>
                                </TableCell>
                                <TableCell>
                                  {customer ? (
                                    <Link
                                      to={`/admin/customers/${sub.customer_id}`}
                                      className="hover:underline"
                                    >
                                      {customer.name}
                                    </Link>
                                  ) : (
                                    <span className="text-muted-foreground">
                                      {sub.customer_id.slice(0, 8)}...
                                    </span>
                                  )}
                                </TableCell>
                                <TableCell>
                                  <StatusBadge status={sub.status} />
                                </TableCell>
                                <TableCell>
                                  {sub.started_at
                                    ? format(
                                        new Date(sub.started_at),
                                        'MMM d, yyyy'
                                      )
                                    : '—'}
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
            </TabsContent>

            {/* Activity Tab */}
            <TabsContent value="activity" className="space-y-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <ScrollText className="h-4 w-4" />
                    Activity Log
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <AuditTrailTimeline
                    resourceType="plan"
                    resourceId={id!}
                    limit={20}
                    showViewAll
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      ) : null}

      {/* Delete Commitment Confirmation */}
      <AlertDialog
        open={!!deleteCommitment}
        onOpenChange={(open) => !open && setDeleteCommitment(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Commitment</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this commitment? This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteCommitment &&
                deleteCommitmentMutation.mutate(deleteCommitment.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteCommitmentMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Threshold Confirmation */}
      <AlertDialog
        open={!!deleteThreshold}
        onOpenChange={(open) => !open && setDeleteThreshold(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Usage Threshold</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this usage threshold? This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteThreshold &&
                deleteThresholdMutation.mutate(deleteThreshold.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteThresholdMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
