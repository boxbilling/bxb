import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Plus, Trash2, Target } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
import { plansApi, billableMetricsApi, commitmentsApi, usageThresholdsApi, ApiError } from '@/lib/api'
import type { PlanCreate, PlanUpdate, PlanInterval, ChargeModel, ChargeInput, Commitment, CommitmentCreateAPI, CommitmentUpdate, UsageThreshold, UsageThresholdCreateAPI } from '@/lib/api'
import { formatCents } from '@/lib/utils'

const CHARGE_MODELS: { value: ChargeModel; label: string }[] = [
  { value: 'standard', label: 'Standard' },
  { value: 'graduated', label: 'Graduated' },
  { value: 'volume', label: 'Volume' },
  { value: 'package', label: 'Package' },
  { value: 'percentage', label: 'Percentage' },
  { value: 'graduated_percentage', label: 'Graduated Percentage' },
  { value: 'custom', label: 'Custom' },
  { value: 'dynamic', label: 'Dynamic' },
]

interface ChargeFormData {
  billable_metric_id: string
  charge_model: ChargeModel
  properties: string
}

interface FormState {
  code: string
  name: string
  description: string
  amount_cents: number
  currency: string
  interval: PlanInterval
  trial_period_days: number
  charges: ChargeFormData[]
}

const defaultFormState: FormState = {
  code: '',
  name: '',
  description: '',
  amount_cents: 0,
  currency: 'USD',
  interval: 'monthly',
  trial_period_days: 0,
  charges: [],
}

export default function PlanFormPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { id } = useParams<{ id: string }>()
  const isEdit = !!id

  const [form, setForm] = useState<FormState>(defaultFormState)
  const [initialized, setInitialized] = useState(false)

  // Commitments state (edit mode only)
  const [showAddCommitment, setShowAddCommitment] = useState(false)
  const [editingCommitment, setEditingCommitment] = useState<Commitment | null>(null)
  const [deleteCommitmentTarget, setDeleteCommitmentTarget] = useState<Commitment | null>(null)
  const [commitmentForm, setCommitmentForm] = useState({
    commitment_type: 'minimum_commitment',
    amount_cents: '',
    invoice_display_name: '',
  })

  // Usage threshold state (edit mode only)
  const [thresholdForm, setThresholdForm] = useState({
    amount_cents: '',
    currency: 'USD',
    recurring: false,
    threshold_display_name: '',
  })
  const [deleteThresholdTarget, setDeleteThresholdTarget] = useState<UsageThreshold | null>(null)

  // Fetch plan for edit mode
  const { data: plan, isLoading: loadingPlan } = useQuery({
    queryKey: ['plan', id],
    queryFn: () => plansApi.get(id!),
    enabled: isEdit,
  })

  // Fetch billable metrics
  const { data: metrics } = useQuery({
    queryKey: ['billable-metrics'],
    queryFn: () => billableMetricsApi.list(),
  })

  // Fetch commitments (edit mode only)
  const { data: commitments, isLoading: commitmentsLoading } = useQuery({
    queryKey: ['commitments', plan?.code],
    queryFn: () => commitmentsApi.listForPlan(plan!.code),
    enabled: !!plan?.code,
  })

  // Fetch usage thresholds (edit mode only)
  const { data: thresholds, isLoading: thresholdsLoading } = useQuery({
    queryKey: ['plan-thresholds', plan?.code],
    queryFn: () => usageThresholdsApi.listForPlan(plan!.code),
    enabled: !!plan?.code,
  })

  // Populate form from plan data
  useEffect(() => {
    if (plan && !initialized) {
      setForm({
        code: plan.code,
        name: plan.name,
        description: plan.description ?? '',
        amount_cents: plan.amount_cents,
        currency: plan.currency,
        interval: plan.interval,
        trial_period_days: plan.trial_period_days,
        charges: plan.charges?.map((c) => ({
          billable_metric_id: c.billable_metric_id,
          charge_model: c.charge_model,
          properties: c.properties && Object.keys(c.properties).length > 0
            ? JSON.stringify(c.properties, null, 2)
            : '{}',
        })) ?? [],
      })
      setInitialized(true)
    }
  }, [plan, initialized])

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: PlanCreate) => plansApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      toast.success('Plan created successfully')
      navigate('/admin/plans')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create plan'
      toast.error(message)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: PlanUpdate }) =>
      plansApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plans'] })
      queryClient.invalidateQueries({ queryKey: ['plan', id] })
      toast.success('Plan updated successfully')
      navigate('/admin/plans')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update plan'
      toast.error(message)
    },
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
      setDeleteCommitmentTarget(null)
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
      setDeleteThresholdTarget(null)
      toast.success('Usage threshold deleted')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete usage threshold'
      toast.error(message)
    },
  })

  // Charge helpers
  const addCharge = () => {
    setForm({
      ...form,
      charges: [...form.charges, { billable_metric_id: '', charge_model: 'standard', properties: '{}' }],
    })
  }

  const removeCharge = (index: number) => {
    setForm({
      ...form,
      charges: form.charges.filter((_, i) => i !== index),
    })
  }

  const updateCharge = (index: number, updates: Partial<ChargeFormData>) => {
    setForm({
      ...form,
      charges: form.charges.map((c, i) => (i === index ? { ...c, ...updates } : c)),
    })
  }

  // Commitment helpers
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

  // Threshold helpers
  const handleCreateThreshold = (e: React.FormEvent) => {
    e.preventDefault()
    createThresholdMutation.mutate({
      amount_cents: parseInt(thresholdForm.amount_cents) || 0,
      currency: thresholdForm.currency,
      recurring: thresholdForm.recurring,
      threshold_display_name: thresholdForm.threshold_display_name || undefined,
    })
  }

  // Form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const charges: ChargeInput[] = form.charges
      .filter((c) => c.billable_metric_id)
      .map((c) => {
        let properties: Record<string, unknown> = {}
        try {
          properties = JSON.parse(c.properties)
        } catch {
          // keep empty
        }
        return {
          billable_metric_id: c.billable_metric_id,
          charge_model: c.charge_model,
          properties,
        }
      })

    if (isEdit) {
      const data: PlanUpdate = {
        name: form.name,
        description: form.description || null,
        amount_cents: form.amount_cents,
        currency: form.currency,
        trial_period_days: form.trial_period_days,
        charges,
      }
      updateMutation.mutate({ id: id!, data })
    } else {
      const data: PlanCreate = {
        code: form.code,
        name: form.name,
        description: form.description || undefined,
        amount_cents: form.amount_cents,
        currency: form.currency,
        interval: form.interval,
        trial_period_days: form.trial_period_days,
        charges,
      }
      createMutation.mutate(data)
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  if (isEdit && loadingPlan) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[600px] w-full" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/admin/plans')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">
            {isEdit ? 'Edit Plan' : 'Create Plan'}
          </h2>
          <p className="text-muted-foreground">
            {isEdit ? 'Update plan details and manage charges, commitments, and thresholds.' : 'Create a new pricing plan for your customers.'}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Card 1: Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>The plan identifier and display details.</CardDescription>
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
                    placeholder="pro_monthly"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="name">Name *</Label>
                  <Input
                    id="name"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required
                    placeholder="Professional"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="For growing businesses"
                  rows={3}
                />
              </div>
            </CardContent>
          </Card>

          {/* Card 2: Pricing & Billing */}
          <Card>
            <CardHeader>
              <CardTitle>Pricing &amp; Billing</CardTitle>
              <CardDescription>Base price, currency, and billing interval.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="amount">Amount (cents) *</Label>
                  <Input
                    id="amount"
                    type="number"
                    min={0}
                    value={form.amount_cents}
                    onChange={(e) => setForm({ ...form, amount_cents: parseInt(e.target.value) || 0 })}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    {formatCents(form.amount_cents, form.currency)}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Currency</Label>
                  <Select
                    value={form.currency}
                    onValueChange={(value) => setForm({ ...form, currency: value })}
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

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Interval</Label>
                  <Select
                    value={form.interval}
                    onValueChange={(value: PlanInterval) => setForm({ ...form, interval: value })}
                    disabled={isEdit}
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
                  {isEdit && (
                    <p className="text-xs text-muted-foreground">Interval cannot be changed after creation.</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="trial">Trial Period (days)</Label>
                  <Input
                    id="trial"
                    type="number"
                    min={0}
                    value={form.trial_period_days}
                    onChange={(e) => setForm({ ...form, trial_period_days: parseInt(e.target.value) || 0 })}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Card 3: Charges (full width) */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Usage Charges</CardTitle>
                  <CardDescription>Add usage-based charges on top of the base price.</CardDescription>
                </div>
                <Button type="button" variant="outline" size="sm" onClick={addCharge}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Charge
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {form.charges.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground text-sm border border-dashed rounded-lg">
                  No usage charges. Click "Add Charge" to add metered billing.
                </div>
              ) : (
                <div className="space-y-4">
                  {form.charges.map((charge, index) => (
                    <div
                      key={index}
                      className="p-4 border rounded-lg bg-muted/50 space-y-3"
                    >
                      <div className="flex items-start justify-between">
                        <span className="text-sm font-medium">Charge {index + 1}</span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive"
                          onClick={() => removeCharge(index)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>Billable Metric</Label>
                          <Select
                            value={charge.billable_metric_id}
                            onValueChange={(value) => updateCharge(index, { billable_metric_id: value })}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select metric" />
                            </SelectTrigger>
                            <SelectContent>
                              {(metrics ?? []).map((m) => (
                                <SelectItem key={m.id} value={m.id}>
                                  {m.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>Charge Model</Label>
                          <Select
                            value={charge.charge_model}
                            onValueChange={(value: ChargeModel) => updateCharge(index, { charge_model: value })}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {CHARGE_MODELS.map((m) => (
                                <SelectItem key={m.value} value={m.value}>
                                  {m.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label>Properties (JSON)</Label>
                        <Textarea
                          value={charge.properties}
                          onChange={(e) => updateCharge(index, { properties: e.target.value })}
                          rows={3}
                          className="font-mono text-sm"
                          placeholder="{}"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Card 4: Commitments (edit mode only, full width) */}
          {isEdit && (
            <Card className="lg:col-span-2">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Target className="h-5 w-5" />
                      Commitments
                    </CardTitle>
                    <CardDescription>Minimum spend requirements for this plan.</CardDescription>
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
              </CardHeader>
              <CardContent>
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
                              <td className="p-2">{formatCents(parseInt(c.amount_cents))}</td>
                              <td className="p-2 text-muted-foreground">{c.invoice_display_name || '\u2014'}</td>
                              <td className="p-2 text-right">
                                <div className="flex items-center justify-end gap-1">
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => startEditCommitment(c)}
                                  >
                                    Edit
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    className="text-destructive"
                                    onClick={() => setDeleteCommitmentTarget(c)}
                                  >
                                    Delete
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
                  <form onSubmit={handleCreateCommitment} className="border rounded-lg p-3 bg-muted/50 space-y-3 mt-4">
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
              </CardContent>
            </Card>
          )}

          {/* Card 5: Usage Thresholds (edit mode only, full width) */}
          {isEdit && (
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-5 w-5" />
                  Usage Thresholds
                </CardTitle>
                <CardDescription>
                  Thresholds trigger progressive billing when usage reaches the specified amount.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
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
                            <td className="p-2">{formatCents(parseInt(t.amount_cents))}</td>
                            <td className="p-2">{t.currency}</td>
                            <td className="p-2">{t.recurring ? 'Yes' : 'No'}</td>
                            <td className="p-2 text-muted-foreground">{t.threshold_display_name || '\u2014'}</td>
                            <td className="p-2 text-right">
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="text-destructive"
                                onClick={() => setDeleteThresholdTarget(t)}
                              >
                                Delete
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
                <Separator />
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
              </CardContent>
            </Card>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-4 mt-6">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate('/admin/plans')}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={isPending || !form.code || !form.name}>
            {isPending
              ? (isEdit ? 'Saving...' : 'Creating...')
              : (isEdit ? 'Save Changes' : 'Create Plan')}
          </Button>
        </div>
      </form>

      {/* Delete Commitment Confirmation */}
      <AlertDialog
        open={!!deleteCommitmentTarget}
        onOpenChange={(open) => !open && setDeleteCommitmentTarget(null)}
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
              onClick={() => deleteCommitmentTarget && deleteCommitmentMutation.mutate(deleteCommitmentTarget.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteCommitmentMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Threshold Confirmation */}
      <AlertDialog
        open={!!deleteThresholdTarget}
        onOpenChange={(open) => !open && setDeleteThresholdTarget(null)}
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
              onClick={() => deleteThresholdTarget && deleteThresholdMutation.mutate(deleteThresholdTarget.id)}
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
