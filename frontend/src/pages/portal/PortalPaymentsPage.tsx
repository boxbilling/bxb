import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { portalApi } from '@/lib/api'
import { usePortalToken } from '@/layouts/PortalLayout'

const statusColors: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  pending: 'secondary',
  processing: 'secondary',
  succeeded: 'default',
  failed: 'destructive',
  refunded: 'outline',
  canceled: 'outline',
}

const providerLabels: Record<string, string> = {
  stripe: 'Stripe',
  ucp: 'UCP',
  manual: 'Manual',
}

function formatAmount(amount: string, currency: string): string {
  const num = parseFloat(amount)
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(num)
}

export default function PortalPaymentsPage() {
  const token = usePortalToken()

  const { data: payments = [], isLoading } = useQuery({
    queryKey: ['portal-payments', token],
    queryFn: () => portalApi.listPayments(token),
    enabled: !!token,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Payments</h1>
        <p className="text-muted-foreground">Your payment history</p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Provider</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                </TableRow>
              ))
            ) : payments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                  No payments found
                </TableCell>
              </TableRow>
            ) : (
              payments.map((payment) => (
                <TableRow key={payment.id}>
                  <TableCell>
                    {format(new Date(payment.created_at), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell className="font-medium">
                    {formatAmount(payment.amount, payment.currency)}
                  </TableCell>
                  <TableCell>
                    <Badge variant={statusColors[payment.status] || 'secondary'}>
                      {payment.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {providerLabels[payment.provider] || payment.provider}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
