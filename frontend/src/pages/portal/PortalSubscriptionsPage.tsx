import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowUpDown, Check, ChevronRight, Clock, Pause, XCircle } from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog'
import { portalApi, ApiError } from '@/lib/api'
import type { PortalSubscriptionResponse, PortalPlanResponse, PortalPlanSummary } from '@/lib/api'
import { usePortalToken } from '@/layouts/PortalLayout'

const statusConfig: Record<string, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; icon: typeof Check }> = {
  active: { label: 'Active', variant: 'default', icon: Check },
  paused: { label: 'Paused', variant: 'secondary', icon: Pause },
  canceled: { label: 'Canceled', variant: 'destructive', icon: XCircle },
  terminated: { label: 'Terminated', variant: 'destructive', icon: XCircle },
  pending: { label: 'Pending', variant: 'outline', icon: Clock },
}

function formatCurrency(amountCents: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency.toUpperCase(),
  }).format(amountCents / 100)
}

function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] ?? { label: status, variant: 'outline' as const, icon: Clock }
  const Icon = config.icon
  return (
    <Badge variant={config.variant} className="gap-1">
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  )
}

export default function PortalSubscriptionsPage() {
  const token = usePortalToken()
  const queryClient = useQueryClient()
  const [changePlanSub, setChangePlanSub] = useState<PortalSubscriptionResponse | null>(null)

  const { data: subscriptions, isLoading } = useQuery({
    queryKey: ['portal-subscriptions', token],
    queryFn: () => portalApi.listSubscriptions(token),
    enabled: !!token,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Subscriptions</h1>
        <p className="text-muted-foreground">
          View and manage your subscriptions
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      ) : !subscriptions?.length ? (
        <Card>
          <CardContent className="py-12 text-center">
            <ArrowUpDown className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No subscriptions found.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {subscriptions.map((sub) => (
            <Card key={sub.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{sub.plan.name}</CardTitle>
                  <StatusBadge status={sub.status} />
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <div className="text-2xl font-bold">
                      {formatCurrency(sub.plan.amount_cents, sub.plan.currency)}
                      <span className="text-sm font-normal text-muted-foreground ml-1">
                        / {sub.plan.interval}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                      <span>Plan: {sub.plan.code}</span>
                      {sub.started_at && (
                        <span>Since {format(new Date(sub.started_at), 'MMM d, yyyy')}</span>
                      )}
                    </div>
                    {sub.pending_downgrade_plan && (
                      <div className="flex items-center gap-1 text-sm text-amber-600">
                        <Clock className="h-3.5 w-3.5" />
                        Downgrade to {sub.pending_downgrade_plan.name} pending at end of period
                      </div>
                    )}
                  </div>
                  {sub.status === 'active' && (
                    <Button
                      variant="outline"
                      onClick={() => setChangePlanSub(sub)}
                    >
                      <ArrowUpDown className="mr-2 h-4 w-4" />
                      Change Plan
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {changePlanSub && (
        <ChangePlanDialog
          subscription={changePlanSub}
          token={token}
          onClose={() => setChangePlanSub(null)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['portal-subscriptions', token] })
            setChangePlanSub(null)
          }}
        />
      )}
    </div>
  )
}

function ChangePlanDialog({
  subscription,
  token,
  onClose,
  onSuccess,
}: {
  subscription: PortalSubscriptionResponse
  token: string
  onClose: () => void
  onSuccess: () => void
}) {
  const [selectedPlan, setSelectedPlan] = useState<PortalPlanResponse | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)

  const { data: plans, isLoading: plansLoading } = useQuery({
    queryKey: ['portal-plans', token],
    queryFn: () => portalApi.listPlans(token),
    enabled: !!token,
  })

  const { data: preview, isLoading: previewLoading } = useQuery({
    queryKey: ['portal-change-plan-preview', token, subscription.id, selectedPlan?.id],
    queryFn: () => portalApi.changePlanPreview(token, subscription.id, selectedPlan!.id),
    enabled: !!token && !!selectedPlan,
  })

  const changePlanMutation = useMutation({
    mutationFn: () => portalApi.changePlan(token, subscription.id, selectedPlan!.id),
    onSuccess: () => {
      toast.success('Plan changed successfully')
      onSuccess()
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : 'Failed to change plan'
      toast.error(msg)
    },
  })

  const availablePlans = plans?.filter((p) => p.id !== subscription.plan.id) ?? []

  if (showConfirm && preview && selectedPlan) {
    return (
      <Dialog open onOpenChange={() => setShowConfirm(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Plan Change</DialogTitle>
            <DialogDescription>
              Review the proration details before confirming.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <PlanComparisonCard label="Current Plan" plan={preview.current_plan} />
              <PlanComparisonCard label="New Plan" plan={preview.new_plan} />
            </div>
            <Card>
              <CardContent className="pt-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Credit for current plan</span>
                  <span className="text-green-600">
                    -{formatCurrency(preview.proration.current_plan_credit_cents, preview.current_plan.currency)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Charge for new plan</span>
                  <span>
                    {formatCurrency(preview.proration.new_plan_charge_cents, preview.new_plan.currency)}
                  </span>
                </div>
                <div className="border-t pt-2 flex justify-between font-medium">
                  <span>Net amount</span>
                  <span className={preview.proration.net_amount_cents < 0 ? 'text-green-600' : ''}>
                    {preview.proration.net_amount_cents < 0 ? '-' : ''}
                    {formatCurrency(Math.abs(preview.proration.net_amount_cents), preview.current_plan.currency)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {preview.proration.days_remaining} days remaining in billing period ({preview.proration.total_days} day cycle)
                </p>
              </CardContent>
            </Card>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirm(false)}>
              Back
            </Button>
            <Button
              onClick={() => changePlanMutation.mutate()}
              disabled={changePlanMutation.isPending}
            >
              {changePlanMutation.isPending ? 'Changing...' : 'Confirm Change'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Change Plan</DialogTitle>
          <DialogDescription>
            Currently on <strong>{subscription.plan.name}</strong> ({formatCurrency(subscription.plan.amount_cents, subscription.plan.currency)}/{subscription.plan.interval}).
            Select a new plan below.
          </DialogDescription>
        </DialogHeader>
        {plansLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : availablePlans.length === 0 ? (
          <p className="text-muted-foreground text-center py-6">
            No other plans available.
          </p>
        ) : (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {availablePlans.map((plan) => {
              const isSelected = selectedPlan?.id === plan.id
              const isUpgrade = plan.amount_cents > subscription.plan.amount_cents
              return (
                <button
                  key={plan.id}
                  onClick={() => setSelectedPlan(plan)}
                  className={`w-full text-left rounded-lg border p-4 transition-colors ${
                    isSelected
                      ? 'border-primary bg-primary/5'
                      : 'hover:bg-accent/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{plan.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {isUpgrade ? 'Upgrade' : 'Downgrade'}
                        </Badge>
                      </div>
                      {plan.description && (
                        <p className="text-xs text-muted-foreground mt-0.5">{plan.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">
                        {formatCurrency(plan.amount_cents, plan.currency)}
                        <span className="text-xs font-normal text-muted-foreground">/{plan.interval}</span>
                      </span>
                      {isSelected && <Check className="h-4 w-4 text-primary" />}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!selectedPlan || previewLoading}
            onClick={() => setShowConfirm(true)}
          >
            {previewLoading ? 'Loading...' : 'Review Change'}
            {!previewLoading && <ChevronRight className="ml-1 h-4 w-4" />}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function PlanComparisonCard({ label, plan }: { label: string; plan: PortalPlanSummary }) {
  return (
    <div className="rounded-lg border p-3 text-center">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-medium mt-1">{plan.name}</p>
      <p className="text-lg font-bold">
        {formatCurrency(plan.amount_cents, plan.currency)}
        <span className="text-xs font-normal text-muted-foreground">/{plan.interval}</span>
      </p>
    </div>
  )
}
