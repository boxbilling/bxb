import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { FileText, CreditCard, Tag, ScrollText, Plus, History } from 'lucide-react'
import { toast } from 'sonner'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { CustomerFormDialog } from '@/components/CustomerFormDialog'
import { CustomerPaymentMethodsCard } from '@/components/customer-detail/CustomerPaymentMethodsCard'
import { CustomerSubscriptionsTable } from '@/components/customer-detail/CustomerSubscriptionsTable'
import { CustomerInvoicesTable } from '@/components/customer-detail/CustomerInvoicesTable'
import { CustomerPaymentsTable } from '@/components/customer-detail/CustomerPaymentsTable'
import { CustomerWalletsTable } from '@/components/customer-detail/CustomerWalletsTable'
import { CustomerCouponsTable } from '@/components/customer-detail/CustomerCouponsTable'
import { CustomerCreditNotesTable } from '@/components/customer-detail/CustomerCreditNotesTable'
import { CustomerFeesTable } from '@/components/customer-detail/CustomerFeesTable'
import { CustomerKPICards } from '@/components/customer-detail/CustomerKPICards'
import { CustomerUsageSection } from '@/components/customer-detail/CustomerUsageSection'
import { CustomerActivityTab } from '@/components/customer-detail/CustomerActivityTab'
import { CustomerHeader } from '@/components/customer-detail/CustomerHeader'
import { customersApi, subscriptionsApi, plansApi, ApiError } from '@/lib/api'
import { SubscriptionFormDialog } from '@/components/SubscriptionFormDialog'
import type { CustomerUpdate, SubscriptionCreate } from '@/types/billing'

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [editOpen, setEditOpen] = useState(false)
  const [subscriptionFormOpen, setSubscriptionFormOpen] = useState(false)

  const { data: customer, isLoading, error } = useQuery({
    queryKey: ['customer', id],
    queryFn: () => customersApi.get(id!),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: (data: CustomerUpdate) => customersApi.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer', id] })
      setEditOpen(false)
      toast.success('Customer updated successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update customer'
      toast.error(message)
    },
  })

  const { data: plans } = useQuery({
    queryKey: ['plans'],
    queryFn: () => plansApi.list(),
  })

  const createSubscriptionMutation = useMutation({
    mutationFn: (data: SubscriptionCreate) => subscriptionsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-subscriptions', id] })
      setSubscriptionFormOpen(false)
      toast.success('Subscription created successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create subscription'
      toast.error(message)
    },
  })

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load customer. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/admin/customers">Customers</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>
              {isLoading ? <Skeleton className="h-4 w-32 inline-block" /> : customer?.name}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {isLoading ? (
        <div className="space-y-6">
          <div>
            <Skeleton className="h-7 w-48 mb-1" />
            <Skeleton className="h-4 w-64" />
          </div>
          <Skeleton className="h-64 w-full" />
        </div>
      ) : customer ? (
        <>
          {/* Header */}
          <CustomerHeader customer={customer} onEdit={() => setEditOpen(true)} />

          {/* Outstanding Balance */}
          <CustomerKPICards customerId={customer.id} currency={customer.currency} />

          {/* Customer Information */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Customer Information</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">External ID</span>
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{customer.external_id}</code>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Email</span>
                  <span>{customer.email ?? '\u2014'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Currency</span>
                  <Badge variant="outline">{customer.currency}</Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Timezone</span>
                  <span>{customer.timezone}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Invoice Grace Period</span>
                  <span>{customer.invoice_grace_period} days</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Net Payment Term</span>
                  <span>{customer.net_payment_term} days</span>
                </div>
                <div className="space-y-1">
                  <span className="text-muted-foreground">Billing Metadata</span>
                  {customer.billing_metadata && Object.keys(customer.billing_metadata).length > 0 ? (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {Object.entries(customer.billing_metadata).map(([key, value]) => (
                        <Badge key={key} variant="outline" className="font-normal text-xs">
                          <span className="font-medium">{key}:</span>
                          <span className="ml-1 text-muted-foreground">{String(value)}</span>
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <span>None</span>
                  )}
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Created</span>
                  <span>{format(new Date(customer.created_at), 'MMM d, yyyy HH:mm')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Updated</span>
                  <span>{format(new Date(customer.updated_at), 'MMM d, yyyy HH:mm')}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Related Data Tabs */}
          <Tabs defaultValue="overview">
            <div className="overflow-x-auto">
              <TabsList>
                <TabsTrigger value="overview">
                  <ScrollText className="mr-2 h-4 w-4" />
                  Overview
                </TabsTrigger>
                <TabsTrigger value="billing">
                  <FileText className="mr-2 h-4 w-4" />
                  Billing
                </TabsTrigger>
                <TabsTrigger value="payments">
                  <CreditCard className="mr-2 h-4 w-4" />
                  Payments
                </TabsTrigger>
                <TabsTrigger value="coupons">
                  <Tag className="mr-2 h-4 w-4" />
                  Coupons
                </TabsTrigger>
                <TabsTrigger value="activity">
                  <History className="mr-2 h-4 w-4" />
                  Activity
                </TabsTrigger>
              </TabsList>
            </div>

            {/* Overview: Subscriptions + Usage */}
            <TabsContent value="overview">
              <div className="space-y-6">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium">Subscriptions</h3>
                    <Button variant="outline" size="sm" onClick={() => setSubscriptionFormOpen(true)}>
                      <Plus className="mr-2 h-4 w-4" />
                      Create Subscription
                    </Button>
                  </div>
                  <CustomerSubscriptionsTable customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Usage</h3>
                  <CustomerUsageSection customerId={customer.id} externalId={customer.external_id} />
                </div>
              </div>
            </TabsContent>

            {/* Billing: Invoices + Fees + Credit Notes */}
            <TabsContent value="billing">
              <div className="space-y-6">
                <div>
                  <h3 className="text-sm font-medium mb-3">Invoices</h3>
                  <CustomerInvoicesTable customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Fees</h3>
                  <CustomerFeesTable customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Credit Notes</h3>
                  <CustomerCreditNotesTable customerId={customer.id} />
                </div>
              </div>
            </TabsContent>

            {/* Payments: Payment Methods + Payments + Wallets */}
            <TabsContent value="payments">
              <div className="space-y-6">
                <CustomerPaymentMethodsCard customerId={customer.id} customerName={customer.name} />
                <div>
                  <h3 className="text-sm font-medium mb-3">Payment History</h3>
                  <CustomerPaymentsTable customerId={customer.id} />
                </div>
                <div>
                  <h3 className="text-sm font-medium mb-3">Wallets</h3>
                  <CustomerWalletsTable customerId={customer.id} />
                </div>
              </div>
            </TabsContent>

            {/* Coupons */}
            <TabsContent value="coupons">
              <CustomerCouponsTable customerId={customer.id} />
            </TabsContent>

            {/* Activity: Audit Trail */}
            <TabsContent value="activity">
              <CustomerActivityTab customerId={customer.id} />
            </TabsContent>
          </Tabs>

          {/* Edit Customer Dialog */}
          <CustomerFormDialog
            open={editOpen}
            onOpenChange={setEditOpen}
            customer={customer}
            onSubmit={(data) => updateMutation.mutate(data as CustomerUpdate)}
            isLoading={updateMutation.isPending}
          />

          {/* Create Subscription Dialog */}
          <SubscriptionFormDialog
            open={subscriptionFormOpen}
            onOpenChange={setSubscriptionFormOpen}
            customers={customer ? [customer] : []}
            plans={plans ?? []}
            onSubmit={(data) => createSubscriptionMutation.mutate(data)}
            isLoading={createSubscriptionMutation.isPending}
            defaultCustomerId={customer?.id}
          />
        </>
      ) : null}
    </div>
  )
}
