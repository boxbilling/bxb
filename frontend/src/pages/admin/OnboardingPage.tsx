import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Building,
  Building2,
  Layers,
  Check,
  ArrowRight,
  CircleAlert,
} from 'lucide-react'

import { organizationsApi, billingEntitiesApi, plansApi } from '@/lib/api'
import PageHeader from '@/components/PageHeader'
import { Progress } from '@/components/ui/progress'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface OnboardingStep {
  key: string
  label: string
  description: string
  icon: React.ElementType
  href: string
  actionLabel: string
  completed: boolean
}

function useOnboardingSteps() {
  const orgQuery = useQuery({
    queryKey: ['organization'],
    queryFn: () => organizationsApi.getCurrent(),
    staleTime: 5 * 60 * 1000,
  })

  const billingEntitiesQuery = useQuery({
    queryKey: ['billing-entities-onboarding'],
    queryFn: () => billingEntitiesApi.list(),
  })

  const plansQuery = useQuery({
    queryKey: ['plans-onboarding'],
    queryFn: () => plansApi.list(),
  })

  const isLoading =
    orgQuery.isLoading ||
    billingEntitiesQuery.isLoading ||
    plansQuery.isLoading

  const org = orgQuery.data
  const billingEntities = billingEntitiesQuery.data ?? []
  const plans = plansQuery.data ?? []

  const orgComplete = !!(
    org?.name &&
    org.default_currency &&
    org.timezone
  )

  const billingEntityComplete = billingEntities.length > 0
  const planComplete = plans.length > 0

  const steps: OnboardingStep[] = [
    {
      key: 'organization',
      label: 'Organization Details',
      description:
        'Set up your organization name, default currency, and timezone.',
      icon: Building,
      href: '/admin/settings',
      actionLabel: orgComplete ? 'Review settings' : 'Configure organization',
      completed: orgComplete,
    },
    {
      key: 'billing-entity',
      label: 'Create a Billing Entity',
      description:
        'Add at least one billing entity with legal name and address for invoicing.',
      icon: Building2,
      href: '/admin/billing-entities/new',
      actionLabel: billingEntityComplete
        ? 'View billing entities'
        : 'Create billing entity',
      completed: billingEntityComplete,
    },
    {
      key: 'plan',
      label: 'Create a Plan',
      description:
        'Define a pricing plan with charges that you can assign to customers.',
      icon: Layers,
      href: '/admin/plans',
      actionLabel: planComplete ? 'View plans' : 'Create a plan',
      completed: planComplete,
    },
  ]

  const completedCount = steps.filter((s) => s.completed).length
  const progressPercent = Math.round((completedCount / steps.length) * 100)

  return { steps, completedCount, progressPercent, isLoading }
}

function StepCard({ step, index }: { step: OnboardingStep; index: number }) {
  const Icon = step.icon

  return (
    <Card
      className={cn(
        'transition-colors',
        step.completed && 'border-green-500/30 bg-green-50/50 dark:bg-green-950/10',
      )}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div
              className={cn(
                'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold',
                step.completed
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400'
                  : 'bg-muted text-muted-foreground',
              )}
            >
              {step.completed ? <Check className="h-4 w-4" /> : index + 1}
            </div>
            <div className="space-y-1">
              <CardTitle className="text-base">{step.label}</CardTitle>
              <p className="text-sm text-muted-foreground">
                {step.description}
              </p>
            </div>
          </div>
          <Badge variant={step.completed ? 'default' : 'outline'}>
            {step.completed ? 'Complete' : 'Pending'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <Button variant={step.completed ? 'outline' : 'default'} size="sm" asChild>
          <Link to={step.href}>
            {step.actionLabel}
            <ArrowRight className="ml-1 h-4 w-4" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  )
}

function OnboardingLoading() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-2 h-4 w-72" />
      </div>
      <Card>
        <CardContent className="pt-6">
          <Skeleton className="h-2 w-full rounded-full" />
          <Skeleton className="mt-2 h-4 w-40" />
        </CardContent>
      </Card>
      {Array.from({ length: 3 }).map((_, i) => (
        <Card key={i}>
          <CardHeader>
            <div className="flex items-start gap-3">
              <Skeleton className="h-8 w-8 rounded-full" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-4 w-64" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <Skeleton className="h-9 w-40" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

export default function OnboardingPage() {
  const { steps, completedCount, progressPercent, isLoading } =
    useOnboardingSteps()

  if (isLoading) {
    return <OnboardingLoading />
  }

  const allComplete = completedCount === steps.length

  return (
    <div className="space-y-6">
      <PageHeader
        title="Get Started"
        description="Complete these steps to start billing your customers"
      />

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">
              {completedCount} of {steps.length} steps completed
            </span>
            <span className="text-sm text-muted-foreground">
              {progressPercent}%
            </span>
          </div>
          <Progress value={progressPercent} />
          {allComplete && (
            <div className="mt-3 flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
              <Check className="h-4 w-4" />
              <span>All set! Your organization is ready to start billing.</span>
            </div>
          )}
          {!allComplete && (
            <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
              <CircleAlert className="h-4 w-4" />
              <span>
                Complete the remaining steps to start billing your customers.
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="space-y-4">
        {steps.map((step, i) => (
          <StepCard key={step.key} step={step} index={i} />
        ))}
      </div>
    </div>
  )
}
