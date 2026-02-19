import { useState } from 'react'
import { format } from 'date-fns'
import { Copy, Check, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { customersApi, billingEntitiesApi } from '@/lib/api'
import type { Customer } from '@/types/billing'

export function CustomerInfoSidebar({ customer }: { customer: Customer }) {
  const [copied, setCopied] = useState(false)

  const { data: integrationMappings } = useQuery({
    queryKey: ['customer-integration-mappings', customer.id],
    queryFn: () => customersApi.getIntegrationMappings(customer.id),
  })

  const { data: billingEntities } = useQuery({
    queryKey: ['billing-entities'],
    queryFn: () => billingEntitiesApi.list(),
    enabled: !!customer.billing_entity_id,
  })

  const billingEntity = billingEntities?.find(
    (e) => e.id === customer.billing_entity_id
  )

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

        {/* Billing Entity */}
        <div className="space-y-1 text-sm">
          <span className="text-muted-foreground">Billing Entity</span>
          {customer.billing_entity_id ? (
            billingEntity ? (
              <p>
                <Link
                  to={`/admin/billing-entities/${billingEntity.code}`}
                  className="text-primary hover:underline"
                >
                  {billingEntity.name}
                </Link>
              </p>
            ) : (
              <p className="text-muted-foreground">{'\u2014'}</p>
            )
          ) : (
            <p className="text-muted-foreground">Default</p>
          )}
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

        <Separator className="my-3" />

        {/* Integration Mappings */}
        <div className="space-y-2 text-sm">
          <span className="text-muted-foreground">Integrations</span>
          {integrationMappings && integrationMappings.length > 0 ? (
            <div className="space-y-2">
              {integrationMappings.map((mapping) => (
                <div key={mapping.id} className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <span className="font-medium">{mapping.integration_name}</span>
                    <p className="font-mono text-xs text-muted-foreground truncate">
                      {mapping.external_customer_id}
                    </p>
                  </div>
                  <Link
                    to={`/admin/integrations/${mapping.integration_id}`}
                    className="text-muted-foreground hover:text-primary shrink-0"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Link>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">No integrations linked</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
