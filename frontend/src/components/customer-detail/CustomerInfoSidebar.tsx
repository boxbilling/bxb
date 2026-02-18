import { useState } from 'react'
import { format } from 'date-fns'
import { Copy, Check } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import type { Customer } from '@/types/billing'

export function CustomerInfoSidebar({ customer }: { customer: Customer }) {
  const [copied, setCopied] = useState(false)

  const handleCopyExternalId = async () => {
    await navigator.clipboard.writeText(customer.external_id)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Card>
      <CardContent className="pt-5">
        {/* Customer Info */}
        <div className="grid gap-3 text-sm">
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">External ID</span>
            <div className="flex items-center gap-1.5">
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{customer.external_id}</code>
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleCopyExternalId}>
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              </Button>
            </div>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Email</span>
            {customer.email ? (
              <a href={`mailto:${customer.email}`} className="text-primary hover:underline">
                {customer.email}
              </a>
            ) : (
              <span>{'\u2014'}</span>
            )}
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
        </div>

        <Separator className="my-3" />

        {/* Billing Metadata */}
        <div className="space-y-1 text-sm">
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
            <p>None</p>
          )}
        </div>

        <Separator className="my-3" />

        {/* Dates */}
        <div className="grid gap-3 text-sm">
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
  )
}
