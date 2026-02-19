import { Fragment, useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { Link, useNavigate } from 'react-router-dom'
import { FileText, ChevronRight, CreditCard, AlertCircle } from 'lucide-react'

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
import { invoicesApi, paymentsApi, creditNotesApi } from '@/lib/api'
import { formatCents, formatCurrency } from '@/lib/utils'

interface SubscriptionInvoicesTabProps {
  subscriptionId: string
}

const invoiceStatusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  draft: 'secondary',
  finalized: 'outline',
  paid: 'default',
  voided: 'destructive',
}

const paymentStatusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  pending: 'secondary',
  processing: 'secondary',
  succeeded: 'default',
  failed: 'destructive',
  refunded: 'outline',
  canceled: 'outline',
}

const providerLabels: Record<string, string> = {
  stripe: 'Stripe',
  manual: 'Manual',
  ucp: 'UCP',
  gocardless: 'GoCardless',
  adyen: 'Adyen',
}

const creditNoteStatusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  draft: 'secondary',
  finalized: 'default',
  voided: 'destructive',
}

const reasonLabels: Record<string, string> = {
  duplicated_charge: 'Duplicated charge',
  product_unsatisfactory: 'Product unsatisfactory',
  order_change: 'Order change',
  order_cancellation: 'Order cancellation',
  fraudulent_charge: 'Fraudulent charge',
  other: 'Other',
}

export function SubscriptionInvoicesTab({
  subscriptionId,
}: SubscriptionInvoicesTabProps) {
  const navigate = useNavigate()
  const [expandedInvoiceId, setExpandedInvoiceId] = useState<string | null>(null)

  const { data: invoices, isLoading: invoicesLoading } = useQuery({
    queryKey: ['subscription-invoices', subscriptionId],
    queryFn: () => invoicesApi.list({ subscription_id: subscriptionId }),
    enabled: !!subscriptionId,
  })

  const customerId = invoices?.[0]?.customer_id
  const invoiceIds = useMemo(() => new Set(invoices?.map((i) => i.id) ?? []), [invoices])

  const { data: payments } = useQuery({
    queryKey: ['subscription-payments', customerId],
    queryFn: () => paymentsApi.list({ customer_id: customerId! }),
    enabled: !!customerId,
  })

  const { data: allCreditNotes } = useQuery({
    queryKey: ['subscription-credit-notes', customerId],
    queryFn: () => creditNotesApi.list({ customer_id: customerId! }),
    enabled: !!customerId,
  })

  const paymentsByInvoice = useMemo(() => {
    const map = new Map<string, typeof payments>()
    if (!payments) return map
    for (const payment of payments) {
      if (!invoiceIds.has(payment.invoice_id)) continue
      const existing = map.get(payment.invoice_id) ?? []
      existing.push(payment)
      map.set(payment.invoice_id, existing)
    }
    return map
  }, [payments, invoiceIds])

  const creditNotes = useMemo(
    () => allCreditNotes?.filter((cn) => invoiceIds.has(cn.invoice_id)) ?? [],
    [allCreditNotes, invoiceIds],
  )

  const toggleExpand = (invoiceId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setExpandedInvoiceId((prev) => (prev === invoiceId ? null : invoiceId))
  }

  return (
    <div className="space-y-4">
      {/* Invoices Card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Invoices & Payments
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
                    <TableHead className="w-8" />
                    <TableHead>Number</TableHead>
                    <TableHead className="hidden md:table-cell">Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden md:table-cell">Issue Date</TableHead>
                    <TableHead className="hidden md:table-cell">Due Date</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoices.map((invoice) => {
                    const invoicePayments = paymentsByInvoice.get(invoice.id) ?? []
                    const hasPayments = invoicePayments.length > 0
                    const isExpanded = expandedInvoiceId === invoice.id

                    return (
                      <Fragment key={invoice.id}>
                        <TableRow
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => navigate(`/admin/invoices/${invoice.id}`)}
                        >
                          <TableCell className="w-8 px-2">
                            {hasPayments && (
                              <button
                                onClick={(e) => toggleExpand(invoice.id, e)}
                                className="p-1 rounded hover:bg-muted"
                                aria-label={isExpanded ? 'Collapse payments' : 'Expand payments'}
                              >
                                <ChevronRight
                                  className={`h-3.5 w-3.5 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                                />
                              </button>
                            )}
                          </TableCell>
                          <TableCell>
                            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                              {invoice.invoice_number || '\u2014'}
                            </code>
                          </TableCell>
                          <TableCell className="hidden md:table-cell capitalize">{invoice.invoice_type}</TableCell>
                          <TableCell>
                            <Badge variant={invoiceStatusVariant[invoice.status] ?? 'outline'}>{invoice.status}</Badge>
                          </TableCell>
                          <TableCell className="hidden md:table-cell">{invoice.issued_at ? format(new Date(invoice.issued_at), 'MMM d, yyyy') : '\u2014'}</TableCell>
                          <TableCell className="hidden md:table-cell">{invoice.due_date ? format(new Date(invoice.due_date), 'MMM d, yyyy') : '\u2014'}</TableCell>
                          <TableCell className="text-right font-mono">
                            {formatCents(Number(invoice.total), invoice.currency)}
                          </TableCell>
                        </TableRow>
                        {isExpanded && invoicePayments.map((payment) => (
                          <TableRow key={`payment-${payment.id}`} className="bg-muted/30">
                            <TableCell />
                            <TableCell colSpan={2}>
                              <div className="flex items-center gap-2 pl-2">
                                <CreditCard className="h-3.5 w-3.5 text-muted-foreground" />
                                <Badge variant={paymentStatusVariant[payment.status] ?? 'secondary'} className="text-xs">
                                  {payment.status}
                                </Badge>
                                <Badge variant="outline" className="text-xs">
                                  {providerLabels[payment.provider] || payment.provider}
                                </Badge>
                              </div>
                            </TableCell>
                            <TableCell className="hidden md:table-cell" />
                            <TableCell colSpan={2} className="hidden md:table-cell">
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                {payment.completed_at
                                  ? format(new Date(payment.completed_at), 'MMM d, yyyy')
                                  : 'Pending'}
                                {payment.failure_reason && (
                                  <span className="flex items-center gap-1 text-destructive">
                                    <AlertCircle className="h-3 w-3" />
                                    {payment.failure_reason}
                                  </span>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="text-right font-mono text-xs">
                              {formatCurrency(payment.amount, payment.currency)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </Fragment>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Credit Notes Card */}
      {creditNotes.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Credit Notes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Number</TableHead>
                    <TableHead className="hidden md:table-cell">Reason</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {creditNotes.map((cn) => (
                    <TableRow
                      key={cn.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate(`/admin/credit-notes/${cn.id}`)}
                    >
                      <TableCell>
                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                          {cn.number}
                        </code>
                      </TableCell>
                      <TableCell className="hidden md:table-cell capitalize">
                        {reasonLabels[cn.reason] || cn.reason}
                      </TableCell>
                      <TableCell>
                        <Badge variant={creditNoteStatusVariant[cn.status] ?? 'outline'}>
                          {cn.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatCents(Number(cn.total_amount_cents), cn.currency)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
