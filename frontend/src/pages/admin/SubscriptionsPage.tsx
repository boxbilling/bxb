import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Plus, Search, ArrowUpDown, Target, Trash2, Pencil, CalendarIcon, ArrowRight, TrendingUp, TrendingDown, Minus, Pause, Play, MoreHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import { format } from 'date-fns'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
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
import { SubscriptionFormDialog } from '@/components/SubscriptionFormDialog'
import { EditSubscriptionDialog } from '@/components/EditSubscriptionDialog'
import { TablePagination } from '@/components/TablePagination'
import { subscriptionsApi, customersApi, plansApi, usageThresholdsApi, ApiError } from '@/lib/api'
import type { Subscription, SubscriptionCreate, SubscriptionUpdate, SubscriptionStatus, Plan, TerminationAction, UsageThresholdCreateAPI, ChangePlanPreviewResponse } from '@/types/billing'
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
  onSubmit: (subscriptionId: string, newPlanId: string, effectiveDate?: string) => void
  isLoading: boolean
}) {
  const [selectedPlanId, setSelectedPlanId] = useState('')
  const [effectiveDate, setEffectiveDate] = useState<Date | undefined>(undefined)
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [preview, setPreview] = useState<ChangePlanPreviewResponse | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const currentPlan = subscription ? plans.find(p => p.id === subscription.plan_id) : null
  const newPlan = selectedPlanId ? plans.find(p => p.id === selectedPlanId) : null

  // Fetch preview when plan is selected
  const fetchPreview = async (planId: string, date?: Date) => {
    if (!subscription) return
    setPreviewLoading(true)
    try {
      const result = await subscriptionsApi.changePlanPreview(subscription.id, {
        new_plan_id: planId,
        effective_date: date?.toISOString() ?? null,
      })
      setPreview(result)
    } catch {
      setPreview(null)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handlePlanChange = (planId: string) => {
    setSelectedPlanId(planId)
    if (planId) fetchPreview(planId, effectiveDate)
    else setPreview(null)
  }

  const handleDateChange = (date: Date | undefined) => {
    setEffectiveDate(date)
    setCalendarOpen(false)
    if (selectedPlanId) fetchPreview(selectedPlanId, date)
  }

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setSelectedPlanId('')
      setEffectiveDate(undefined)
      setPreview(null)
    }
    onOpenChange(isOpen)
  }

  if (!subscription) return null

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Change Plan</DialogTitle>
          <DialogDescription>
            Upgrade or downgrade the subscription to a different plan
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          {/* Plan Selection */}
          <div className="space-y-2">
            <Label>New Plan *</Label>
            <Select value={selectedPlanId} onValueChange={handlePlanChange}>
              <SelectTrigger>
                <SelectValue placeholder="Select a new plan" />
              </SelectTrigger>
              <SelectContent>
                {plans
                  .filter(p => p.id !== subscription.plan_id)
                  .map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} — {formatCents(p.amount_cents, p.currency)}/{p.interval}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          {/* Effective Date Picker */}
          <div className="space-y-2">
            <Label>Effective Date</Label>
            <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-full justify-start text-left font-normal">
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {effectiveDate ? format(effectiveDate, 'MMM d, yyyy') : 'Immediately (now)'}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={effectiveDate}
                  onSelect={handleDateChange}
                  disabled={(date) => date < new Date(new Date().setHours(0, 0, 0, 0))}
                />
                {effectiveDate && (
                  <div className="border-t p-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full"
                      onClick={() => handleDateChange(undefined)}
                    >
                      Clear (use now)
                    </Button>
                  </div>
                )}
              </PopoverContent>
            </Popover>
            <p className="text-xs text-muted-foreground">
              Leave empty to apply the change immediately
            </p>
          </div>

          {/* Price Comparison */}
          {selectedPlanId && currentPlan && newPlan && (
            <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
              <p className="text-sm font-medium">Price Comparison</p>
              <div className="flex items-center gap-3">
                <div className="flex-1 rounded-md border bg-background p-3 text-center">
                  <p className="text-xs text-muted-foreground mb-1">Current</p>
                  <p className="font-semibold">{currentPlan.name}</p>
                  <p className="text-lg font-mono">
                    {formatCents(currentPlan.amount_cents, currentPlan.currency)}
                  </p>
                  <p className="text-xs text-muted-foreground">/{currentPlan.interval}</p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                <div className="flex-1 rounded-md border bg-background p-3 text-center">
                  <p className="text-xs text-muted-foreground mb-1">New</p>
                  <p className="font-semibold">{newPlan.name}</p>
                  <p className="text-lg font-mono">
                    {formatCents(newPlan.amount_cents, newPlan.currency)}
                  </p>
                  <p className="text-xs text-muted-foreground">/{newPlan.interval}</p>
                </div>
              </div>
              {/* Price difference indicator */}
              {(() => {
                const diff = newPlan.amount_cents - currentPlan.amount_cents
                if (diff === 0) return (
                  <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <Minus className="h-3.5 w-3.5" />
                    Same base price
                  </div>
                )
                return (
                  <div className={`flex items-center gap-1.5 text-sm ${diff > 0 ? 'text-orange-600' : 'text-green-600'}`}>
                    {diff > 0 ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                    {diff > 0 ? 'Upgrade' : 'Downgrade'}: {diff > 0 ? '+' : ''}{formatCents(diff, newPlan.currency)}/{newPlan.interval}
                  </div>
                )
              })()}
            </div>
          )}

          {/* Proration Preview */}
          {previewLoading && (
            <div className="rounded-lg border p-4">
              <div className="space-y-2 animate-pulse">
                <div className="h-4 w-32 bg-muted rounded" />
                <div className="h-3 w-full bg-muted rounded" />
                <div className="h-3 w-3/4 bg-muted rounded" />
              </div>
            </div>
          )}
          {preview && !previewLoading && (
            <div className="rounded-lg border p-4 space-y-2">
              <p className="text-sm font-medium">Proration Preview</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <span className="text-muted-foreground">Days remaining in period</span>
                <span className="text-right font-mono">
                  {preview.proration.days_remaining} / {preview.proration.total_days}
                </span>
                <span className="text-muted-foreground">Credit for current plan</span>
                <span className="text-right font-mono text-green-600">
                  -{formatCents(preview.proration.current_plan_credit_cents, preview.current_plan.currency)}
                </span>
                <span className="text-muted-foreground">Charge for new plan</span>
                <span className="text-right font-mono">
                  +{formatCents(preview.proration.new_plan_charge_cents, preview.new_plan.currency)}
                </span>
              </div>
              <div className="border-t pt-2 mt-2 flex justify-between text-sm font-medium">
                <span>Net adjustment</span>
                <span className={`font-mono ${preview.proration.net_amount_cents > 0 ? 'text-orange-600' : preview.proration.net_amount_cents < 0 ? 'text-green-600' : ''}`}>
                  {preview.proration.net_amount_cents >= 0 ? '+' : ''}{formatCents(preview.proration.net_amount_cents, preview.current_plan.currency)}
                </span>
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>Cancel</Button>
          <Button
            disabled={!selectedPlanId || isLoading}
            onClick={() => onSubmit(subscription.id, selectedPlanId, effectiveDate?.toISOString())}
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

  // Fetch subscriptions from API
  const { data, isLoading, error } = useQuery({
    queryKey: ['subscriptions', page, pageSize],
    queryFn: () => subscriptionsApi.listPaginated({ skip: (page - 1) * pageSize, limit: pageSize }),
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
            <SelectItem value="paused">Paused</SelectItem>
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
              <TableHead>Next Billing</TableHead>
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
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                </TableRow>
              ))
            ) : filteredSubscriptions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="h-24 text-center">
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
                          {plan ? `${formatCents(plan.amount_cents, plan.currency)}/${plan.interval}` : '\u2014'}
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
                      <NextBillingCell sub={sub} />
                    </TableCell>
                    <TableCell>
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
