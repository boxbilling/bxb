import { useQuery } from '@tanstack/react-query'
import { ArrowLeftRight } from 'lucide-react'
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
import { formatCurrency } from '@/lib/utils'
import { usePortalToken } from '@/layouts/PortalLayout'
import { useIsMobile } from '@/hooks/use-mobile'

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

export default function PortalPaymentsPage() {
  const token = usePortalToken()

  const { data: payments = [], isLoading } = useQuery({
    queryKey: ['portal-payments', token],
    queryFn: () => portalApi.listPayments(token),
    enabled: !!token,
  })

  const isMobile = useIsMobile()

  return (
    <div className="space-y-4 md:space-y-6">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold">Payments</h1>
        <p className="text-sm md:text-base text-muted-foreground">Your payment history</p>
      </div>

      {isMobile ? (
        <div className="space-y-3">
          {isLoading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full rounded-lg" />
            ))
          ) : payments.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <ArrowLeftRight className="mx-auto h-10 w-10 mb-3 text-muted-foreground/50" />
              No payments found
            </div>
          ) : (
            payments.map((payment) => (
              <div key={payment.id} className="rounded-lg border p-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-lg font-bold">
                    {formatCurrency(payment.amount, payment.currency)}
                  </span>
                  <Badge variant={statusColors[payment.status] || 'secondary'}>
                    {payment.status}
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{format(new Date(payment.created_at), 'MMM d, yyyy')}</span>
                  <Badge variant="outline" className="text-[10px]">
                    {providerLabels[payment.provider] || payment.provider}
                  </Badge>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
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
                      {formatCurrency(payment.amount, payment.currency)}
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
      )}
    </div>
  )
}
