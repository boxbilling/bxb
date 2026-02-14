import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, MoreHorizontal, XCircle, ExternalLink, Trash2, Target, TrendingUp, Calendar } from 'lucide-react'
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
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { subscriptionsApi, customersApi, plansApi, usageThresholdsApi, ApiError } from '@/lib/api'
import type { Subscription, SubscriptionCreate, SubscriptionStatus, Customer, Plan, CurrentUsage, UsageThreshold, UsageThresholdCreateAPI } from '@/types/billing'

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

function SubscriptionFormDialog({
  open,
  onOpenChange,
  customers,
  plans,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  customers: Customer[]
  plans: Plan[]
  onSubmit: (data: SubscriptionCreate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<SubscriptionCreate>({
    external_id: '',
    customer_id: '',
    plan_id: '',
    billing_time: 'calendar',
    trial_period_days: 0,
    pay_in_advance: false,
    on_termination_action: 'generate_invoice',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create Subscription</DialogTitle>
            <DialogDescription>
              Subscribe a customer to a plan
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="external_id">External ID *</Label>
              <Input
                id="external_id"
                value={formData.external_id}
                onChange={(e) =>
                  setFormData({ ...formData, external_id: e.target.value })
                }
                placeholder="sub_123"
                required
              />
            </div>

            <div className="space-y-2">
              <Label>Customer *</Label>
              <Select
                value={formData.customer_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, customer_id: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a customer" />
                </SelectTrigger>
                <SelectContent>
                  {customers.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Plan *</Label>
              <Select
                value={formData.plan_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, plan_id: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a plan" />
                </SelectTrigger>
                <SelectContent>
                  {plans.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} — {formatCurrency(p.amount_cents, p.currency)}/{p.interval}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
              {isLoading ? 'Creating...' : 'Create Subscription'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function SubscriptionDetailSheet({
  open,
  onOpenChange,
  subscription,
  customerName,
  planName,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscription: Subscription | null
  customerName: string
  planName: string
}) {
  const queryClient = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [thresholdForm, setThresholdForm] = useState<UsageThresholdCreateAPI>({
    amount_cents: '',
    currency: 'USD',
    recurring: false,
    threshold_display_name: null,
  })

  const { data: usage, isLoading: usageLoading, isError: usageError } = useQuery({
    queryKey: ['current-usage', subscription?.id],
    queryFn: () => usageThresholdsApi.getCurrentUsage(subscription!.id),
    enabled: !!subscription?.id,
  })

  const { data: thresholds, isLoading: thresholdsLoading } = useQuery({
    queryKey: ['usage-thresholds', subscription?.id],
    queryFn: () => usageThresholdsApi.listForSubscription(subscription!.id),
    enabled: !!subscription?.id,
  })

  const deleteMutation = useMutation({
    mutationFn: (thresholdId: string) => usageThresholdsApi.delete(thresholdId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-thresholds', subscription?.id] })
      toast.success('Threshold deleted')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete threshold'
      toast.error(message)
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: UsageThresholdCreateAPI) =>
      usageThresholdsApi.createForSubscription(subscription!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-thresholds', subscription?.id] })
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

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Subscription Details</SheetTitle>
          <SheetDescription>
            {customerName} — {planName}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-6 px-4 pb-4">
          {/* Current Usage Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
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
                  <p className="text-3xl font-bold">
                    {formatCurrency(parseInt(usage.current_usage_amount_cents))}
                  </p>
                  <p className="text-sm text-muted-foreground flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    Billing Period: {format(new Date(usage.billing_period_start), 'MMM d, yyyy')} — {format(new Date(usage.billing_period_end), 'MMM d, yyyy')}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          <Separator />

          {/* Usage Thresholds Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold flex items-center gap-2">
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
                        <TableCell>
                          {formatCurrency(parseInt(t.amount_cents), t.currency)}
                        </TableCell>
                        <TableCell>
                          <Badge variant={t.recurring ? 'default' : 'secondary'}>
                            {t.recurring ? 'Yes' : 'No'}
                          </Badge>
                        </TableCell>
                        <TableCell>{t.threshold_display_name ?? '—'}</TableCell>
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
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default function SubscriptionsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)
  const [terminateSub, setTerminateSub] = useState<Subscription | null>(null)
  const [detailSub, setDetailSub] = useState<Subscription | null>(null)

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

  // Terminate mutation
  const terminateMutation = useMutation({
    mutationFn: (id: string) => subscriptionsApi.terminate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setTerminateSub(null)
      toast.success('Subscription terminated')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to terminate subscription'
      toast.error(message)
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
              <TableHead>Started</TableHead>
              <TableHead>External ID</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : filteredSubscriptions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center">
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
                          {customer?.email ?? '—'}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div>
                        <div>{plan?.name ?? 'Unknown'}</div>
                        <div className="text-xs text-muted-foreground">
                          {plan ? `${formatCurrency(plan.amount_cents, plan.currency)}/${plan.interval}` : '—'}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={sub.status} />
                    </TableCell>
                    <TableCell>
                      {sub.started_at 
                        ? format(new Date(sub.started_at), 'MMM d, yyyy')
                        : '—'}
                    </TableCell>
                    <TableCell>
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                        {sub.external_id}
                      </code>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => setDetailSub(sub)}>
                            <ExternalLink className="mr-2 h-4 w-4" />
                            View Details
                          </DropdownMenuItem>
                          {sub.status === 'active' && (
                            <DropdownMenuItem
                              onClick={() => setTerminateSub(sub)}
                              className="text-destructive"
                            >
                              <XCircle className="mr-2 h-4 w-4" />
                              Terminate
                            </DropdownMenuItem>
                          )}
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

      {/* Create Dialog */}
      <SubscriptionFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        customers={customers ?? []}
        plans={plans ?? []}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
      />

      {/* Terminate Confirmation */}
      <AlertDialog
        open={!!terminateSub}
        onOpenChange={(open) => !open && setTerminateSub(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Terminate Subscription</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to terminate this subscription? This will end access immediately.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => terminateSub && terminateMutation.mutate(terminateSub.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {terminateMutation.isPending ? 'Terminating...' : 'Terminate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Subscription Detail Sheet */}
      <SubscriptionDetailSheet
        open={!!detailSub}
        onOpenChange={(open) => !open && setDetailSub(null)}
        subscription={detailSub}
        customerName={detailSub ? (customerMap.get(detailSub.customer_id)?.name ?? 'Unknown') : ''}
        planName={detailSub ? (planMap.get(detailSub.plan_id)?.name ?? 'Unknown') : ''}
      />
    </div>
  )
}
