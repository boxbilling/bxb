import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Package, ShoppingCart, Check, Loader2 } from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { portalApi, ApiError } from '@/lib/api'
import { usePortalToken } from '@/layouts/PortalLayout'
import type { PortalAddOn, PortalPurchasedAddOn } from '@/lib/api'

function formatCurrency(cents: number, currency: string): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}

export default function PortalAddOnsPage() {
  const token = usePortalToken()
  const queryClient = useQueryClient()
  const [purchaseTarget, setPurchaseTarget] = useState<PortalAddOn | null>(null)

  const { data: addOns, isLoading: loadingAddOns } = useQuery({
    queryKey: ['portal-add-ons', token],
    queryFn: () => portalApi.listAddOns(token),
    enabled: !!token,
  })

  const { data: purchased, isLoading: loadingPurchased } = useQuery({
    queryKey: ['portal-purchased-add-ons', token],
    queryFn: () => portalApi.listPurchasedAddOns(token),
    enabled: !!token,
  })

  const purchaseMutation = useMutation({
    mutationFn: (addOnId: string) => portalApi.purchaseAddOn(token, addOnId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['portal-purchased-add-ons', token] })
      queryClient.invalidateQueries({ queryKey: ['portal-add-ons', token] })
      toast.success(`Purchased ${data.add_on_name}. An invoice has been created.`)
      setPurchaseTarget(null)
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : 'Failed to purchase add-on'
      toast.error(msg)
      setPurchaseTarget(null)
    },
  })

  return (
    <div className="space-y-4 md:space-y-6">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold">Add-ons</h1>
        <p className="text-sm md:text-base text-muted-foreground">
          Browse and purchase additional features
        </p>
      </div>

      <Tabs defaultValue="available">
        <TabsList>
          <TabsTrigger value="available">
            Available{addOns?.length ? ` (${addOns.length})` : ''}
          </TabsTrigger>
          <TabsTrigger value="purchased">
            Purchased{purchased?.length ? ` (${purchased.length})` : ''}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="available" className="mt-4">
          {loadingAddOns ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-48" />
              ))}
            </div>
          ) : !addOns?.length ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Package className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No add-ons available at this time.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {addOns.map((addOn) => (
                <AddOnCard
                  key={addOn.id}
                  addOn={addOn}
                  onPurchase={() => setPurchaseTarget(addOn)}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="purchased" className="mt-4">
          {loadingPurchased ? (
            <div className="space-y-3">
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-20" />
              ))}
            </div>
          ) : !purchased?.length ? (
            <Card>
              <CardContent className="py-12 text-center">
                <ShoppingCart className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">You haven't purchased any add-ons yet.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {purchased.map((item) => (
                <PurchasedAddOnCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Purchase confirmation dialog */}
      <AlertDialog open={!!purchaseTarget} onOpenChange={() => setPurchaseTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Purchase Add-on</AlertDialogTitle>
            <AlertDialogDescription>
              {purchaseTarget && (
                <>
                  You are about to purchase <strong>{purchaseTarget.name}</strong> for{' '}
                  <strong>
                    {formatCurrency(Number(purchaseTarget.amount_cents), purchaseTarget.amount_currency)}
                  </strong>
                  . An invoice will be created for this purchase.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={purchaseMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => purchaseTarget && purchaseMutation.mutate(purchaseTarget.id)}
              disabled={purchaseMutation.isPending}
            >
              {purchaseMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Purchasing...
                </>
              ) : (
                'Confirm Purchase'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function AddOnCard({
  addOn,
  onPurchase,
}: {
  addOn: PortalAddOn
  onPurchase: () => void
}) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Package className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">{addOn.name}</CardTitle>
          </div>
          <Badge variant="outline">{addOn.amount_currency}</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col justify-between gap-4">
        {addOn.description && (
          <p className="text-sm text-muted-foreground">{addOn.description}</p>
        )}
        <div className="flex items-center justify-between">
          <span className="text-2xl font-bold">
            {formatCurrency(Number(addOn.amount_cents), addOn.amount_currency)}
          </span>
          <Button size="sm" onClick={onPurchase}>
            <ShoppingCart className="mr-2 h-4 w-4" />
            Purchase
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function PurchasedAddOnCard({ item }: { item: PortalPurchasedAddOn }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
            <Check className="h-4 w-4 text-primary" />
          </div>
          <div>
            <div className="font-medium">{item.add_on_name}</div>
            <div className="text-xs text-muted-foreground">
              Purchased {format(new Date(item.created_at), 'MMM d, yyyy')}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="font-semibold">
            {formatCurrency(Number(item.amount_cents), item.amount_currency)}
          </div>
          <Badge variant="outline" className="text-xs">
            {item.amount_currency}
          </Badge>
        </div>
      </CardContent>
    </Card>
  )
}
