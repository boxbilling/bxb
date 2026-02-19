import { useState } from 'react'
import { format } from 'date-fns'
import { Copy, Check, Pencil, Pause, Play, ArrowRightLeft, Trash2, ExternalLink, Users, FileText, Radio } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { billingEntitiesApi } from '@/lib/api'
import type { Subscription, Customer, Plan } from '@/types/billing'

interface SubscriptionInfoSidebarProps {
  subscription?: Subscription
  customer?: Customer
  plan?: Plan
  isLoading?: boolean
  onEdit?: () => void
  onPause?: () => void
  onResume?: () => void
  onChangePlan?: () => void
  onTerminate?: () => void
  isPauseLoading?: boolean
  isResumeLoading?: boolean
  isTerminateLoading?: boolean
}

const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  active: 'default',
  pending: 'secondary',
  paused: 'outline',
  canceled: 'secondary',
  terminated: 'destructive',
}

export function SubscriptionInfoSidebar({
  subscription,
  customer,
  plan,
  isLoading,
  onEdit,
  onPause,
  onResume,
  onChangePlan,
  onTerminate,
  isPauseLoading,
  isResumeLoading,
  isTerminateLoading,
}: SubscriptionInfoSidebarProps) {
  const [copied, setCopied] = useState(false)

  const { data: billingEntities } = useQuery({
    queryKey: ['billing-entities'],
    queryFn: () => billingEntitiesApi.list(),
    enabled: !!customer?.billing_entity_id,
  })

  const billingEntity = billingEntities?.find(
    (e) => e.id === customer?.billing_entity_id
  )

  const handleCopyExternalId = async () => {
    if (!subscription) return
    await navigator.clipboard.writeText(subscription.external_id)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (isLoading || !subscription) {
    return (
      <Card>
        <CardContent className="pt-5 space-y-3">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-px w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-px w-full" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-px w-full" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-3/4" />
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardContent className="pt-5">
        {/* Subscription External ID & Status */}
        <div className="grid gap-3 text-sm">
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">External ID</span>
            <div className="flex items-center gap-1.5">
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{subscription.external_id}</code>
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleCopyExternalId}>
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              </Button>
            </div>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Status</span>
            <Badge variant={statusVariant[subscription.status] ?? 'outline'}>
              {subscription.status}
            </Badge>
          </div>
        </div>

        <Separator className="my-3" />

        {/* Quick Actions */}
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Quick Actions</h4>
          {(subscription.status === 'active' || subscription.status === 'pending' || subscription.status === 'paused') && (
            <Button variant="outline" size="sm" className="w-full justify-start" onClick={onEdit}>
              <Pencil className="mr-2 h-3.5 w-3.5" />
              Edit
            </Button>
          )}
          {subscription.status === 'active' && (
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-start"
              onClick={onPause}
              disabled={isPauseLoading}
            >
              <Pause className="mr-2 h-3.5 w-3.5" />
              {isPauseLoading ? 'Pausing...' : 'Pause'}
            </Button>
          )}
          {subscription.status === 'paused' && (
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-start"
              onClick={onResume}
              disabled={isResumeLoading}
            >
              <Play className="mr-2 h-3.5 w-3.5" />
              {isResumeLoading ? 'Resuming...' : 'Resume'}
            </Button>
          )}
          {(subscription.status === 'active' || subscription.status === 'pending') && plan && (
            <Button variant="outline" size="sm" className="w-full justify-start" onClick={onChangePlan}>
              <ArrowRightLeft className="mr-2 h-3.5 w-3.5" />
              Change Plan
            </Button>
          )}
          {(subscription.status === 'active' || subscription.status === 'pending' || subscription.status === 'paused') && (
            <Button
              variant="destructive"
              size="sm"
              className="w-full justify-start"
              onClick={onTerminate}
              disabled={isTerminateLoading}
            >
              <Trash2 className="mr-2 h-3.5 w-3.5" />
              {isTerminateLoading ? 'Terminating...' : 'Terminate'}
            </Button>
          )}
        </div>

        <Separator className="my-3" />

        {/* Customer & Plan Links */}
        <div className="grid gap-3 text-sm">
          <div>
            <span className="text-muted-foreground text-xs">Customer</span>
            {customer ? (
              <div className="mt-0.5">
                <Link to={`/admin/customers/${customer.id}`} className="text-primary hover:underline font-medium flex items-center gap-1">
                  {customer.name}
                  <ExternalLink className="h-3 w-3" />
                </Link>
                {customer.email && (
                  <span className="text-xs text-muted-foreground">{customer.email}</span>
                )}
              </div>
            ) : (
              <Skeleton className="h-4 w-24 mt-0.5" />
            )}
          </div>
          <div>
            <span className="text-muted-foreground text-xs">Plan</span>
            {plan ? (
              <div className="mt-0.5">
                <Link to={`/admin/plans/${plan.id}`} className="text-primary hover:underline font-medium flex items-center gap-1">
                  {plan.name}
                  <ExternalLink className="h-3 w-3" />
                </Link>
                <span className="text-xs text-muted-foreground">
                  {(plan.amount_cents / 100).toLocaleString(undefined, { style: 'currency', currency: plan.currency })} / {plan.interval}
                </span>
              </div>
            ) : (
              <Skeleton className="h-4 w-24 mt-0.5" />
            )}
          </div>
        </div>

        <Separator className="my-3" />

        {/* Billing Configuration */}
        <div className="grid gap-3 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Billing Time</span>
            <span className="capitalize">{subscription.billing_time}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Pay in Advance</span>
            <span>{subscription.pay_in_advance ? 'Yes' : 'No'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">On Termination</span>
            <span className="capitalize">{subscription.on_termination_action.replace(/_/g, ' ')}</span>
          </div>
        </div>

        {/* Trial Info */}
        {subscription.trial_period_days > 0 && (
          <>
            <Separator className="my-3" />
            <div className="grid gap-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Trial Period</span>
                <span>{subscription.trial_period_days} days</span>
              </div>
              {subscription.trial_ended_at && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Trial Ended</span>
                  <span>{format(new Date(subscription.trial_ended_at), 'MMM d, yyyy HH:mm')}</span>
                </div>
              )}
            </div>
          </>
        )}

        <Separator className="my-3" />

        {/* Key Dates */}
        <div className="grid gap-3 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Started At</span>
            <span>{subscription.started_at ? format(new Date(subscription.started_at), 'MMM d, yyyy HH:mm') : '\u2014'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Created</span>
            <span>{format(new Date(subscription.created_at), 'MMM d, yyyy HH:mm')}</span>
          </div>
          {subscription.paused_at && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Paused At</span>
              <span>{format(new Date(subscription.paused_at), 'MMM d, yyyy HH:mm')}</span>
            </div>
          )}
          {subscription.resumed_at && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Last Resumed</span>
              <span>{format(new Date(subscription.resumed_at), 'MMM d, yyyy HH:mm')}</span>
            </div>
          )}
          {subscription.canceled_at && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Canceled At</span>
              <span>{format(new Date(subscription.canceled_at), 'MMM d, yyyy HH:mm')}</span>
            </div>
          )}
          {subscription.ending_at && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Ending At</span>
              <span>{format(new Date(subscription.ending_at), 'MMM d, yyyy HH:mm')}</span>
            </div>
          )}
        </div>

        {/* Billing Entity */}
        {customer?.billing_entity_id && (
          <>
            <Separator className="my-3" />
            <div className="text-sm">
              <span className="text-muted-foreground text-xs">Billing Entity</span>
              {billingEntity ? (
                <div className="mt-0.5">
                  <Link
                    to={`/admin/billing-entities/${billingEntity.code}`}
                    className="text-primary hover:underline font-medium flex items-center gap-1"
                  >
                    {billingEntity.name}
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              ) : (
                <p className="text-muted-foreground">{'\u2014'}</p>
              )}
            </div>
          </>
        )}

        {/* Related */}
        <Separator className="my-3" />
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Related</h4>
          {customer && (
            <Link
              to={`/admin/subscriptions?customer_id=${subscription.customer_id}`}
              className="flex items-center gap-2 text-sm text-primary hover:underline"
            >
              <Users className="h-3.5 w-3.5" />
              Customer&apos;s other subscriptions
            </Link>
          )}
          <Link
            to={`/admin/invoices?subscription_id=${subscription.id}`}
            className="flex items-center gap-2 text-sm text-primary hover:underline"
          >
            <FileText className="h-3.5 w-3.5" />
            Invoices for this subscription
          </Link>
          {customer && (
            <Link
              to={`/admin/events?customer_id=${customer.external_id}`}
              className="flex items-center gap-2 text-sm text-primary hover:underline"
            >
              <Radio className="h-3.5 w-3.5" />
              Events from this customer
            </Link>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
