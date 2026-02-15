import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import type { PaymentMethodCreate } from '@/types/billing'

export function PaymentMethodFormDialog({
  open,
  onOpenChange,
  onSubmit,
  isLoading,
  customers,
  defaultCustomerId,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: PaymentMethodCreate) => void
  isLoading: boolean
  customers: { id: string; name: string }[]
  defaultCustomerId?: string
}) {
  const [formData, setFormData] = useState<PaymentMethodCreate>({
    customer_id: defaultCustomerId ?? '',
    provider: 'stripe',
    provider_payment_method_id: '',
    type: 'card',
    is_default: false,
    details: {},
  })
  const [last4, setLast4] = useState('')
  const [brand, setBrand] = useState('')
  const [expMonth, setExpMonth] = useState('')
  const [expYear, setExpYear] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const details: Record<string, unknown> = {}
    if (last4) details.last4 = last4
    if (brand) details.brand = brand
    if (expMonth) details.exp_month = Number(expMonth)
    if (expYear) details.exp_year = Number(expYear)
    onSubmit({ ...formData, details })
  }

  const resetForm = () => {
    setFormData({
      customer_id: defaultCustomerId ?? '',
      provider: 'stripe',
      provider_payment_method_id: '',
      type: 'card',
      is_default: false,
      details: {},
    })
    setLast4('')
    setBrand('')
    setExpMonth('')
    setExpYear('')
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen) resetForm()
        onOpenChange(isOpen)
      }}
    >
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add Payment Method</DialogTitle>
            <DialogDescription>
              Register a new payment method for a customer
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="pm-customer">Customer *</Label>
              <Select
                value={formData.customer_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, customer_id: value })
                }
                disabled={!!defaultCustomerId}
              >
                <SelectTrigger id="pm-customer">
                  <SelectValue placeholder="Select a customer" />
                </SelectTrigger>
                <SelectContent>
                  {customers.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pm-provider">Provider *</Label>
                <Select
                  value={formData.provider}
                  onValueChange={(value) =>
                    setFormData({ ...formData, provider: value })
                  }
                >
                  <SelectTrigger id="pm-provider">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="stripe">Stripe</SelectItem>
                    <SelectItem value="gocardless">GoCardless</SelectItem>
                    <SelectItem value="adyen">Adyen</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="pm-type">Type *</Label>
                <Select
                  value={formData.type}
                  onValueChange={(value) =>
                    setFormData({ ...formData, type: value })
                  }
                >
                  <SelectTrigger id="pm-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="card">Card</SelectItem>
                    <SelectItem value="bank_account">Bank Account</SelectItem>
                    <SelectItem value="direct_debit">Direct Debit</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="pm-provider-id">Provider Payment Method ID *</Label>
              <Input
                id="pm-provider-id"
                value={formData.provider_payment_method_id}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    provider_payment_method_id: e.target.value,
                  })
                }
                placeholder="pm_1234567890"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pm-brand">Card Brand</Label>
                <Input
                  id="pm-brand"
                  value={brand}
                  onChange={(e) => setBrand(e.target.value)}
                  placeholder="Visa"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pm-last4">Last 4 Digits</Label>
                <Input
                  id="pm-last4"
                  value={last4}
                  onChange={(e) => setLast4(e.target.value)}
                  placeholder="4242"
                  maxLength={4}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="pm-exp-month">Expiry Month</Label>
                <Input
                  id="pm-exp-month"
                  type="number"
                  value={expMonth}
                  onChange={(e) => setExpMonth(e.target.value)}
                  placeholder="12"
                  min={1}
                  max={12}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="pm-exp-year">Expiry Year</Label>
                <Input
                  id="pm-exp-year"
                  type="number"
                  value={expYear}
                  onChange={(e) => setExpYear(e.target.value)}
                  placeholder="2025"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isLoading || !formData.customer_id || !formData.provider_payment_method_id}
            >
              {isLoading ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
