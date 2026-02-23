import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Activity, FileText, Target, ToggleLeft, GitBranch, ScrollText, ChevronDown } from 'lucide-react'
import { toast } from 'sonner'

import { useSetBreadcrumbs } from '@/components/HeaderBreadcrumb'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { EditSubscriptionDialog } from '@/components/EditSubscriptionDialog'
import { ChangePlanDialog } from '@/components/ChangePlanDialog'
import { TerminateSubscriptionDialog } from '@/components/TerminateSubscriptionDialog'
import { SubscriptionHeader } from '@/components/subscription-detail/SubscriptionHeader'
import { SubscriptionKPICards } from '@/components/subscription-detail/SubscriptionKPICards'
import { SubscriptionInfoSidebar } from '@/components/subscription-detail/SubscriptionInfoSidebar'
import { SubscriptionOverviewTab } from '@/components/subscription-detail/SubscriptionOverviewTab'
import { SubscriptionInvoicesTab } from '@/components/subscription-detail/SubscriptionInvoicesTab'
import { SubscriptionThresholdsAlertsTab } from '@/components/subscription-detail/SubscriptionThresholdsAlertsTab'
import { SubscriptionEntitlementsTab } from '@/components/subscription-detail/SubscriptionEntitlementsTab'
import { SubscriptionLifecycleTab } from '@/components/subscription-detail/SubscriptionLifecycleTab'
import { SubscriptionActivityTab } from '@/components/subscription-detail/SubscriptionActivityTab'
import { subscriptionsApi, customersApi, plansApi, ApiError } from '@/lib/api'
import { useIsMobile } from '@/hooks/use-mobile'
import type { SubscriptionUpdate, TerminationAction } from '@/lib/api'

export default function SubscriptionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()
  const [editOpen, setEditOpen] = useState(false)
  const [changePlanOpen, setChangePlanOpen] = useState(false)
  const [terminateOpen, setTerminateOpen] = useState(false)

  const { data: subscription, isLoading, error } = useQuery({
    queryKey: ['subscription', id],
    queryFn: () => subscriptionsApi.get(id!),
    enabled: !!id,
  })

  const { data: customer } = useQuery({
    queryKey: ['customer', subscription?.customer_id],
    queryFn: () => customersApi.get(subscription!.customer_id),
    enabled: !!subscription?.customer_id,
  })

  const { data: plan } = useQuery({
    queryKey: ['plan', subscription?.plan_id],
    queryFn: () => plansApi.get(subscription!.plan_id),
    enabled: !!subscription?.plan_id,
  })

  const { data: plans } = useQuery({
    queryKey: ['plans'],
    queryFn: () => plansApi.list(),
  })

  const updateMutation = useMutation({
    mutationFn: (data: SubscriptionUpdate) => subscriptionsApi.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription', id] })
      setEditOpen(false)
      toast.success('Subscription updated')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update subscription'
      toast.error(message)
    },
  })

  const pauseMutation = useMutation({
    mutationFn: () => subscriptionsApi.pause(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription', id] })
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      toast.success('Subscription paused')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to pause subscription'
      toast.error(message)
    },
  })

  const resumeMutation = useMutation({
    mutationFn: () => subscriptionsApi.resume(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription', id] })
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      toast.success('Subscription resumed')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to resume subscription'
      toast.error(message)
    },
  })

  const changePlanMutation = useMutation({
    mutationFn: ({ planId }: { planId: string }) =>
      subscriptionsApi.update(id!, {
        plan_id: planId,
        previous_plan_id: subscription?.plan_id,
        downgraded_at: new Date().toISOString(),
      } as SubscriptionUpdate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscription', id] })
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setChangePlanOpen(false)
      toast.success('Plan changed successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to change plan'
      toast.error(message)
    },
  })

  const terminateMutation = useMutation({
    mutationFn: ({ action }: { action: TerminationAction }) =>
      subscriptionsApi.terminate(id!, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setTerminateOpen(false)
      toast.success('Subscription terminated')
      navigate('/admin/subscriptions')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to terminate subscription'
      toast.error(message)
    },
  })

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load subscription. Please try again.</p>
      </div>
    )
  }

  const customerName = customer?.name ?? 'Loading...'
  const planName = plan?.name ?? 'Loading...'

  useSetBreadcrumbs([
    { label: 'Subscriptions', href: '/admin/subscriptions' },
    { label: isLoading ? 'Loading...' : `${customerName} — ${planName}` },
  ])

  const tabsContent = (
    <Tabs defaultValue="overview">
      <div className="overflow-x-auto">
        <TabsList>
          <TabsTrigger value="overview">
            <Activity className="mr-2 h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="invoices">
            <FileText className="mr-2 h-4 w-4" />
            Invoices &amp; Payments
          </TabsTrigger>
          <TabsTrigger value="thresholds">
            <Target className="mr-2 h-4 w-4" />
            Thresholds &amp; Alerts
          </TabsTrigger>
          <TabsTrigger value="entitlements">
            <ToggleLeft className="mr-2 h-4 w-4" />
            Entitlements
          </TabsTrigger>
          <TabsTrigger value="lifecycle">
            <GitBranch className="mr-2 h-4 w-4" />
            Lifecycle
          </TabsTrigger>
          <TabsTrigger value="activity">
            <ScrollText className="mr-2 h-4 w-4" />
            Activity
          </TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value="overview">
        <SubscriptionOverviewTab
          subscriptionId={id!}
          customerExternalId={customer?.external_id}
          subscriptionExternalId={subscription?.external_id}
          customerId={subscription?.customer_id}
          planId={subscription?.plan_id}
          previousPlanId={subscription?.previous_plan_id}
          downgradedAt={subscription?.downgraded_at}
        />
      </TabsContent>

      <TabsContent value="invoices">
        <SubscriptionInvoicesTab subscriptionId={id!} />
      </TabsContent>

      <TabsContent value="thresholds">
        <SubscriptionThresholdsAlertsTab subscriptionId={id!} />
      </TabsContent>

      <TabsContent value="entitlements">
        {subscription?.external_id ? (
          <SubscriptionEntitlementsTab subscriptionExternalId={subscription.external_id} />
        ) : (
          <p className="text-sm text-muted-foreground">Loading entitlements...</p>
        )}
      </TabsContent>

      <TabsContent value="lifecycle">
        <SubscriptionLifecycleTab subscriptionId={id!} />
      </TabsContent>

      <TabsContent value="activity">
        <SubscriptionActivityTab subscriptionId={id!} />
      </TabsContent>
    </Tabs>
  )

  return (
    <div className="space-y-6">
      {isLoading ? (
        <div className="space-y-6">
          <div>
            <Skeleton className="h-7 w-64 mb-1" />
            <Skeleton className="h-4 w-48" />
          </div>
          <Skeleton className="h-48 w-full" />
        </div>
      ) : subscription ? (
        <>
          {/* Header */}
          <SubscriptionHeader
            subscription={subscription}
            customer={customer}
            plan={plan}
            isLoading={isLoading}
          />

          {/* KPI Cards */}
          <SubscriptionKPICards
            subscriptionId={id!}
            subscription={subscription}
            plan={plan}
            isLoading={isLoading}
          />

          {/* Sidebar + Tabs Layout */}
          {isMobile ? (
            <div className="space-y-6">
              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button variant="outline" className="w-full justify-between">
                    Subscription Details
                    <ChevronDown className="h-4 w-4" />
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="mt-3">
                  <SubscriptionInfoSidebar
                    subscription={subscription}
                    customer={customer}
                    plan={plan}
                    onEdit={() => setEditOpen(true)}
                    onPause={() => pauseMutation.mutate()}
                    onResume={() => resumeMutation.mutate()}
                    onChangePlan={() => setChangePlanOpen(true)}
                    onTerminate={() => setTerminateOpen(true)}
                    isPauseLoading={pauseMutation.isPending}
                    isResumeLoading={resumeMutation.isPending}
                    isTerminateLoading={terminateMutation.isPending}
                  />
                </CollapsibleContent>
              </Collapsible>
              {tabsContent}
            </div>
          ) : (
            <div className="grid grid-cols-[280px_1fr] gap-6 items-start">
              <div className="sticky top-6">
                <SubscriptionInfoSidebar
                  subscription={subscription}
                  customer={customer}
                  plan={plan}
                  onEdit={() => setEditOpen(true)}
                  onPause={() => pauseMutation.mutate()}
                  onResume={() => resumeMutation.mutate()}
                  onChangePlan={() => setChangePlanOpen(true)}
                  onTerminate={() => setTerminateOpen(true)}
                  isPauseLoading={pauseMutation.isPending}
                  isResumeLoading={resumeMutation.isPending}
                  isTerminateLoading={terminateMutation.isPending}
                />
              </div>
              {tabsContent}
            </div>
          )}

          {/* Edit Subscription Dialog */}
          <EditSubscriptionDialog
            open={editOpen}
            onOpenChange={setEditOpen}
            subscription={subscription}
            onSubmit={(data) => updateMutation.mutate(data)}
            isLoading={updateMutation.isPending}
          />

          {/* Change Plan Dialog */}
          <ChangePlanDialog
            open={changePlanOpen}
            onOpenChange={setChangePlanOpen}
            subscription={subscription}
            plans={plans ?? []}
            onSubmit={(_id, planId) => changePlanMutation.mutate({ planId })}
            isLoading={changePlanMutation.isPending}
          />

          {/* Terminate Subscription Dialog */}
          <TerminateSubscriptionDialog
            open={terminateOpen}
            onOpenChange={setTerminateOpen}
            subscription={subscription}
            onTerminate={(_id, action) => terminateMutation.mutate({ action })}
            isLoading={terminateMutation.isPending}
          />
        </>
      ) : null}
    </div>
  )
}
