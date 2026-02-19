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
import { creditNotesApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'

export function CustomerCreditNotesTable({ customerId }: { customerId: string }) {
  const { data: creditNotes, isLoading } = useQuery({
    queryKey: ['customer-credit-notes', customerId],
    queryFn: () => creditNotesApi.list({ customer_id: customerId }),
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

  if (!creditNotes?.length) {
    return <p className="text-sm text-muted-foreground py-4">No credit notes found</p>
  }

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    draft: 'secondary',
    finalized: 'outline',
    voided: 'destructive',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Number</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Reason</TableHead>
            <TableHead>Credit Amount</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {creditNotes.map((cn) => (
            <TableRow key={cn.id}>
              <TableCell>
                {cn.number ? (
                  <Link to={'/admin/credit-notes/' + cn.id} className="text-primary hover:underline">
                    {cn.number}
                  </Link>
                ) : (
                  '\u2014'
                )}
              </TableCell>
              <TableCell>
                <Badge variant={statusVariant[cn.status] ?? 'outline'}>{cn.status}</Badge>
              </TableCell>
              <TableCell>{cn.reason || '\u2014'}</TableCell>
              <TableCell className="font-mono">{formatCents(Number(cn.credit_amount_cents), cn.currency)}</TableCell>
              <TableCell>{format(new Date(cn.created_at), 'MMM d, yyyy')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
