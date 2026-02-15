import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, MoreHorizontal, Pencil, Trash2, Calendar, Layers, Settings, Target, Users } from 'lucide-react'
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
import { Separator } from '@/components/ui/separator'
import { plansApi, billableMetricsApi, commitmentsApi, usageThresholdsApi, ApiError } from '@/lib/api'
import type { Plan, PlanCreate, PlanUpdate, PlanInterval, ChargeModel, ChargeInput, BillableMetric, Commitment, CommitmentCreateAPI, CommitmentUpdate, UsageThreshold, UsageThresholdCreateAPI } from '@/types/billing'

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
}

function PlanFormDialog({
  open,
  onOpenChange,
  plan,
  metrics,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  plan?: Plan | null
  metrics: BillableMetric[]
  onSubmit: (data: PlanCreate | PlanUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<{
    code: string
    name: string
    description: string
    amount_cents: number
    currency: string
    interval: PlanInterval
    trial_period_days: number
    charges: ChargeFormData[]
  }>({
    code: plan?.code ?? '',
    name: plan?.name ?? '',
    description: plan?.description ?? '',
    amount_cents: plan?.amount_cents ?? 0,
    currency: plan?.currency ?? 'USD',
    interval: plan?.interval ?? 'monthly',
    trial_period_days: plan?.trial_period_days ?? 0,
    charges: plan?.charges?.map((c) => ({
      billable_metric_id: c.billable_metric_id,
      charge_model: c.charge_model,
    })) ?? [],
  })

  const addCharge = () => {
    setFormData({
      ...formData,
      charges: [
        ...formData.charges,
        { billable_metric_id: '', charge_model: 'standard' },
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
    const charges: ChargeInput[] = formData.charges
      .filter((c) => c.billable_metric_id)
      .map((c) => ({
        billable_metric_id: c.billable_metric_id,
        charge_model: c.charge_model,
        properties: {},
      }))

    const data: PlanCreate = {
      code: formData.code,
      name: formData.name,
      description: formData.description || undefined,
      amount_cents: formData.amount_cents,
      currency: formData.currency,
      interval: formData.interval,
      trial_period_days: formData.trial_period_days,
      charges,
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
                  {formatCurrency(formData.amount_cents, formData.currency)}
                </p>
              </div>
              <div className="space-y-2">
                <Label>Currency</Label>
                <Select
                  value={formData.currency}
                  onValueChange={(value) =>
                    setFormData({ ...formData, currency: value })
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

            <div className="space-y-2">
              <Label htmlFor="trial">Trial Period (days)</Label>
              <Input
                id="trial"
                type="number"
                value={formData.trial_period_days}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    trial_period_days: parseInt(e.target.value) || 0,
                  })
                }
                placeholder="14"
              />
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
                            {metrics.map((m) => (
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
                            <SelectItem value="percentage">Percentage</SelectItem>
                          </SelectContent>
                        </Select>
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

function PlanManageDialog({
  open,
  onOpenChange,
  plan,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  plan: Plan | null
}) {
  const queryClient = useQueryClient()

  // Commitments state
  const [showAddCommitment, setShowAddCommitment] = useState(false)
  const [editingCommitment, setEditingCommitment] = useState<Commitment | null>(null)
  const [deleteCommitment, setDeleteCommitment] = useState<Commitment | null>(null)
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
  const [deleteThreshold, setDeleteThreshold] = useState<UsageThreshold | null>(null)

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

  // Commitment mutations
  const createCommitmentMutation = useMutation({
    mutationFn: (data: CommitmentCreateAPI) =>
      commitmentsApi.createForPlan(plan!.code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['commitments', plan?.code] })
      setShowAddCommitment(false)
      setCommitmentForm({ commitment_type: 'minimum_commitment', amount_cents: '', invoice_display_name: '' })
      toast.success('Commitment created successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create commitment'
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
      const message = error instanceof ApiError ? error.message : 'Failed to update commitment'
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
      const message = error instanceof ApiError ? error.message : 'Failed to delete commitment'
      toast.error(message)
    },
  })

  // Usage threshold mutations
  const createThresholdMutation = useMutation({
    mutationFn: (data: UsageThresholdCreateAPI) =>
      usageThresholdsApi.createForPlan(plan!.code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plan-thresholds', plan?.code] })
      setThresholdForm({ amount_cents: '', currency: 'USD', recurring: false, threshold_display_name: '' })
      toast.success('Usage threshold created')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create usage threshold'
      toast.error(message)
    },
  })

  const deleteThresholdMutation = useMutation({
    mutationFn: (id: string) => usageThresholdsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plan-thresholds', plan?.code] })
      setDeleteThreshold(null)
      toast.success('Usage threshold deleted')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete usage threshold'
      toast.error(message)
    },
  })

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
      threshold_display_name: thresholdForm.threshold_display_name || undefined,
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
    setCommitmentForm({ commitment_type: 'minimum_commitment', amount_cents: '', invoice_display_name: '' })
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-[650px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Manage Plan: {plan?.name}
            </DialogTitle>
            <DialogDescription>
              Configure commitments and usage thresholds for this plan
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Commitments Section */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium flex items-center gap-2">
                    <Target className="h-4 w-4" />
                    Commitments
                  </h4>
                  <p className="text-sm text-muted-foreground">
                    Minimum spend requirements for this plan
                  </p>
                </div>
                {!showAddCommitment && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setShowAddCommitment(true)
                      setCommitmentForm({ commitment_type: 'minimum_commitment', amount_cents: '', invoice_display_name: '' })
                    }}
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    Add Commitment
                  </Button>
                )}
              </div>

              {/* Commitments Table */}
              {commitmentsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : commitments && commitments.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="text-left p-2 font-medium">Type</th>
                        <th className="text-left p-2 font-medium">Amount</th>
                        <th className="text-left p-2 font-medium">Display Name</th>
                        <th className="text-right p-2 font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {commitments.map((c) =>
                        editingCommitment?.id === c.id ? (
                          <tr key={c.id} className="border-b">
                            <td colSpan={4} className="p-2">
                              <form onSubmit={handleUpdateCommitment} className="flex items-end gap-2">
                                <div className="space-y-1">
                                  <Label className="text-xs">Type</Label>
                                  <Select
                                    value={commitmentForm.commitment_type}
                                    onValueChange={(value) =>
                                      setCommitmentForm({ ...commitmentForm, commitment_type: value })
                                    }
                                  >
                                    <SelectTrigger className="w-[180px]">
                                      <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                      <SelectItem value="minimum_commitment">Minimum Commitment</SelectItem>
                                    </SelectContent>
                                  </Select>
                                </div>
                                <div className="space-y-1">
                                  <Label className="text-xs">Amount (cents)</Label>
                                  <Input
                                    type="number"
                                    value={commitmentForm.amount_cents}
                                    onChange={(e) =>
                                      setCommitmentForm({ ...commitmentForm, amount_cents: e.target.value })
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
                                      setCommitmentForm({ ...commitmentForm, invoice_display_name: e.target.value })
                                    }
                                    className="w-[140px]"
                                  />
                                </div>
                                <Button type="submit" size="sm" disabled={updateCommitmentMutation.isPending}>
                                  {updateCommitmentMutation.isPending ? 'Saving...' : 'Save'}
                                </Button>
                                <Button type="button" size="sm" variant="outline" onClick={cancelEditCommitment}>
                                  Cancel
                                </Button>
                              </form>
                            </td>
                          </tr>
                        ) : (
                          <tr key={c.id} className="border-b last:border-b-0">
                            <td className="p-2">
                              <Badge variant="outline">{c.commitment_type}</Badge>
                            </td>
                            <td className="p-2">{formatCurrency(parseInt(c.amount_cents))}</td>
                            <td className="p-2 text-muted-foreground">{c.invoice_display_name || '\u2014'}</td>
                            <td className="p-2 text-right">
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7"
                                  onClick={() => startEditCommitment(c)}
                                >
                                  <Pencil className="h-3 w-3" />
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon"
                                  className="h-7 w-7 text-destructive"
                                  onClick={() => setDeleteCommitment(c)}
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            </td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-4 text-muted-foreground text-sm border border-dashed rounded-lg">
                  No commitments configured for this plan.
                </div>
              )}

              {/* Add Commitment Inline Form */}
              {showAddCommitment && (
                <form onSubmit={handleCreateCommitment} className="border rounded-lg p-3 bg-muted/50 space-y-3">
                  <div className="flex items-end gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Commitment Type</Label>
                      <Select
                        value={commitmentForm.commitment_type}
                        onValueChange={(value) =>
                          setCommitmentForm({ ...commitmentForm, commitment_type: value })
                        }
                      >
                        <SelectTrigger className="w-[180px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="minimum_commitment">Minimum Commitment</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Amount (cents) *</Label>
                      <Input
                        type="number"
                        value={commitmentForm.amount_cents}
                        onChange={(e) =>
                          setCommitmentForm({ ...commitmentForm, amount_cents: e.target.value })
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
                          setCommitmentForm({ ...commitmentForm, invoice_display_name: e.target.value })
                        }
                        className="w-[140px]"
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button type="submit" size="sm" disabled={createCommitmentMutation.isPending}>
                      {createCommitmentMutation.isPending ? 'Creating...' : 'Submit'}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setShowAddCommitment(false)
                        setCommitmentForm({ commitment_type: 'minimum_commitment', amount_cents: '', invoice_display_name: '' })
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              )}
            </div>

            <Separator />

            {/* Usage Thresholds Section */}
            <div className="space-y-4">
              <div>
                <h4 className="font-medium flex items-center gap-2">
                  <Target className="h-4 w-4" />
                  Usage Thresholds
                </h4>
                <p className="text-sm text-muted-foreground">
                  Thresholds trigger progressive billing when usage reaches the specified amount.
                </p>
              </div>

              {/* Existing Thresholds Table */}
              {thresholdsLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : thresholds && thresholds.length > 0 ? (
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="text-left p-2 font-medium">Amount</th>
                        <th className="text-left p-2 font-medium">Currency</th>
                        <th className="text-left p-2 font-medium">Recurring</th>
                        <th className="text-left p-2 font-medium">Display Name</th>
                        <th className="text-right p-2 font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {thresholds.map((t) => (
                        <tr key={t.id} className="border-b last:border-b-0">
                          <td className="p-2">{formatCurrency(parseInt(t.amount_cents))}</td>
                          <td className="p-2">{t.currency}</td>
                          <td className="p-2">{t.recurring ? 'Yes' : 'No'}</td>
                          <td className="p-2 text-muted-foreground">{t.threshold_display_name || '\u2014'}</td>
                          <td className="p-2 text-right">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-destructive"
                              onClick={() => setDeleteThreshold(t)}
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
                  No usage thresholds configured for this plan.
                </div>
              )}

              {/* Add Threshold Form */}
              <form onSubmit={handleCreateThreshold} className="border rounded-lg p-3 bg-muted/50 space-y-3">
                <p className="text-xs font-medium">Add Usage Threshold</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label className="text-xs">Amount (cents) *</Label>
                    <Input
                      type="number"
                      value={thresholdForm.amount_cents}
                      onChange={(e) =>
                        setThresholdForm({ ...thresholdForm, amount_cents: e.target.value })
                      }
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Currency</Label>
                    <Select
                      value={thresholdForm.currency}
                      onValueChange={(value) =>
                        setThresholdForm({ ...thresholdForm, currency: value })
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
                      setThresholdForm({ ...thresholdForm, threshold_display_name: e.target.value })
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
                      setThresholdForm({ ...thresholdForm, recurring: e.target.checked })
                    }
                  />
                  <Label htmlFor="threshold-recurring" className="text-sm">Recurring</Label>
                </div>
                <Button type="submit" size="sm" disabled={createThresholdMutation.isPending}>
                  {createThresholdMutation.isPending ? 'Creating...' : 'Add Threshold'}
                </Button>
              </form>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Commitment Confirmation */}
      <AlertDialog
        open={!!deleteCommitment}
        onOpenChange={(open) => !open && setDeleteCommitment(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Commitment</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this commitment? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteCommitment && deleteCommitmentMutation.mutate(deleteCommitment.id)}
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
              Are you sure you want to delete this usage threshold? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteThreshold && deleteThresholdMutation.mutate(deleteThreshold.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteThresholdMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

export default function PlansPage() {
  const queryClient = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null)
  const [deletePlan, setDeletePlan] = useState<Plan | null>(null)
  const [managePlan, setManagePlan] = useState<Plan | null>(null)

  // Fetch plans from API
  const { data: plans, isLoading, error } = useQuery({
    queryKey: ['plans'],
    queryFn: () => plansApi.list(),
  })

  // Fetch metrics for the form
  const { data: metrics } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: () => billableMetricsApi.list(),
  })

  // Fetch subscription counts per plan
  const { data: subscriptionCounts } = useQuery({
    queryKey: ['plan-subscription-counts'],
    queryFn: () => plansApi.subscriptionCounts(),
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: PlanCreate) => plansApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      setFormOpen(false)
      toast.success('Plan created successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create plan'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: PlanUpdate }) =>
      plansApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      setEditingPlan(null)
      setFormOpen(false)
      toast.success('Plan updated successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update plan'
      toast.error(message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => plansApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      setDeletePlan(null)
      toast.success('Plan deleted successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete plan'
      toast.error(message)
    },
  })

  const handleSubmit = (data: PlanCreate | PlanUpdate) => {
    if (editingPlan) {
      updateMutation.mutate({ id: editingPlan.id, data })
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

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load plans. Please try again.</p>
      </div>
    )
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
      ) : !plans || plans.length === 0 ? (
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
          {plans.map((plan) => (
            <Card key={plan.id} className="hover:border-primary/50 transition-colors">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <Link to={`/admin/plans/${plan.id}`} className="min-w-0">
                    <CardTitle className="hover:underline">{plan.name}</CardTitle>
                    <code className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                      {plan.code}
                    </code>
                  </Link>
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
                      <DropdownMenuItem onClick={() => setManagePlan(plan)}>
                        <Settings className="mr-2 h-4 w-4" />
                        Manage
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
                    {formatCurrency(plan.amount_cents, plan.currency)}
                  </span>
                  <span className="text-muted-foreground">
                    /{intervalLabel(plan.interval)}
                  </span>
                </div>

                {/* Stats */}
                <div className="flex items-center gap-4 text-sm">
                  {plan.trial_period_days > 0 && (
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Calendar className="h-4 w-4" />
                      {plan.trial_period_days}d trial
                    </div>
                  )}
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Users className="h-4 w-4" />
                    {subscriptionCounts?.[plan.id] ?? 0} subscription{(subscriptionCounts?.[plan.id] ?? 0) !== 1 ? 's' : ''}
                  </div>
                </div>

                {/* Charges */}
                {plan.charges && plan.charges.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Usage Charges ({plan.charges.length})
                    </p>
                    <div className="space-y-1">
                      {plan.charges.map((charge) => (
                        <div
                          key={charge.id}
                          className="flex items-center justify-between text-sm"
                        >
                          <span className="text-muted-foreground truncate max-w-[150px]">
                            {charge.billable_metric_id.slice(0, 8)}...
                          </span>
                          <div className="flex items-center gap-1">
                            {charge.properties && Object.keys(charge.properties).length > 0 && (
                              <Badge variant="outline" className="text-xs px-1">
                                {Object.keys(charge.properties).length} prop{Object.keys(charge.properties).length > 1 ? 's' : ''}
                              </Badge>
                            )}
                            <ChargeModelBadge model={charge.charge_model} />
                          </div>
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
        metrics={metrics ?? []}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Manage Plan Dialog */}
      <PlanManageDialog
        open={!!managePlan}
        onOpenChange={(open) => !open && setManagePlan(null)}
        plan={managePlan}
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
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deletePlan && deleteMutation.mutate(deletePlan.id)}
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
