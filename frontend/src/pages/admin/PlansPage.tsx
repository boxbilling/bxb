import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, MoreHorizontal, Pencil, Trash2, Users, DollarSign, Calendar, Layers } from 'lucide-react'
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
import { Checkbox } from '@/components/ui/checkbox'
import { Separator } from '@/components/ui/separator'
import type { Plan, PlanCreate, PlanUpdate, PlanInterval, Charge, ChargeCreate, ChargeModel, BillableMetric } from '@/types/billing'

// Mock data
const mockPlans: Plan[] = [
  {
    id: '1',
    code: 'starter',
    name: 'Starter',
    description: 'Perfect for small teams getting started',
    amount_cents: 2900,
    amount_currency: 'USD',
    interval: 'monthly',
    pay_in_advance: true,
    trial_period_days: 14,
    charges: [
      {
        id: 'c1',
        billable_metric_id: '1',
        billable_metric: { id: '1', code: 'api_requests', name: 'API Requests', description: null, aggregation_type: 'count', field_name: null, recurring: false, created_at: '', updated_at: '' },
        charge_model: 'standard',
        amount: '0.001',
        properties: {},
        min_amount_cents: null,
        created_at: '',
        updated_at: '',
      },
    ],
    active_subscriptions_count: 45,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: '2',
    code: 'pro',
    name: 'Professional',
    description: 'For growing businesses with advanced needs',
    amount_cents: 9900,
    amount_currency: 'USD',
    interval: 'monthly',
    pay_in_advance: true,
    trial_period_days: null,
    charges: [
      {
        id: 'c2',
        billable_metric_id: '1',
        billable_metric: { id: '1', code: 'api_requests', name: 'API Requests', description: null, aggregation_type: 'count', field_name: null, recurring: false, created_at: '', updated_at: '' },
        charge_model: 'graduated',
        amount: null,
        properties: {
          graduated_tiers: [
            { from_value: 0, to_value: 10000, per_unit_amount: '0', flat_amount: '0' },
            { from_value: 10001, to_value: 100000, per_unit_amount: '0.0005', flat_amount: '0' },
            { from_value: 100001, to_value: null, per_unit_amount: '0.0003', flat_amount: '0' },
          ],
        },
        min_amount_cents: null,
        created_at: '',
        updated_at: '',
      },
      {
        id: 'c3',
        billable_metric_id: '2',
        billable_metric: { id: '2', code: 'storage_gb', name: 'Storage Usage', description: null, aggregation_type: 'max', field_name: 'gb_used', recurring: true, created_at: '', updated_at: '' },
        charge_model: 'standard',
        amount: '0.10',
        properties: {},
        min_amount_cents: null,
        created_at: '',
        updated_at: '',
      },
    ],
    active_subscriptions_count: 128,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: '3',
    code: 'enterprise',
    name: 'Enterprise',
    description: 'Custom solutions for large organizations',
    amount_cents: 49900,
    amount_currency: 'USD',
    interval: 'monthly',
    pay_in_advance: true,
    trial_period_days: null,
    charges: [],
    active_subscriptions_count: 12,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
]

const mockMetrics: BillableMetric[] = [
  { id: '1', code: 'api_requests', name: 'API Requests', description: null, aggregation_type: 'count', field_name: null, recurring: false, created_at: '', updated_at: '' },
  { id: '2', code: 'storage_gb', name: 'Storage Usage', description: null, aggregation_type: 'max', field_name: 'gb_used', recurring: true, created_at: '', updated_at: '' },
  { id: '3', code: 'active_users', name: 'Active Users', description: null, aggregation_type: 'unique_count', field_name: 'user_id', recurring: false, created_at: '', updated_at: '' },
]

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}

function intervalLabel(interval: PlanInterval) {
  return {
    weekly: 'week',
    monthly: 'month',
    quarterly: 'quarter',
    yearly: 'year',
  }[interval]
}

function ChargeModelBadge({ model }: { model: ChargeModel }) {
  const colors = {
    standard: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
    graduated: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
    volume: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
    package: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300',
    percentage: 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-300',
  }

  return (
    <Badge variant="outline" className={colors[model]}>
      {model}
    </Badge>
  )
}

interface ChargeFormData {
  billable_metric_id: string
  charge_model: ChargeModel
  amount: string
}

function PlanFormDialog({
  open,
  onOpenChange,
  plan,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  plan?: Plan | null
  onSubmit: (data: PlanCreate | PlanUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<{
    code: string
    name: string
    description: string
    amount_cents: number
    amount_currency: string
    interval: PlanInterval
    pay_in_advance: boolean
    trial_period_days: number | null
    charges: ChargeFormData[]
  }>({
    code: plan?.code ?? '',
    name: plan?.name ?? '',
    description: plan?.description ?? '',
    amount_cents: plan?.amount_cents ?? 0,
    amount_currency: plan?.amount_currency ?? 'USD',
    interval: plan?.interval ?? 'monthly',
    pay_in_advance: plan?.pay_in_advance ?? true,
    trial_period_days: plan?.trial_period_days ?? null,
    charges: plan?.charges.map((c) => ({
      billable_metric_id: c.billable_metric_id,
      charge_model: c.charge_model,
      amount: c.amount ?? '',
    })) ?? [],
  })

  const addCharge = () => {
    setFormData({
      ...formData,
      charges: [
        ...formData.charges,
        { billable_metric_id: '', charge_model: 'standard', amount: '0' },
      ],
    })
  }

  const removeCharge = (index: number) => {
    setFormData({
      ...formData,
      charges: formData.charges.filter((_, i) => i !== index),
    })
  }

  const updateCharge = (index: number, updates: Partial<ChargeFormData>) => {
    setFormData({
      ...formData,
      charges: formData.charges.map((c, i) =>
        i === index ? { ...c, ...updates } : c
      ),
    })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const data: PlanCreate = {
      code: formData.code,
      name: formData.name,
      description: formData.description || undefined,
      amount_cents: formData.amount_cents,
      amount_currency: formData.amount_currency,
      interval: formData.interval,
      pay_in_advance: formData.pay_in_advance,
      trial_period_days: formData.trial_period_days,
      charges: formData.charges.map((c) => ({
        billable_metric_id: c.billable_metric_id,
        charge_model: c.charge_model,
        amount: c.amount || undefined,
      })),
    }
    onSubmit(data)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{plan ? 'Edit Plan' : 'Create Plan'}</DialogTitle>
            <DialogDescription>
              {plan ? 'Update plan details' : 'Create a new pricing plan'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {/* Basic Info */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="code">Code *</Label>
                <Input
                  id="code"
                  value={formData.code}
                  onChange={(e) =>
                    setFormData({ ...formData, code: e.target.value })
                  }
                  placeholder="pro_monthly"
                  required
                  disabled={!!plan}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="Professional"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="For growing businesses"
              />
            </div>

            {/* Pricing */}
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="amount">Base Price (cents) *</Label>
                <Input
                  id="amount"
                  type="number"
                  value={formData.amount_cents}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      amount_cents: parseInt(e.target.value) || 0,
                    })
                  }
                  required
                />
                <p className="text-xs text-muted-foreground">
                  {formatCurrency(formData.amount_cents, formData.amount_currency)}
                </p>
              </div>
              <div className="space-y-2">
                <Label>Currency</Label>
                <Select
                  value={formData.amount_currency}
                  onValueChange={(value) =>
                    setFormData({ ...formData, amount_currency: value })
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
              <div className="space-y-2">
                <Label>Interval</Label>
                <Select
                  value={formData.interval}
                  onValueChange={(value: PlanInterval) =>
                    setFormData({ ...formData, interval: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                    <SelectItem value="quarterly">Quarterly</SelectItem>
                    <SelectItem value="yearly">Yearly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="pay_in_advance"
                  checked={formData.pay_in_advance}
                  onCheckedChange={(checked) =>
                    setFormData({ ...formData, pay_in_advance: checked as boolean })
                  }
                />
                <Label htmlFor="pay_in_advance">Pay in advance</Label>
              </div>
              <div className="space-y-2">
                <Label htmlFor="trial">Trial Period (days)</Label>
                <Input
                  id="trial"
                  type="number"
                  value={formData.trial_period_days ?? ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      trial_period_days: e.target.value
                        ? parseInt(e.target.value)
                        : null,
                    })
                  }
                  placeholder="14"
                />
              </div>
            </div>

            {/* Charges */}
            <Separator />
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">Usage Charges</h4>
                  <p className="text-sm text-muted-foreground">
                    Add usage-based charges on top of the base price
                  </p>
                </div>
                <Button type="button" variant="outline" size="sm" onClick={addCharge}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Charge
                </Button>
              </div>

              {formData.charges.length === 0 ? (
                <div className="text-center py-4 text-muted-foreground text-sm border border-dashed rounded-lg">
                  No usage charges. Click "Add Charge" to add metered billing.
                </div>
              ) : (
                <div className="space-y-3">
                  {formData.charges.map((charge, index) => (
                    <div
                      key={index}
                      className="flex items-end gap-3 p-3 border rounded-lg bg-muted/50"
                    >
                      <div className="flex-1 space-y-2">
                        <Label>Billable Metric</Label>
                        <Select
                          value={charge.billable_metric_id}
                          onValueChange={(value) =>
                            updateCharge(index, { billable_metric_id: value })
                          }
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select metric" />
                          </SelectTrigger>
                          <SelectContent>
                            {mockMetrics.map((m) => (
                              <SelectItem key={m.id} value={m.id}>
                                {m.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="w-32 space-y-2">
                        <Label>Model</Label>
                        <Select
                          value={charge.charge_model}
                          onValueChange={(value: ChargeModel) =>
                            updateCharge(index, { charge_model: value })
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="standard">Standard</SelectItem>
                            <SelectItem value="graduated">Graduated</SelectItem>
                            <SelectItem value="volume">Volume</SelectItem>
                            <SelectItem value="package">Package</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="w-24 space-y-2">
                        <Label>Amount</Label>
                        <Input
                          value={charge.amount}
                          onChange={(e) =>
                            updateCharge(index, { amount: e.target.value })
                          }
                          placeholder="0.01"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeCharge(index)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
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
              {isLoading ? 'Saving...' : plan ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function PlansPage() {
  const queryClient = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null)
  const [deletePlan, setDeletePlan] = useState<Plan | null>(null)

  // Fetch plans
  const { data, isLoading } = useQuery({
    queryKey: ['plans'],
    queryFn: async () => {
      await new Promise((r) => setTimeout(r, 500))
      return {
        data: mockPlans,
        meta: { total: mockPlans.length, page: 1, per_page: 10, total_pages: 1 },
      }
    },
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: async (data: PlanCreate) => {
      await new Promise((r) => setTimeout(r, 500))
      return { ...data, id: String(Date.now()) } as Plan
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      setFormOpen(false)
      toast.success('Plan created successfully')
    },
    onError: () => {
      toast.error('Failed to create plan')
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async ({ code, data }: { code: string; data: PlanUpdate }) => {
      await new Promise((r) => setTimeout(r, 500))
      return { code, ...data } as Plan
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      setEditingPlan(null)
      setFormOpen(false)
      toast.success('Plan updated successfully')
    },
    onError: () => {
      toast.error('Failed to update plan')
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (code: string) => {
      await new Promise((r) => setTimeout(r, 500))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      setDeletePlan(null)
      toast.success('Plan deleted successfully')
    },
    onError: () => {
      toast.error('Failed to delete plan')
    },
  })

  const handleSubmit = (data: PlanCreate | PlanUpdate) => {
    if (editingPlan) {
      updateMutation.mutate({ code: editingPlan.code, data })
    } else {
      createMutation.mutate(data as PlanCreate)
    }
  }

  const handleEdit = (plan: Plan) => {
    setEditingPlan(plan)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingPlan(null)
    }
    setFormOpen(open)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Plans</h2>
          <p className="text-muted-foreground">
            Create and manage pricing plans for your customers
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Plan
        </Button>
      </div>

      {/* Plans Grid */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-4 w-48" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : data?.data.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Layers className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No plans yet</h3>
            <p className="text-muted-foreground text-center max-w-sm mt-1">
              Create your first pricing plan to start billing customers
            </p>
            <Button onClick={() => setFormOpen(true)} className="mt-4">
              <Plus className="mr-2 h-4 w-4" />
              Create Plan
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data?.data.map((plan) => (
            <Card key={plan.id}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle>{plan.name}</CardTitle>
                    <code className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                      {plan.code}
                    </code>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => handleEdit(plan)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => setDeletePlan(plan)}
                        className="text-destructive"
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
                {plan.description && (
                  <CardDescription>{plan.description}</CardDescription>
                )}
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Price */}
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-bold">
                    {formatCurrency(plan.amount_cents, plan.amount_currency)}
                  </span>
                  <span className="text-muted-foreground">
                    /{intervalLabel(plan.interval)}
                  </span>
                </div>

                {/* Stats */}
                <div className="flex items-center gap-4 text-sm">
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Users className="h-4 w-4" />
                    {plan.active_subscriptions_count} active
                  </div>
                  {plan.trial_period_days && (
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Calendar className="h-4 w-4" />
                      {plan.trial_period_days}d trial
                    </div>
                  )}
                </div>

                {/* Charges */}
                {plan.charges.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Usage Charges
                    </p>
                    <div className="space-y-1">
                      {plan.charges.map((charge) => (
                        <div
                          key={charge.id}
                          className="flex items-center justify-between text-sm"
                        >
                          <span>{charge.billable_metric?.name}</span>
                          <ChargeModelBadge model={charge.charge_model} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Dialog */}
      <PlanFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        plan={editingPlan}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deletePlan}
        onOpenChange={(open) => !open && setDeletePlan(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Plan</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deletePlan?.name}"?
              {deletePlan?.active_subscriptions_count
                ? ` This plan has ${deletePlan.active_subscriptions_count} active subscriptions.`
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deletePlan && deleteMutation.mutate(deletePlan.code)}
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
