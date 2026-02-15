import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Plus, Search, ArrowUpDown, Target, Trash2, Pencil } from 'lucide-react'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { SubscriptionFormDialog } from '@/components/SubscriptionFormDialog'
import { EditSubscriptionDialog } from '@/components/EditSubscriptionDialog'
import { subscriptionsApi, customersApi, plansApi, usageThresholdsApi, ApiError } from '@/lib/api'
import type { Subscription, SubscriptionCreate, SubscriptionUpdate, SubscriptionStatus, Plan, TerminationAction, UsageThresholdCreateAPI } from '@/types/billing'

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}

function StatusBadge({ status }: { status: SubscriptionStatus }) {
  const variants: Record<SubscriptionStatus, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
    pending: { variant: 'secondary', label: 'Pending' },
    active: { variant: 'default', label: 'Active' },
    canceled: { variant: 'outline', label: 'Canceled' },
    terminated: { variant: 'destructive', label: 'Terminated' },
  }

  const config = variants[status]
  return <Badge variant={config.variant}>{config.label}</Badge>
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

function ChangePlanDialog({
  open,
  onOpenChange,
  subscription,
  plans,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscription: Subscription | null
  plans: Plan[]
  onSubmit: (subscriptionId: string, newPlanId: string) => void
  isLoading: boolean
}) {
  const [selectedPlanId, setSelectedPlanId] = useState('')

  if (!subscription) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle>Change Plan</DialogTitle>
          <DialogDescription>
            Upgrade or downgrade the subscription to a different plan
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Current Plan</Label>
            <p className="text-sm text-muted-foreground">
              {plans.find(p => p.id === subscription.plan_id)?.name ?? 'Unknown'}
            </p>
          </div>
          <div className="space-y-2">
            <Label>New Plan *</Label>
            <Select value={selectedPlanId} onValueChange={setSelectedPlanId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a new plan" />
              </SelectTrigger>
              <SelectContent>
                {plans
                  .filter(p => p.id !== subscription.plan_id)
                  .map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} — {formatCurrency(p.amount_cents, p.currency)}/{p.interval}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            disabled={!selectedPlanId || isLoading}
            onClick={() => onSubmit(subscription.id, selectedPlanId)}
          >
            {isLoading ? 'Changing...' : 'Change Plan'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TerminateDialog({
  open,
  onOpenChange,
  subscription,
  onTerminate,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscription: Subscription | null
  onTerminate: (id: string, action: TerminationAction) => void
  isLoading: boolean
}) {
  const [action, setAction] = useState<TerminationAction>('generate_invoice')

  if (!subscription) return null

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Terminate Subscription</AlertDialogTitle>
          <AlertDialogDescription>
            This will permanently terminate the subscription. Choose what should happen with the remaining billing period.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="py-4 space-y-3">
          <Label>Financial Action</Label>
          <Select value={action} onValueChange={(v: TerminationAction) => setAction(v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="generate_invoice">Generate final invoice</SelectItem>
              <SelectItem value="generate_credit_note">Generate credit note (refund)</SelectItem>
              <SelectItem value="skip">Skip (no financial action)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => onTerminate(subscription.id, action)}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isLoading ? 'Terminating...' : 'Terminate'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
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
              <p className="text-2xl font-bold">{formatCurrency(Number(currentUsage.current_usage_amount_cents))}</p>
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
                      <td className="p-2">{formatCurrency(parseInt(t.amount_cents))}</td>
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
  const [searchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>(searchParams.get('status') || 'all')
  const [formOpen, setFormOpen] = useState(false)
  const [changePlanSub, setChangePlanSub] = useState<Subscription | null>(null)
  const [terminateSub, setTerminateSub] = useState<Subscription | null>(null)
  const [thresholdsSub, setThresholdsSub] = useState<Subscription | null>(null)
  const [editSub, setEditSub] = useState<Subscription | null>(null)

  // Fetch subscriptions from API
  const { data: subscriptions, isLoading, error } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => subscriptionsApi.list(),
  })

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
      subscriptionsApi.update(id, { previous_plan_id: changePlanSub?.plan_id } as never),
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

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load subscriptions. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Subscriptions</h2>
          <p className="text-muted-foreground">
            Manage customer subscriptions
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Subscription
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search subscriptions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="canceled">Canceled</SelectItem>
            <SelectItem value="terminated">Terminated</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>Plan</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Trial</TableHead>
              <TableHead>Billing</TableHead>
              <TableHead>Started</TableHead>
              <TableHead className="w-[120px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                </TableRow>
              ))
            ) : filteredSubscriptions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center">
                  No subscriptions found
                </TableCell>
              </TableRow>
            ) : (
              filteredSubscriptions.map((sub) => {
                const customer = customerMap.get(sub.customer_id)
                const plan = planMap.get(sub.plan_id)

                return (
                  <TableRow key={sub.id}>
                    <TableCell>
                      <div>
                        <div className="font-medium">{customer?.name ?? 'Unknown'}</div>
                        <div className="text-xs text-muted-foreground">
                          {sub.external_id}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div>
                        <div>{plan?.name ?? 'Unknown'}</div>
                        <div className="text-xs text-muted-foreground">
                          {plan ? `${formatCurrency(plan.amount_cents, plan.currency)}/${plan.interval}` : '\u2014'}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={sub.status} />
                    </TableCell>
                    <TableCell>
                      <TrialBadge sub={sub} />
                      {sub.trial_ended_at && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {format(new Date(sub.trial_ended_at), 'MMM d, yyyy')}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="text-xs">
                        <span className="capitalize">{sub.billing_time}</span>
                        {sub.pay_in_advance && (
                          <Badge variant="outline" className="ml-1 text-xs px-1">prepaid</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {sub.started_at
                        ? format(new Date(sub.started_at), 'MMM d, yyyy')
                        : '\u2014'}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {(sub.status === 'active' || sub.status === 'pending') && (
                          <>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              title="Edit subscription"
                              onClick={() => setEditSub(sub)}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              title="Change plan"
                              onClick={() => setChangePlanSub(sub)}
                            >
                              <ArrowUpDown className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              title="Usage thresholds"
                              onClick={() => setThresholdsSub(sub)}
                            >
                              <Target className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-destructive"
                              title="Terminate"
                              onClick={() => setTerminateSub(sub)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
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
        onSubmit={(id, planId) => changePlanMutation.mutate({ id, planId })}
        isLoading={changePlanMutation.isPending}
      />

      {/* Terminate Dialog */}
      <TerminateDialog
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
