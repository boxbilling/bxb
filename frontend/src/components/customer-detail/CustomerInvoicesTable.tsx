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
import { invoicesApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'

export function CustomerInvoicesTable({ customerId }: { customerId: string }) {
  const { data: invoices, isLoading } = useQuery({
    queryKey: ['customer-invoices', customerId],
    queryFn: () => invoicesApi.list({ customer_id: customerId }),
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

  if (!invoices?.length) {
    return <p className="text-sm text-muted-foreground py-4">No invoices found</p>
  }

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    draft: 'secondary',
    finalized: 'outline',
    paid: 'default',
    voided: 'destructive',
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Number</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Total</TableHead>
            <TableHead>Issued At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invoices.map((invoice) => (
            <TableRow key={invoice.id}>
              <TableCell>{invoice.invoice_number || '\u2014'}</TableCell>
              <TableCell>
                <Badge variant={statusVariant[invoice.status] ?? 'outline'}>{invoice.status}</Badge>
              </TableCell>
              <TableCell className="font-mono">{formatCents(Number(invoice.total), invoice.currency)}</TableCell>
              <TableCell>{invoice.issued_at ? format(new Date(invoice.issued_at), 'MMM d, yyyy') : '\u2014'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
