import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CreditCard, Plus, Star, Trash2, Landmark } from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { CardBrandIcon } from '@/components/CardBrandIcon'
import { portalApi, ApiError } from '@/lib/api'
import { usePortalToken } from '@/layouts/PortalLayout'
import type { PaymentMethod } from '@/lib/api'

type PaymentMethodDetails = {
  last4?: string
  brand?: string
  exp_month?: number
  exp_year?: number
} | null

function getDetails(method: PaymentMethod): PaymentMethodDetails {
  return method.details as PaymentMethodDetails
}

function formatCardNumber(method: PaymentMethod): string {
  const details = getDetails(method)
  if (details?.last4) return `•••• •••• •••• ${details.last4}`
  return '•••• •••• •••• ••••'
}

function formatExpiry(method: PaymentMethod): string | null {
  const details = getDetails(method)
  if (details?.exp_month && details?.exp_year) {
    return `${String(details.exp_month).padStart(2, '0')}/${String(details.exp_year).slice(-2)}`
  }
  return null
}

function getTypeIcon(type: string) {
  if (type === 'bank_account' || type === 'direct_debit') {
    return <Landmark className="h-5 w-5 text-muted-foreground" />
  }
  return <CreditCard className="h-5 w-5 text-muted-foreground" />
}

const providerLabels: Record<string, string> = {
  stripe: 'Stripe',
  gocardless: 'GoCardless',
  adyen: 'Adyen',
}

export default function PortalPaymentMethodsPage() {
  const token = usePortalToken()
  const queryClient = useQueryClient()
  const [deleteTarget, setDeleteTarget] = useState<PaymentMethod | null>(null)
  const [showAddDialog, setShowAddDialog] = useState(false)

  const { data: customer } = useQuery({
    queryKey: ['portal-customer', token],
    queryFn: () => portalApi.getCustomer(token),
    enabled: !!token,
  })

  const { data: methods, isLoading } = useQuery({
    queryKey: ['portal-payment-methods', token],
    queryFn: () => portalApi.listPaymentMethods(token),
    enabled: !!token,
  })

  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => portalApi.setDefaultPaymentMethod(token, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portal-payment-methods', token] })
      toast.success('Default payment method updated')
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : 'Failed to set default'
      toast.error(msg)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => portalApi.deletePaymentMethod(token, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portal-payment-methods', token] })
      toast.success('Payment method removed')
      setDeleteTarget(null)
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : 'Failed to remove payment method'
      toast.error(msg)
      setDeleteTarget(null)
    },
  })

  const addMutation = useMutation({
    mutationFn: (data: {
      provider: string
      provider_payment_method_id: string
      type: string
      is_default: boolean
      details: Record<string, unknown>
    }) => {
      if (!customer) throw new Error('Customer not loaded')
      return portalApi.addPaymentMethod(token, {
        customer_id: customer.id,
        ...data,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portal-payment-methods', token] })
      toast.success('Payment method added')
      setShowAddDialog(false)
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : 'Failed to add payment method'
      toast.error(msg)
    },
  })

  const defaultMethod = methods?.find((m) => m.is_default)
  const otherMethods = methods?.filter((m) => !m.is_default) ?? []

  return (
    <div className="space-y-4 md:space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl md:text-3xl font-bold">Payment Methods</h1>
          <p className="text-sm md:text-base text-muted-foreground">
            Manage your payment methods
          </p>
        </div>
        <Button onClick={() => setShowAddDialog(true)} className="shrink-0 min-h-[44px] md:min-h-0">
          <Plus className="mr-2 h-4 w-4" />
          Add
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : !methods?.length ? (
        <Card>
          <CardContent className="py-12 text-center">
            <CreditCard className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No payment methods on file.</p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => setShowAddDialog(true)}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add Your First Payment Method
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Default payment method */}
          {defaultMethod && (
            <Card className="border-primary/50">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                  Default Payment Method
                </CardTitle>
              </CardHeader>
              <CardContent>
                <PaymentMethodCard
                  method={defaultMethod}
                  isDefault
                  onDelete={() => setDeleteTarget(defaultMethod)}
                  onSetDefault={() => {}}
                  isSettingDefault={false}
                />
              </CardContent>
            </Card>
          )}

          {/* Other payment methods */}
          {otherMethods.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">
                  Other Payment Methods
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {otherMethods.map((method) => (
                  <PaymentMethodCard
                    key={method.id}
                    method={method}
                    isDefault={false}
                    onDelete={() => setDeleteTarget(method)}
                    onSetDefault={() => setDefaultMutation.mutate(method.id)}
                    isSettingDefault={setDefaultMutation.isPending}
                  />
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Delete confirmation dialog */}
      <AlertDialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
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
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Removing...' : 'Remove'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Add payment method dialog */}
      <AddPaymentMethodDialog
        open={showAddDialog}
        onOpenChange={setShowAddDialog}
        onSubmit={(data) => addMutation.mutate(data)}
        isPending={addMutation.isPending}
      />
    </div>
  )
}

function PaymentMethodCard({
  method,
  isDefault,
  onDelete,
  onSetDefault,
  isSettingDefault,
}: {
  method: PaymentMethod
  isDefault: boolean
  onDelete: () => void
  onSetDefault: () => void
  isSettingDefault: boolean
}) {
  const details = getDetails(method)
  const expiry = formatExpiry(method)

  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-center gap-3 md:gap-4">
        <div className="flex-shrink-0">
          {details?.brand ? (
            <CardBrandIcon brand={details.brand} size={28} />
          ) : (
            getTypeIcon(method.type)
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs md:text-sm truncate">{formatCardNumber(method)}</span>
            <Badge variant="outline" className="text-[10px] md:text-xs shrink-0">
              {providerLabels[method.provider] ?? method.provider}
            </Badge>
          </div>
          <div className="flex items-center gap-2 md:gap-3 mt-1 text-[10px] md:text-xs text-muted-foreground">
            {expiry && <span>Exp {expiry}</span>}
            <span>Added {format(new Date(method.created_at), 'MMM d, yyyy')}</span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-3 md:mt-0 md:absolute md:right-4 md:top-1/2 md:-translate-y-1/2">
        {!isDefault && (
          <Button
            variant="ghost"
            size="sm"
            className="min-h-[44px] md:min-h-0 flex-1 md:flex-none"
            onClick={onSetDefault}
            disabled={isSettingDefault}
            title="Set as default"
          >
            <Star className="h-4 w-4 mr-1" />
            Set Default
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="min-h-[44px] min-w-[44px] md:min-h-0 md:min-w-0"
          onClick={onDelete}
          disabled={isDefault}
          title={isDefault ? 'Cannot remove default payment method' : 'Remove'}
        >
          <Trash2 className={`h-4 w-4 ${isDefault ? 'opacity-30' : 'text-destructive'}`} />
        </Button>
      </div>
    </div>
  )
}

function AddPaymentMethodDialog({
  open,
  onOpenChange,
  onSubmit,
  isPending,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: {
    provider: string
    provider_payment_method_id: string
    type: string
    is_default: boolean
    details: Record<string, unknown>
  }) => void
  isPending: boolean
}) {
  const [provider, setProvider] = useState('stripe')
  const [type, setType] = useState('card')
  const [providerPmId, setProviderPmId] = useState('')
  const [brand, setBrand] = useState('')
  const [last4, setLast4] = useState('')
  const [expMonth, setExpMonth] = useState('')
  const [expYear, setExpYear] = useState('')
  const [isDefault, setIsDefault] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const details: Record<string, unknown> = {}
    if (brand) details.brand = brand
    if (last4) details.last4 = last4
    if (expMonth) details.exp_month = parseInt(expMonth, 10)
    if (expYear) details.exp_year = parseInt(expYear, 10)
    onSubmit({
      provider,
      provider_payment_method_id: providerPmId,
      type,
      is_default: isDefault,
      details,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Payment Method</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Provider</Label>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="stripe">Stripe</SelectItem>
                <SelectItem value="gocardless">GoCardless</SelectItem>
                <SelectItem value="adyen">Adyen</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Type</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="card">Card</SelectItem>
                <SelectItem value="bank_account">Bank Account</SelectItem>
                <SelectItem value="direct_debit">Direct Debit</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="pm-id">Payment Method ID</Label>
            <Input
              id="pm-id"
              value={providerPmId}
              onChange={(e) => setProviderPmId(e.target.value)}
              placeholder="pm_..."
              required
            />
          </div>
          {type === 'card' && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="pm-brand">Card Brand</Label>
                <Select value={brand} onValueChange={setBrand}>
                  <SelectTrigger id="pm-brand"><SelectValue placeholder="Select..." /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="visa">Visa</SelectItem>
                    <SelectItem value="mastercard">Mastercard</SelectItem>
                    <SelectItem value="amex">Amex</SelectItem>
                    <SelectItem value="discover">Discover</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="pm-last4">Last 4 Digits</Label>
                <Input
                  id="pm-last4"
                  value={last4}
                  onChange={(e) => setLast4(e.target.value.replace(/\D/g, '').slice(0, 4))}
                  placeholder="4242"
                  maxLength={4}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pm-exp-month">Exp Month</Label>
                <Input
                  id="pm-exp-month"
                  type="number"
                  min={1}
                  max={12}
                  value={expMonth}
                  onChange={(e) => setExpMonth(e.target.value)}
                  placeholder="MM"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pm-exp-year">Exp Year</Label>
                <Input
                  id="pm-exp-year"
                  type="number"
                  min={2024}
                  max={2099}
                  value={expYear}
                  onChange={(e) => setExpYear(e.target.value)}
                  placeholder="YYYY"
                />
              </div>
            </div>
          )}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="pm-default"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
              className="rounded"
            />
            <Label htmlFor="pm-default">Set as default payment method</Label>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || !providerPmId}>
              {isPending ? 'Adding...' : 'Add Payment Method'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
