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
import type { Subscription, SubscriptionUpdate, BillingTime, TerminationAction } from '@/types/billing'

export function EditSubscriptionDialog({
  open,
  onOpenChange,
  subscription,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscription: Subscription
  onSubmit: (data: SubscriptionUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState({
    billing_time: subscription.billing_time as BillingTime,
    pay_in_advance: subscription.pay_in_advance,
    on_termination_action: subscription.on_termination_action as TerminationAction,
    trial_period_days: subscription.trial_period_days,
  })

  useEffect(() => {
    if (open) {
      setFormData({
        billing_time: subscription.billing_time as BillingTime,
        pay_in_advance: subscription.pay_in_advance,
        on_termination_action: subscription.on_termination_action as TerminationAction,
        trial_period_days: subscription.trial_period_days,
      })
    }
  }, [open, subscription])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      billing_time: formData.billing_time,
      pay_in_advance: formData.pay_in_advance,
      on_termination_action: formData.on_termination_action,
      trial_period_days: formData.trial_period_days,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Edit Subscription</DialogTitle>
            <DialogDescription>
              Update subscription billing settings
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
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
                <Label htmlFor="edit_trial_days">Trial Period (days)</Label>
                <Input
                  id="edit_trial_days"
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
              {isLoading ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
