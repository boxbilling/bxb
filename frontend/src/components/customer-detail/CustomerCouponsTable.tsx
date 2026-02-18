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
import { customersApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'

export function CustomerCouponsTable({ customerId }: { customerId: string }) {
  const { data: coupons, isLoading } = useQuery({
    queryKey: ['customer-coupons', customerId],
    queryFn: () => customersApi.getAppliedCoupons(customerId),
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

  if (!coupons?.length) {
    return <p className="text-sm text-muted-foreground py-4">No applied coupons found</p>
  }

  const statusVariant: Record<string, 'default' | 'destructive'> = {
    active: 'default',
    terminated: 'destructive',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Coupon ID</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {coupons.map((coupon) => (
            <TableRow key={coupon.id}>
              <TableCell>
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                  {coupon.coupon_id.substring(0, 8)}...
                </code>
              </TableCell>
              <TableCell>
                <Badge variant={statusVariant[coupon.status] ?? 'outline'}>{coupon.status}</Badge>
              </TableCell>
              <TableCell className="font-mono">
                {coupon.amount_cents
                  ? formatCents(Number(coupon.amount_cents), coupon.amount_currency ?? 'USD')
                  : `${coupon.percentage_rate}%`}
              </TableCell>
              <TableCell>{format(new Date(coupon.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
