import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Link, useNavigate } from 'react-router-dom'

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
import { subscriptionsApi } from '@/lib/api'

interface CustomerSubscriptionsTableProps {
  customerId: string
  plans?: Array<{ id: string; name: string; code: string }>
}

export function CustomerSubscriptionsTable({ customerId, plans }: CustomerSubscriptionsTableProps) {
  const navigate = useNavigate()
  const { data: subscriptions, isLoading } = useQuery({
    queryKey: ['customer-subscriptions', customerId],
    queryFn: () => subscriptionsApi.list({ customer_id: customerId }),
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

  if (!subscriptions?.length) {
    return <p className="text-sm text-muted-foreground py-4">No subscriptions found</p>
  }

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    active: 'default',
    pending: 'secondary',
    canceled: 'outline',
    terminated: 'destructive',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>External ID</TableHead>
            <TableHead>Plan</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Billing Time</TableHead>
            <TableHead>Started At</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {subscriptions.map((sub) => (
            <TableRow
              key={sub.id}
              className="cursor-pointer hover:bg-muted/50"
              onClick={() => navigate('/admin/subscriptions/' + sub.id)}
            >
              <TableCell>
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{sub.external_id}</code>
              </TableCell>
              <TableCell>
                {plans?.find((p) => p.id === sub.plan_id)?.name ? (
                  <Link
                    to={'/admin/plans/' + sub.plan_id}
                    className="hover:underline text-primary"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {plans.find((p) => p.id === sub.plan_id)!.name}
                  </Link>
                ) : (
                  '\u2014'
                )}
              </TableCell>
              <TableCell>
                <Badge variant={statusVariant[sub.status] ?? 'outline'}>{sub.status}</Badge>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{sub.billing_time}</Badge>
              </TableCell>
              <TableCell>{sub.started_at ? format(new Date(sub.started_at), 'MMM d, yyyy') : '\u2014'}</TableCell>
              <TableCell>{format(new Date(sub.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
