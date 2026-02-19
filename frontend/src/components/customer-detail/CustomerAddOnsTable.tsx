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

export function CustomerAddOnsTable({ customerId }: { customerId: string }) {
  const { data: addOns, isLoading } = useQuery({
    queryKey: ['customer-applied-add-ons', customerId],
    queryFn: () => customersApi.getAppliedAddOns(customerId),
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

  if (!addOns?.length) {
    return <p className="text-sm text-muted-foreground py-4">No add-ons applied</p>
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Add-On ID</TableHead>
            <TableHead>Amount</TableHead>
            <TableHead>Currency</TableHead>
            <TableHead>Applied Date</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {addOns.map((addOn) => (
            <TableRow key={addOn.id}>
              <TableCell>
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                  {addOn.add_on_id.substring(0, 8)}...
                </code>
              </TableCell>
              <TableCell className="font-mono">
                {formatCents(addOn.amount_cents, addOn.amount_currency)}
              </TableCell>
              <TableCell>
                <Badge variant="outline">{addOn.amount_currency}</Badge>
              </TableCell>
              <TableCell>{format(new Date(addOn.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
