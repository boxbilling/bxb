import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { FileText, Download, Eye, CreditCard, Loader2, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { format } from 'date-fns'

import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { portalApi } from '@/lib/api'
import { formatCurrency } from '@/lib/utils'
import { usePortalToken } from '@/layouts/PortalLayout'
import { useIsMobile } from '@/hooks/use-mobile'
import type { components } from '@/lib/schema'

type InvoiceResponse = components['schemas']['InvoiceResponse']
type PaymentResponse = components['schemas']['PaymentResponse']

const statusColors: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  draft: 'outline',
  pending: 'secondary',
  finalized: 'secondary',
  paid: 'default',
  voided: 'outline',
  failed: 'destructive',
}

const paymentStatusIcons: Record<string, typeof CheckCircle> = {
  succeeded: CheckCircle,
  failed: XCircle,
  pending: Clock,
  processing: Loader2,
  refunded: AlertCircle,
  canceled: XCircle,
}

const paymentStatusColors: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  succeeded: 'default',
  failed: 'destructive',
  pending: 'secondary',
  processing: 'secondary',
  refunded: 'outline',
  canceled: 'outline',
}

export default function PortalInvoicesPage() {
  const token = usePortalToken()
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceResponse | null>(null)
  const [pdfPreviewOpen, setPdfPreviewOpen] = useState(false)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)

  const { data: invoices = [], isLoading } = useQuery({
    queryKey: ['portal-invoices', token],
    queryFn: () => portalApi.listInvoices(token),
    enabled: !!token,
  })

  const { data: invoicePayments = [] } = useQuery({
    queryKey: ['portal-invoice-payments', token, selectedInvoice?.id],
    queryFn: () => portalApi.getInvoicePayments(token, selectedInvoice!.id),
    enabled: !!token && !!selectedInvoice,
  })

  const handleDownloadPdf = async (invoiceId: string, invoiceNumber: string) => {
    const blob = await portalApi.downloadInvoicePdf(token, invoiceId)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `invoice-${invoiceNumber}.pdf`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    a.remove()
  }

  const handlePreviewPdf = async (invoiceId: string) => {
    const blob = await portalApi.previewInvoicePdf(token, invoiceId)
    if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    const url = URL.createObjectURL(blob)
    setPdfUrl(url)
    setPdfPreviewOpen(true)
  }

  const payMutation = useMutation({
    mutationFn: (invoiceId: string) => {
      const currentUrl = window.location.href
      return portalApi.payInvoice(token, invoiceId, currentUrl, currentUrl)
    },
    onSuccess: (data) => {
      window.open(data.checkout_url, '_blank')
    },
  })

  const isMobile = useIsMobile()

  return (
    <div className="space-y-4 md:space-y-6">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold">Invoices</h1>
        <p className="text-sm md:text-base text-muted-foreground">View, pay, and download your invoices</p>
      </div>

      {/* Mobile card view */}
      {isMobile ? (
        <div className="space-y-3">
          {isLoading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full rounded-lg" />
            ))
          ) : invoices.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <FileText className="mx-auto h-10 w-10 mb-3 text-muted-foreground/50" />
              No invoices found
            </div>
          ) : (
            invoices.map((invoice) => (
              <button
                key={invoice.id}
                className="w-full text-left rounded-lg border p-4 active:bg-accent/50 transition-colors"
                onClick={() => setSelectedInvoice(invoice)}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-sm">{invoice.invoice_number}</span>
                  <Badge variant={statusColors[invoice.status] || 'secondary'}>
                    {invoice.status}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-lg font-bold">
                    {formatCurrency(invoice.total, invoice.currency)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {format(new Date(invoice.created_at), 'MMM d, yyyy')}
                  </span>
                </div>
              </button>
            ))
          )}
        </div>
      ) : (
        /* Desktop table view */
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Number</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-[180px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  </TableRow>
                ))
              ) : invoices.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                    No invoices found
                  </TableCell>
                </TableRow>
              ) : (
                invoices.map((invoice) => (
                  <TableRow key={invoice.id}>
                    <TableCell className="font-medium">
                      {invoice.invoice_number}
                    </TableCell>
                    <TableCell>
                      {format(new Date(invoice.created_at), 'MMM d, yyyy')}
                    </TableCell>
                    <TableCell>
                      {formatCurrency(invoice.total, invoice.currency)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusColors[invoice.status] || 'secondary'}>
                        {invoice.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setSelectedInvoice(invoice)}
                          title="View details"
                        >
                          <FileText className="h-4 w-4" />
                        </Button>
                        {(invoice.status === 'finalized' || invoice.status === 'paid') && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handlePreviewPdf(invoice.id)}
                            title="Preview PDF"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        )}
                        {(invoice.status === 'finalized' || invoice.status === 'paid') && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDownloadPdf(invoice.id, invoice.invoice_number)}
                            title="Download PDF"
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        )}
                        {invoice.status === 'finalized' && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => payMutation.mutate(invoice.id)}
                            disabled={payMutation.isPending}
                            title="Pay now"
                          >
                            {payMutation.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <CreditCard className="h-4 w-4" />
                            )}
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Invoice Detail Dialog */}
      <Dialog open={!!selectedInvoice} onOpenChange={() => setSelectedInvoice(null)}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Invoice {selectedInvoice?.invoice_number}</DialogTitle>
            <DialogDescription>Invoice details and payment history</DialogDescription>
          </DialogHeader>
          {selectedInvoice && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 md:gap-4">
                <div>
                  <p className="text-xs md:text-sm text-muted-foreground">Amount</p>
                  <p className="text-base md:text-lg font-semibold">
                    {formatCurrency(selectedInvoice.total, selectedInvoice.currency)}
                  </p>
                </div>
                <div>
                  <p className="text-xs md:text-sm text-muted-foreground">Status</p>
                  <Badge variant={statusColors[selectedInvoice.status] || 'secondary'}>
                    {selectedInvoice.status}
                  </Badge>
                </div>
                <div>
                  <p className="text-xs md:text-sm text-muted-foreground">Issue Date</p>
                  <p className="text-sm">{format(new Date(selectedInvoice.created_at), 'PPP')}</p>
                </div>
                {selectedInvoice.due_date && (
                  <div>
                    <p className="text-xs md:text-sm text-muted-foreground">Due Date</p>
                    <p className="text-sm">{format(new Date(selectedInvoice.due_date), 'PPP')}</p>
                  </div>
                )}
                <div>
                  <p className="text-xs md:text-sm text-muted-foreground">Invoice Type</p>
                  <p className="text-sm">{selectedInvoice.invoice_type}</p>
                </div>
                <div>
                  <p className="text-xs md:text-sm text-muted-foreground">Currency</p>
                  <Badge variant="outline">{selectedInvoice.currency}</Badge>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 justify-end">
                {selectedInvoice.status === 'finalized' && (
                  <Button
                    size="sm"
                    className="min-h-[44px] md:min-h-0"
                    onClick={() => payMutation.mutate(selectedInvoice.id)}
                    disabled={payMutation.isPending}
                  >
                    {payMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <CreditCard className="mr-2 h-4 w-4" />
                    )}
                    Pay Now
                  </Button>
                )}
                {(selectedInvoice.status === 'finalized' || selectedInvoice.status === 'paid') && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="min-h-[44px] md:min-h-0"
                    onClick={() => handlePreviewPdf(selectedInvoice.id)}
                  >
                    <Eye className="mr-2 h-4 w-4" />
                    Preview
                  </Button>
                )}
                {(selectedInvoice.status === 'finalized' || selectedInvoice.status === 'paid') && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="min-h-[44px] md:min-h-0"
                    onClick={() => handleDownloadPdf(selectedInvoice.id, selectedInvoice.invoice_number)}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Download
                  </Button>
                )}
              </div>

              {/* Payment History */}
              {invoicePayments.length > 0 && (
                <>
                  <Separator />
                  <div>
                    <h4 className="text-sm font-medium mb-3">Payment History</h4>
                    <div className="space-y-2">
                      {invoicePayments.map((payment: PaymentResponse) => {
                        const StatusIcon = paymentStatusIcons[payment.status] || AlertCircle
                        return (
                          <div
                            key={payment.id}
                            className="flex items-center justify-between rounded-md border px-3 py-2"
                          >
                            <div className="flex items-center gap-2">
                              <StatusIcon className={`h-4 w-4 ${payment.status === 'succeeded' ? 'text-green-600' : payment.status === 'failed' ? 'text-red-600' : 'text-muted-foreground'}`} />
                              <div>
                                <p className="text-sm font-medium">
                                  {formatCurrency(payment.amount, payment.currency)}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {format(new Date(payment.created_at), 'MMM d, yyyy h:mm a')} via {payment.provider}
                                </p>
                              </div>
                            </div>
                            <Badge variant={paymentStatusColors[payment.status] || 'secondary'}>
                              {payment.status}
                            </Badge>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* PDF Preview Dialog */}
      <Dialog open={pdfPreviewOpen} onOpenChange={(open) => {
        if (!open && pdfUrl) {
          URL.revokeObjectURL(pdfUrl)
          setPdfUrl(null)
        }
        setPdfPreviewOpen(open)
      }}>
        <DialogContent className="sm:max-w-[800px] h-[85vh]">
          <DialogHeader>
            <DialogTitle>Invoice PDF Preview</DialogTitle>
            <DialogDescription>Viewing invoice document</DialogDescription>
          </DialogHeader>
          {pdfUrl && (
            <iframe
              src={pdfUrl}
              className="w-full flex-1 rounded border"
              style={{ minHeight: '70vh' }}
              title="Invoice PDF Preview"
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
