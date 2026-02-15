import { useState } from 'react'
import { toast } from 'sonner'

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
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { Customer, CustomerCreate, CustomerUpdate } from '@/types/billing'

export function CustomerFormDialog({
  open,
  onOpenChange,
  customer,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  customer?: Customer | null
  onSubmit: (data: CustomerCreate | CustomerUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<CustomerCreate>({
    external_id: customer?.external_id ?? '',
    name: customer?.name ?? '',
    email: customer?.email ?? undefined,
    currency: customer?.currency ?? 'USD',
    timezone: customer?.timezone ?? 'UTC',
    invoice_grace_period: customer?.invoice_grace_period ?? 0,
    net_payment_term: customer?.net_payment_term ?? 30,
  })
  const [billingMetadataJson, setBillingMetadataJson] = useState(
    customer?.billing_metadata ? JSON.stringify(customer.billing_metadata, null, 2) : ''
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    let billing_metadata: { [key: string]: unknown } | undefined
    if (billingMetadataJson.trim()) {
      try {
        billing_metadata = JSON.parse(billingMetadataJson)
      } catch {
        toast.error('Invalid JSON in billing metadata')
        return
      }
    }
    const data = {
      ...formData,
      invoice_grace_period: Number(formData.invoice_grace_period),
      net_payment_term: Number(formData.net_payment_term),
      ...(billing_metadata !== undefined ? { billing_metadata } : {}),
    }
    onSubmit(data)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {customer ? 'Edit Customer' : 'Create Customer'}
            </DialogTitle>
            <DialogDescription>
              {customer
                ? 'Update customer information'
                : 'Add a new customer to your billing system'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="external_id">External ID *</Label>
                <Input
                  id="external_id"
                  value={formData.external_id}
                  onChange={(e) =>
                    setFormData({ ...formData, external_id: e.target.value })
                  }
                  placeholder="cust_123"
                  required
                  disabled={!!customer}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="Acme Corp"
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={formData.email ?? ''}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value || undefined })
                  }
                  placeholder="billing@example.com"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="currency">Currency</Label>
                <Input
                  id="currency"
                  value={formData.currency}
                  onChange={(e) =>
                    setFormData({ ...formData, currency: e.target.value })
                  }
                  placeholder="USD"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Input
                id="timezone"
                value={formData.timezone}
                onChange={(e) =>
                  setFormData({ ...formData, timezone: e.target.value })
                }
                placeholder="UTC"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="invoice_grace_period">Invoice Grace Period (days)</Label>
                <Input
                  id="invoice_grace_period"
                  type="number"
                  value={formData.invoice_grace_period}
                  onChange={(e) =>
                    setFormData({ ...formData, invoice_grace_period: Number(e.target.value) })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="net_payment_term">Net Payment Term (days)</Label>
                <Input
                  id="net_payment_term"
                  type="number"
                  value={formData.net_payment_term}
                  onChange={(e) =>
                    setFormData({ ...formData, net_payment_term: Number(e.target.value) })
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="billing_metadata">Billing Metadata (JSON)</Label>
              <Textarea
                id="billing_metadata"
                value={billingMetadataJson}
                onChange={(e) => setBillingMetadataJson(e.target.value)}
                placeholder='{"key": "value"}'
                rows={3}
              />
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
              {isLoading ? 'Saving...' : customer ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
