import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart3 } from 'lucide-react'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { portalApi } from '@/lib/api'
import { usePortalToken } from '@/layouts/PortalLayout'

function formatCurrency(amount: string | number, currency: string): string {
  const value = typeof amount === 'number' ? amount / 100 : parseFloat(amount)
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(value)
}

export default function PortalUsagePage() {
  const token = usePortalToken()
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string>('')

  const { data: invoices = [], isLoading: invoicesLoading } = useQuery({
    queryKey: ['portal-invoices', token],
    queryFn: () => portalApi.listInvoices(token),
    enabled: !!token,
  })

  // Derive unique subscription IDs from invoices
  const subscriptionIds = Array.from(
    new Set(
      invoices
        .map((inv) => inv.subscription_id)
        .filter((id): id is string => id !== null)
    )
  )

  const { data: usage, isLoading: usageLoading } = useQuery({
    queryKey: ['portal-usage', token, selectedSubscriptionId],
    queryFn: () => portalApi.getCurrentUsage(token, selectedSubscriptionId),
    enabled: !!token && !!selectedSubscriptionId,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Usage</h1>
        <p className="text-muted-foreground">
          View your current billing period usage
        </p>
      </div>

      {/* Subscription Selector */}
      <div className="max-w-sm">
        <Select
          value={selectedSubscriptionId}
          onValueChange={setSelectedSubscriptionId}
        >
          <SelectTrigger>
            <SelectValue placeholder="Select a subscription" />
          </SelectTrigger>
          <SelectContent>
            {invoicesLoading ? (
              <SelectItem value="loading" disabled>
                Loading...
              </SelectItem>
            ) : subscriptionIds.length === 0 ? (
              <SelectItem value="none" disabled>
                No subscriptions
              </SelectItem>
            ) : (
              subscriptionIds.map((id) => (
                <SelectItem key={id} value={id}>
                  {id.slice(0, 8)}...
                </SelectItem>
              ))
            )}
          </SelectContent>
        </Select>
      </div>

      {!selectedSubscriptionId ? (
        <Card>
          <CardContent className="py-12 text-center">
            <BarChart3 className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              Select a subscription to view usage
            </p>
          </CardContent>
        </Card>
      ) : usageLoading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      ) : usage ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Current Usage
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              {new Date(usage.from_datetime).toLocaleDateString()} &ndash;{' '}
              {new Date(usage.to_datetime).toLocaleDateString()}
            </p>
          </CardHeader>
          <CardContent>
            {usage.charges.length > 0 ? (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Metric</TableHead>
                      <TableHead>Units</TableHead>
                      <TableHead>Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {usage.charges.map((charge, index) => (
                      <TableRow key={index}>
                        <TableCell className="font-medium">
                          {charge.billable_metric.name}
                          <Badge variant="outline" className="ml-2 text-xs">
                            {charge.billable_metric.code}
                          </Badge>
                        </TableCell>
                        <TableCell>{charge.units}</TableCell>
                        <TableCell>
                          {formatCurrency(
                            Number(charge.amount_cents),
                            usage.currency
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No usage data for this period
              </p>
            )}

            <div className="mt-4 flex justify-end">
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Total</p>
                <p className="text-lg font-bold">
                  {formatCurrency(Number(usage.amount_cents), usage.currency)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
