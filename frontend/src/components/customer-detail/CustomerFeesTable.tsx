import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'

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
import { feesApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'

export function CustomerFeesTable({ customerId }: { customerId: string }) {
  const { data: fees, isLoading } = useQuery({
    queryKey: ['customer-fees', customerId],
    queryFn: () => feesApi.list({ customer_id: customerId }),
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

  if (!fees?.length) {
    return <p className="text-sm text-muted-foreground py-4">No fees found</p>
  }

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    pending: 'secondary',
    succeeded: 'default',
    failed: 'destructive',
    refunded: 'outline',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Type</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Payment Status</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {fees.map((fee) => (
            <TableRow key={fee.id}>
              <TableCell>
                <Badge variant="outline">{fee.fee_type}</Badge>
              </TableCell>
              <TableCell>{fee.description || fee.metric_code || '\u2014'}</TableCell>
              <TableCell>
                <Badge variant={statusVariant[fee.payment_status] ?? 'outline'}>{fee.payment_status}</Badge>
              </TableCell>
              <TableCell className="font-mono">{formatCents(Number(fee.total_amount_cents))}</TableCell>
              <TableCell>{format(new Date(fee.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
