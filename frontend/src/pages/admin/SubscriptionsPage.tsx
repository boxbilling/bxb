import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { Plus, Search, ArrowUpDown, Target, Trash2, Pencil, Pause, Play, MoreHorizontal, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { format } from 'date-fns'

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
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
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
import { Separator } from '@/components/ui/separator'
import PageHeader from '@/components/PageHeader'
import { SubscriptionFormDialog } from '@/components/SubscriptionFormDialog'
import { EditSubscriptionDialog } from '@/components/EditSubscriptionDialog'
import { ChangePlanDialog } from '@/components/ChangePlanDialog'
import { TerminateSubscriptionDialog } from '@/components/TerminateSubscriptionDialog'
import { TablePagination } from '@/components/TablePagination'
import { SortableTableHead, useSortState } from '@/components/SortableTableHead'
import { subscriptionsApi, customersApi, plansApi, usageThresholdsApi, ApiError } from '@/lib/api'
import type { Subscription, SubscriptionCreate, SubscriptionUpdate, SubscriptionStatus, TerminationAction, UsageThresholdCreateAPI } from '@/types/billing'
import { formatCents } from '@/lib/utils'

const PAGE_SIZE = 20

function StatusBadge({ status }: { status: SubscriptionStatus }) {
  const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
    pending: { variant: 'secondary', label: 'Pending' },
    active: { variant: 'default', label: 'Active' },
    paused: { variant: 'outline', label: 'Paused' },
    canceled: { variant: 'outline', label: 'Canceled' },
    terminated: { variant: 'destructive', label: 'Terminated' },
  }

  const config = variants[status]
  return <Badge variant={config.variant}>{config.label}</Badge>
}

function NextBillingCell({ sub }: { sub: Subscription }) {
  const { data } = useQuery({
    queryKey: ['next-billing-date', sub.id],
    queryFn: () => subscriptionsApi.getNextBillingDate(sub.id),
    enabled: sub.status === 'active' || sub.status === 'pending',
  })

  if (sub.status !== 'active' && sub.status !== 'pending') {
    return <span className="text-muted-foreground">{'\u2014'}</span>
  }

  if (!data) {
    return <Skeleton className="h-5 w-20" />
  }

  return (
    <div>
      <div className="text-sm">{format(new Date(data.next_billing_date), 'MMM d, yyyy')}</div>
      <div className="text-xs text-muted-foreground">{data.days_until_next_billing}d away</div>
    </div>
  )
}

function TrialBadge({ sub }: { sub: Subscription }) {
  if (!sub.trial_period_days || sub.trial_period_days === 0) return null
  const trialEnded = sub.trial_ended_at && new Date(sub.trial_ended_at) <= new Date()
  return (
    <Badge variant="outline" className={trialEnded ? 'text-muted-foreground' : 'border-blue-500 text-blue-600'}>
      {trialEnded ? 'Trial ended' : `${sub.trial_period_days}d trial`}
    </Badge>
  )
}

function SubscriptionThresholdsDialog({
  open,
  onOpenChange,
  subscription,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscription: Subscription | null
}) {
  const queryClient = useQueryClient()
  const [thresholdForm, setThresholdForm] = useState({
    amount_cents: '',
    currency: 'USD',
    recurring: false,
    threshold_display_name: '',
  })

  const { data: thresholds, isLoading } = useQuery({
    queryKey: ['sub-thresholds', subscription?.id],
    queryFn: () => usageThresholdsApi.listForSubscription(subscription!.id),
    enabled: !!subscription?.id,
  })

  const { data: currentUsage } = useQuery({
    queryKey: ['sub-current-usage', subscription?.id],
    queryFn: () => usageThresholdsApi.getCurrentUsage(subscription!.id),
    enabled: !!subscription?.id,
  })

  const createMutation = useMutation({
    mutationFn: (data: UsageThresholdCreateAPI) =>
      usageThresholdsApi.createForSubscription(subscription!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sub-thresholds', subscription?.id] })
      setThresholdForm({ amount_cents: '', currency: 'USD', recurring: false, threshold_display_name: '' })
      toast.success('Threshold added')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to create threshold')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => usageThresholdsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sub-thresholds', subscription?.id] })
      toast.success('Threshold removed')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to delete threshold')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate({
      amount_cents: parseInt(thresholdForm.amount_cents) || 0,
      currency: thresholdForm.currency,
      recurring: thresholdForm.recurring,
      threshold_display_name: thresholdForm.threshold_display_name || undefined,
    })
  }

  if (!subscription) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Target className="h-5 w-5" />
            Usage Thresholds
          </DialogTitle>
          <DialogDescription>
            Manage progressive billing thresholds for this subscription
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {currentUsage && (
            <div className="p-3 border rounded-lg bg-muted/50">
              <p className="text-sm font-medium">Current Usage</p>
              <p className="text-2xl font-bold">{formatCents(Number(currentUsage.current_usage_amount_cents))}</p>
              <p className="text-xs text-muted-foreground">
                Period: {format(new Date(currentUsage.billing_period_start), 'MMM d')} &ndash; {format(new Date(currentUsage.billing_period_end), 'MMM d, yyyy')}
              </p>
            </div>
          )}

          {/* Existing thresholds */}
          {isLoading ? (
            <Skeleton className="h-10 w-full" />
          ) : thresholds && thresholds.length > 0 ? (
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="text-left p-2 font-medium">Amount</th>
                    <th className="text-left p-2 font-medium">Recurring</th>
                    <th className="text-left p-2 font-medium">Name</th>
                    <th className="text-right p-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {thresholds.map((t) => (
                    <tr key={t.id} className="border-b last:border-b-0">
                      <td className="p-2">{formatCents(parseInt(t.amount_cents))}</td>
                      <td className="p-2">{t.recurring ? 'Yes' : 'No'}</td>
                      <td className="p-2 text-muted-foreground">{t.threshold_display_name || '\u2014'}</td>
                      <td className="p-2 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive"
                          onClick={() => deleteMutation.mutate(t.id)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-4 text-muted-foreground text-sm border border-dashed rounded-lg">
              No usage thresholds configured.
            </div>
          )}

          {/* Add threshold form */}
          <form onSubmit={handleSubmit} className="border rounded-lg p-3 bg-muted/50 space-y-3">
            <p className="text-xs font-medium">Add Threshold</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">Amount (cents) *</Label>
                <Input
                  type="number"
                  value={thresholdForm.amount_cents}
                  onChange={(e) => setThresholdForm({ ...thresholdForm, amount_cents: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Currency</Label>
                <Select
                  value={thresholdForm.currency}
                  onValueChange={(v) => setThresholdForm({ ...thresholdForm, currency: v })}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
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
                onChange={(e) => setThresholdForm({ ...thresholdForm, threshold_display_name: e.target.value })}
                placeholder="Optional"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="sub-threshold-recurring"
                checked={thresholdForm.recurring}
                onChange={(e) => setThresholdForm({ ...thresholdForm, recurring: e.target.checked })}
              />
              <Label htmlFor="sub-threshold-recurring" className="text-sm">Recurring</Label>
            </div>
            <Button type="submit" size="sm" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Adding...' : 'Add Threshold'}
            </Button>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function SubscriptionsPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>(searchParams.get('status') || 'all')
  const [formOpen, setFormOpen] = useState(false)
  const [changePlanSub, setChangePlanSub] = useState<Subscription | null>(null)
  const [terminateSub, setTerminateSub] = useState<Subscription | null>(null)
  const [thresholdsSub, setThresholdsSub] = useState<Subscription | null>(null)
  const [editSub, setEditSub] = useState<Subscription | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const { sort, setSort, orderBy } = useSortState()

  // Fetch subscriptions from API
  const { data, isLoading, error } = useQuery({
    queryKey: ['subscriptions', page, pageSize, orderBy],
    queryFn: () => subscriptionsApi.listPaginated({ skip: (page - 1) * pageSize, limit: pageSize, order_by: orderBy }),
  })

  const subscriptions = data?.data
  const totalCount = data?.totalCount ?? 0

  // Fetch customers for the form and display
  const { data: customers } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  // Fetch plans for the form and display
  const { data: plans } = useQuery({
    queryKey: ['plans'],
    queryFn: () => plansApi.list(),
  })

  // Create lookup maps for customers and plans
  const customerMap = new Map(customers?.map((c) => [c.id, c]) ?? [])
  const planMap = new Map(plans?.map((p) => [p.id, p]) ?? [])

  // Filter subscriptions (client-side)
  const filteredSubscriptions = subscriptions?.filter((s) => {
    const customer = customerMap.get(s.customer_id)
    const plan = planMap.get(s.plan_id)

    const matchesStatus = statusFilter === 'all' || s.status === statusFilter
    const matchesSearch = !search ||
      customer?.name.toLowerCase().includes(search.toLowerCase()) ||
      plan?.name.toLowerCase().includes(search.toLowerCase()) ||
      s.external_id.toLowerCase().includes(search.toLowerCase())

    return matchesStatus && matchesSearch
  }) ?? []

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: SubscriptionCreate) => subscriptionsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setFormOpen(false)
      toast.success('Subscription created successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create subscription'
      toast.error(message)
    },
  })

  // Change plan mutation (upgrade/downgrade)
  const changePlanMutation = useMutation({
    mutationFn: ({ id, planId }: { id: string; planId: string }) =>
      subscriptionsApi.update(id, {
        plan_id: planId,
        previous_plan_id: changePlanSub?.plan_id,
        downgraded_at: new Date().toISOString(),
      } as SubscriptionUpdate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setChangePlanSub(null)
      toast.success('Plan changed successfully')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to change plan')
    },
  })

  // Terminate mutation
  const terminateMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: TerminationAction }) =>
      subscriptionsApi.terminate(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setTerminateSub(null)
      toast.success('Subscription terminated')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to terminate subscription')
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: SubscriptionUpdate }) =>
      subscriptionsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setEditSub(null)
      toast.success('Subscription updated')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to update subscription')
    },
  })

  // Pause mutation
  const pauseMutation = useMutation({
    mutationFn: (id: string) => subscriptionsApi.pause(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      toast.success('Subscription paused')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to pause subscription')
    },
  })

  // Resume mutation
  const resumeMutation = useMutation({
    mutationFn: (id: string) => subscriptionsApi.resume(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      toast.success('Subscription resumed')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to resume subscription')
    },
  })

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // Selectable subscriptions: active, pending, or paused
  const selectableSubscriptions = filteredSubscriptions.filter(
    (s) => s.status === 'active' || s.status === 'pending' || s.status === 'paused'
  )
  const allSelectableSelected = selectableSubscriptions.length > 0 && selectableSubscriptions.every((s) => selectedIds.has(s.id))

  // Determine which statuses are in the selection
  const selectedStatuses = useMemo(() => {
    const statuses = new Set<string>()
    for (const sub of filteredSubscriptions) {
      if (selectedIds.has(sub.id)) {
        statuses.add(sub.status)
      }
    }
    return statuses
  }, [filteredSubscriptions, selectedIds])

  const hasActiveSelected = selectedStatuses.has('active')
  const hasPausedSelected = selectedStatuses.has('paused')

  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    setSelectedIds(next)
  }

  const toggleSelectAll = () => {
    if (allSelectableSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(selectableSubscriptions.map((s) => s.id)))
    }
  }

  // Bulk mutations
  const bulkPauseMutation = useMutation({
    mutationFn: () =>
      subscriptionsApi.bulkPause({ subscription_ids: Array.from(selectedIds) }),
    onSuccess: (result) => {
      toast.success(`Paused ${result.succeeded_count} subscription(s)${result.failed_count > 0 ? `, ${result.failed_count} failed` : ''}`)
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
    },
    onError: () => {
      toast.error('Failed to bulk pause subscriptions')
    },
  })

  const bulkResumeMutation = useMutation({
    mutationFn: () =>
      subscriptionsApi.bulkResume({ subscription_ids: Array.from(selectedIds) }),
    onSuccess: (result) => {
      toast.success(`Resumed ${result.succeeded_count} subscription(s)${result.failed_count > 0 ? `, ${result.failed_count} failed` : ''}`)
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
    },
    onError: () => {
      toast.error('Failed to bulk resume subscriptions')
    },
  })

  const bulkTerminateMutation = useMutation({
    mutationFn: () =>
      subscriptionsApi.bulkTerminate({ subscription_ids: Array.from(selectedIds), on_termination_action: 'generate_invoice' }),
    onSuccess: (result) => {
      toast.success(`Terminated ${result.succeeded_count} subscription(s)${result.failed_count > 0 ? `, ${result.failed_count} failed` : ''}`)
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
    },
    onError: () => {
      toast.error('Failed to bulk terminate subscriptions')
    },
  })

  const isBulkPending = bulkPauseMutation.isPending || bulkResumeMutation.isPending || bulkTerminateMutation.isPending

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load subscriptions. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Subscriptions"
        description="Manage customer subscriptions"
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Subscription
          </Button>
        }
      />

      {/* Filters */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-4">
        <div className="relative flex-1 max-w-none md:max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search subscriptions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full md:w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="paused">Paused</SelectItem>
            <SelectItem value="canceled">Canceled</SelectItem>
            <SelectItem value="terminated">Terminated</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Floating Bulk Action Bar */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 p-3">
          <span className="text-sm font-medium">{selectedIds.size} selected</span>
          <Separator orientation="vertical" className="h-6" />
          {hasActiveSelected && (
            <Button
              size="sm"
              variant="outline"
              disabled={isBulkPending}
              onClick={() => bulkPauseMutation.mutate()}
            >
              {bulkPauseMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Pause className="mr-2 h-4 w-4" />
              )}
              Pause
            </Button>
          )}
          {hasPausedSelected && (
            <Button
              size="sm"
              variant="outline"
              disabled={isBulkPending}
              onClick={() => bulkResumeMutation.mutate()}
            >
              {bulkResumeMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              Resume
            </Button>
          )}
          <Button
            size="sm"
            variant="destructive"
            disabled={isBulkPending}
            onClick={() => bulkTerminateMutation.mutate()}
          >
            {bulkTerminateMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="mr-2 h-4 w-4" />
            )}
            Terminate
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setSelectedIds(new Set())}
          >
            Clear
          </Button>
        </div>
      )}

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40px]">
                {selectableSubscriptions.length > 0 && (
                  <Checkbox
                    checked={allSelectableSelected}
                    onCheckedChange={toggleSelectAll}
                    aria-label="Select all actionable subscriptions"
                  />
                )}
              </TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Plan</TableHead>
              <SortableTableHead label="Status" sortKey="status" sort={sort} onSort={setSort} />
              <TableHead className="hidden md:table-cell">Trial</TableHead>
              <TableHead className="hidden md:table-cell">Billing</TableHead>
              <SortableTableHead className="hidden md:table-cell" label="Started" sortKey="started_at" sort={sort} onSort={setSort} />
              <TableHead className="hidden md:table-cell">Next Billing</TableHead>
              <TableHead className="w-[120px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-4" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                </TableRow>
              ))
            ) : filteredSubscriptions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="h-24 text-center">
                  No subscriptions found
                </TableCell>
              </TableRow>
            ) : (
              filteredSubscriptions.map((sub) => {
                const customer = customerMap.get(sub.customer_id)
                const plan = planMap.get(sub.plan_id)

                return (
                  <TableRow
                    key={sub.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/admin/subscriptions/${sub.id}`)}
                  >
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      {(sub.status === 'active' || sub.status === 'pending' || sub.status === 'paused') && (
                        <Checkbox
                          checked={selectedIds.has(sub.id)}
                          onCheckedChange={() => toggleSelect(sub.id)}
                          aria-label={`Select subscription ${sub.external_id}`}
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <div>
                        <Link
                          to={`/admin/customers/${sub.customer_id}`}
                          className="font-medium hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {customer?.name ?? 'Unknown'}
                        </Link>
                        <div className="text-xs text-muted-foreground">
                          {sub.external_id}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div>
                        <Link
                          to={`/admin/plans/${sub.plan_id}`}
                          className="hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {plan?.name ?? 'Unknown'}
                        </Link>
                        <div className="text-xs text-muted-foreground">
                          {plan ? `${formatCents(plan.amount_cents, plan.currency)}/${plan.interval}` : '\u2014'}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={sub.status} />
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <TrialBadge sub={sub} />
                      {sub.trial_ended_at && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {format(new Date(sub.trial_ended_at), 'MMM d, yyyy')}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <div className="text-xs">
                        <span className="capitalize">{sub.billing_time}</span>
                        {sub.pay_in_advance && (
                          <Badge variant="outline" className="ml-1 text-xs px-1">prepaid</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      {sub.started_at
                        ? format(new Date(sub.started_at), 'MMM d, yyyy')
                        : '\u2014'}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <NextBillingCell sub={sub} />
                    </TableCell>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      {(sub.status === 'active' || sub.status === 'pending' || sub.status === 'paused') ? (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => setEditSub(sub)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            {sub.status !== 'paused' && (
                              <DropdownMenuItem onClick={() => setChangePlanSub(sub)}>
                                <ArrowUpDown className="mr-2 h-4 w-4" />
                                Change Plan
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem onClick={() => setThresholdsSub(sub)}>
                              <Target className="mr-2 h-4 w-4" />
                              Usage Thresholds
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            {sub.status === 'active' && (
                              <DropdownMenuItem onClick={() => pauseMutation.mutate(sub.id)}>
                                <Pause className="mr-2 h-4 w-4" />
                                Pause
                              </DropdownMenuItem>
                            )}
                            {sub.status === 'paused' && (
                              <DropdownMenuItem onClick={() => resumeMutation.mutate(sub.id)}>
                                <Play className="mr-2 h-4 w-4" />
                                Resume
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() => setTerminateSub(sub)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Terminate
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      ) : (
                        <span className="text-muted-foreground">{'\u2014'}</span>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          pageSize={pageSize}
          totalCount={totalCount}
          onPageChange={setPage}
          onPageSizeChange={(size) => { setPageSize(size); setPage(1) }}
        />
      </div>

      {/* Create Dialog */}
      <SubscriptionFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        customers={customers ?? []}
        plans={plans ?? []}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
      />

      {/* Change Plan Dialog */}
      <ChangePlanDialog
        open={!!changePlanSub}
        onOpenChange={(open) => !open && setChangePlanSub(null)}
        subscription={changePlanSub}
        plans={plans ?? []}
        onSubmit={(id, planId, _effectiveDate) => changePlanMutation.mutate({ id, planId })}
        isLoading={changePlanMutation.isPending}
      />

      {/* Terminate Dialog */}
      <TerminateSubscriptionDialog
        open={!!terminateSub}
        onOpenChange={(open) => !open && setTerminateSub(null)}
        subscription={terminateSub}
        onTerminate={(id, action) => terminateMutation.mutate({ id, action })}
        isLoading={terminateMutation.isPending}
      />

      {/* Usage Thresholds Dialog */}
      <SubscriptionThresholdsDialog
        open={!!thresholdsSub}
        onOpenChange={(open) => !open && setThresholdsSub(null)}
        subscription={thresholdsSub}
      />

      {/* Edit Subscription Dialog */}
      {editSub && (
        <EditSubscriptionDialog
          open={!!editSub}
          onOpenChange={(open) => !open && setEditSub(null)}
          subscription={editSub}
          onSubmit={(data) => updateMutation.mutate({ id: editSub.id, data })}
          isLoading={updateMutation.isPending}
        />
      )}
    </div>
  )
}
