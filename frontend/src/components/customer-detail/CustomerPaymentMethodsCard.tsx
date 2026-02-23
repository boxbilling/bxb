import { useState } from 'react'
import { useQueryClient, useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Plus, Star, Trash2, CreditCard, Landmark } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
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
import { CardBrandIcon } from '@/components/CardBrandIcon'
import { PaymentMethodFormDialog } from '@/components/PaymentMethodFormDialog'
import { paymentMethodsApi, ApiError } from '@/lib/api'
import type { PaymentMethod, PaymentMethodCreate } from '@/lib/api'
import { formatCents } from '@/lib/utils'

export function CustomerPaymentMethodsCard({ customerId, customerName }: { customerId: string; customerName: string }) {
  const queryClient = useQueryClient()
  const [deleteMethod, setDeleteMethod] = useState<PaymentMethod | null>(null)
  const [addFormOpen, setAddFormOpen] = useState(false)

  const { data: paymentMethods, isLoading } = useQuery({
    queryKey: ['customer-payment-methods', customerId],
    queryFn: () => paymentMethodsApi.list({ customer_id: customerId }),
  })

  const createMutation = useMutation({
    mutationFn: (data: PaymentMethodCreate) => paymentMethodsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-payment-methods', customerId] })
      setAddFormOpen(false)
      toast.success('Payment method added')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to add payment method')
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => paymentMethodsApi.setDefault(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-payment-methods', customerId] })
      toast.success('Default payment method updated')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to set default payment method')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => paymentMethodsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customer-payment-methods', customerId] })
      setDeleteMethod(null)
      toast.success('Payment method removed')
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : 'Failed to remove payment method')
    },
  })

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-sm font-medium">Payment Methods</CardTitle>
          <Button variant="outline" size="sm" onClick={() => setAddFormOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Payment Method
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : !paymentMethods?.length ? (
            <p className="text-sm text-muted-foreground py-4">No payment methods found</p>
          ) : (
            <div className="space-y-3">
              {paymentMethods.map((pm) => {
                const details = pm.details as { last4?: string; brand?: string; exp_month?: number; exp_year?: number } | null
                const brand = details?.brand
                const last4 = details?.last4
                const expMonth = details?.exp_month
                const expYear = details?.exp_year

                return (
                  <div
                    key={pm.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="flex items-center gap-3">
                      {pm.type === 'card' && brand ? (
                        <CardBrandIcon brand={brand} size={28} />
                      ) : pm.type === 'card' ? (
                        <CreditCard className="h-6 w-6 text-muted-foreground" />
                      ) : (
                        <Landmark className="h-6 w-6 text-muted-foreground" />
                      )}
                      <div>
                        {last4 ? (
                          <div className="font-mono text-sm font-semibold tracking-wider">
                            {'•••• •••• •••• '}{last4}
                            {expMonth && expYear && (
                              <span className="ml-2 text-xs text-muted-foreground font-normal tracking-normal">
                                {String(expMonth).padStart(2, '0')}/{String(expYear).slice(-2)}
                              </span>
                            )}
                          </div>
                        ) : (
                          <div className="text-sm font-medium">
                            {pm.type === 'bank_account' ? 'Bank Account' : pm.type === 'direct_debit' ? 'Direct Debit' : 'Card'}
                          </div>
                        )}
                        <div className="text-xs text-muted-foreground">
                          {pm.provider}
                        </div>
                      </div>
                      {pm.is_default && (
                        <Badge variant="secondary" className="ml-2">Default</Badge>
                      )}
                    </div>
                    <div className="flex gap-1">
                      {!pm.is_default && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDefaultMutation.mutate(pm.id)}
                          disabled={setDefaultMutation.isPending}
                          title="Set as default"
                        >
                          <Star className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteMethod(pm)}
                        disabled={pm.is_default}
                        title={pm.is_default ? 'Cannot remove default payment method' : 'Remove'}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <PaymentMethodFormDialog
        open={addFormOpen}
        onOpenChange={setAddFormOpen}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
        customers={[{ id: customerId, name: customerName }]}
        defaultCustomerId={customerId}
      />

      <AlertDialog
        open={!!deleteMethod}
        onOpenChange={(open) => !open && setDeleteMethod(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Payment Method</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove this payment method? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMethod && deleteMutation.mutate(deleteMethod.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Removing...' : 'Remove'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
