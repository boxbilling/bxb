import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Link, useNavigate } from 'react-router-dom'
import { FileText } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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

interface SubscriptionInvoicesTabProps {
  subscriptionId: string
}

export function SubscriptionInvoicesTab({
  subscriptionId,
}: SubscriptionInvoicesTabProps) {
  const navigate = useNavigate()

  const { data: invoices, isLoading: invoicesLoading } = useQuery({
    queryKey: ['subscription-invoices', subscriptionId],
    queryFn: () => invoicesApi.list({ subscription_id: subscriptionId }),
    enabled: !!subscriptionId,
  })

  const statusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    draft: 'secondary',
    finalized: 'outline',
    paid: 'default',
    voided: 'destructive',
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Invoices
          </CardTitle>
          <Link
            to={`/admin/invoices?subscription_id=${subscriptionId}`}
            className="text-sm text-primary hover:underline"
          >
            View all
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        {invoicesLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : !invoices?.length ? (
          <p className="text-sm text-muted-foreground">No invoices generated for this subscription</p>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Number</TableHead>
                  <TableHead className="hidden md:table-cell">Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="hidden md:table-cell">Issue Date</TableHead>
                  <TableHead className="hidden md:table-cell">Due Date</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoices.map((invoice) => (
                  <TableRow
                    key={invoice.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/admin/invoices/${invoice.id}`)}
                  >
                    <TableCell>
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                        {invoice.invoice_number || '\u2014'}
                      </code>
                    </TableCell>
                    <TableCell className="hidden md:table-cell capitalize">{invoice.invoice_type}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[invoice.status] ?? 'outline'}>{invoice.status}</Badge>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">{invoice.issued_at ? format(new Date(invoice.issued_at), 'MMM d, yyyy') : '\u2014'}</TableCell>
                    <TableCell className="hidden md:table-cell">{invoice.due_date ? format(new Date(invoice.due_date), 'MMM d, yyyy') : '\u2014'}</TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCents(Number(invoice.total), invoice.currency)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
