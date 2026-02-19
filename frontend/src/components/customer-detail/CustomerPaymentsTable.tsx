import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { paymentsApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'

export function CustomerPaymentsTable({ customerId }: { customerId: string }) {
  const { data: payments, isLoading } = useQuery({
    queryKey: ['customer-payments', customerId],
    queryFn: () => paymentsApi.list({ customer_id: customerId }),
  })

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (!payments?.length) {
    return <p className="text-sm text-muted-foreground py-4">No payments found</p>
  }

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    pending: 'secondary',
    processing: 'outline',
    succeeded: 'default',
    failed: 'destructive',
    refunded: 'outline',
    canceled: 'secondary',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Amount</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Invoice</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {payments.map((payment) => (
            <TableRow key={payment.id}>
              <TableCell className="font-mono">{formatCents(Number(payment.amount), payment.currency)}</TableCell>
              <TableCell>
                <Badge variant={statusVariant[payment.status] ?? 'outline'}>{payment.status}</Badge>
              </TableCell>
              <TableCell>
                {payment.invoice_id ? (
                  <Link to={'/admin/invoices/' + payment.invoice_id} className="text-primary hover:underline">
                    View Invoice
                  </Link>
                ) : (
                  '\u2014'
                )}
              </TableCell>
              <TableCell>{payment.provider || '\u2014'}</TableCell>
              <TableCell>{format(new Date(payment.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
