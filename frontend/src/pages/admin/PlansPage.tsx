import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, MoreHorizontal, Pencil, Trash2, Calendar, Layers, Users } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
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
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import PageHeader from '@/components/PageHeader'
import { plansApi, ApiError } from '@/lib/api'
import type { Plan, PlanInterval, ChargeModel } from '@/lib/api'
import { formatCents } from '@/lib/utils'

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

export default function PlansPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [deletePlan, setDeletePlan] = useState<Plan | null>(null)

  // Fetch plans from API
  const { data: plans, isLoading, error } = useQuery({
    queryKey: ['plans'],
    queryFn: () => plansApi.list(),
  })

  // Fetch subscription counts per plan
  const { data: subscriptionCounts } = useQuery({
    queryKey: ['plan-subscription-counts'],
    queryFn: () => plansApi.subscriptionCounts(),
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

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load plans. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Plans"
        description="Create and manage pricing plans for your customers"
        actions={
          <Button asChild>
            <Link to="/admin/plans/new">
              <Plus className="mr-2 h-4 w-4" />
              Create Plan
            </Link>
          </Button>
        }
      />

      {/* Plans Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
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
            <Button asChild className="mt-4">
              <Link to="/admin/plans/new">
                <Plus className="mr-2 h-4 w-4" />
                Create Plan
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
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
                      <DropdownMenuItem onClick={() => navigate(`/admin/plans/${plan.id}/edit`)}>
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
                    {formatCents(plan.amount_cents, plan.currency)}
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
