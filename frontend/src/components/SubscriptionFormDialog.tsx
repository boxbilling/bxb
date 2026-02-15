import { useState, useEffect } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import type { SubscriptionCreate, Customer, Plan, BillingTime, TerminationAction } from '@/types/billing'

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}

export function SubscriptionFormDialog({
  open,
  onOpenChange,
  customers,
  plans,
  onSubmit,
  isLoading,
  defaultCustomerId,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  customers: Customer[]
  plans: Plan[]
  onSubmit: (data: SubscriptionCreate) => void
  isLoading: boolean
  defaultCustomerId?: string
}) {
  const [formData, setFormData] = useState<SubscriptionCreate>({
    external_id: '',
    customer_id: defaultCustomerId ?? '',
    plan_id: '',
    billing_time: 'calendar',
    trial_period_days: 0,
    pay_in_advance: false,
    on_termination_action: 'generate_invoice',
  })

  useEffect(() => {
    if (open) {
      setFormData({
        external_id: '',
        customer_id: defaultCustomerId ?? '',
        plan_id: '',
        billing_time: 'calendar',
        trial_period_days: 0,
        pay_in_advance: false,
        on_termination_action: 'generate_invoice',
      })
    }
  }, [open, defaultCustomerId])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create Subscription</DialogTitle>
            <DialogDescription>
              Subscribe a customer to a plan
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="external_id">External ID *</Label>
              <Input
                id="external_id"
                value={formData.external_id}
                onChange={(e) =>
                  setFormData({ ...formData, external_id: e.target.value })
                }
                placeholder="sub_123"
                required
              />
            </div>

            <div className="space-y-2">
              <Label>Customer *</Label>
              <Select
                value={formData.customer_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, customer_id: value })
                }
                disabled={!!defaultCustomerId}
              >
                <SelectTrigger>
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

            <div className="space-y-2">
              <Label>Plan *</Label>
              <Select
                value={formData.plan_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, plan_id: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a plan" />
                </SelectTrigger>
                <SelectContent>
                  {plans.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} — {formatCurrency(p.amount_cents, p.currency)}/{p.interval}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Separator />

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Billing Time</Label>
                <Select
                  value={formData.billing_time}
                  onValueChange={(value: BillingTime) =>
                    setFormData({ ...formData, billing_time: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="calendar">Calendar</SelectItem>
                    <SelectItem value="anniversary">Anniversary</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="trial_days">Trial Period (days)</Label>
                <Input
                  id="trial_days"
                  type="number"
                  value={formData.trial_period_days}
                  onChange={(e) =>
                    setFormData({ ...formData, trial_period_days: parseInt(e.target.value) || 0 })
                  }
                  min={0}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Pay in Advance</Label>
                <Select
                  value={formData.pay_in_advance ? 'true' : 'false'}
                  onValueChange={(value) =>
                    setFormData({ ...formData, pay_in_advance: value === 'true' })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="false">No (pay in arrears)</SelectItem>
                    <SelectItem value="true">Yes (pay in advance)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>On Termination</Label>
                <Select
                  value={formData.on_termination_action}
                  onValueChange={(value: TerminationAction) =>
                    setFormData({ ...formData, on_termination_action: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="generate_invoice">Generate invoice</SelectItem>
                    <SelectItem value="generate_credit_note">Generate credit note</SelectItem>
                    <SelectItem value="skip">Skip</SelectItem>
                  </SelectContent>
                </Select>
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
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Creating...' : 'Create Subscription'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
