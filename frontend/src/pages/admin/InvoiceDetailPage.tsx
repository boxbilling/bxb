import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import {
  Download,
  Mail,
  Loader2,
  ScrollText,
  CheckCircle,
  FileMinus,
  FileText,
  Bell,
  Ban,
  Calendar,
  User,
  CreditCard,
  Receipt,
} from 'lucide-react'
import { toast } from 'sonner'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { AuditTrailTimeline } from '@/components/AuditTrailTimeline'
import { invoicesApi, feesApi, taxesApi, creditNotesApi, customersApi } from '@/lib/api'

function formatCurrency(amount: string | number, currency: string = 'USD') {
  const value = typeof amount === 'number' ? amount / 100 : parseFloat(amount)
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(value)
}

type StatusKey = 'draft' | 'finalized' | 'paid' | 'voided'

function StatusBadge({ status }: { status: string }) {
  const variants: Record<StatusKey, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string; className?: string }> = {
    draft: { variant: 'secondary', label: 'Draft' },
    finalized: { variant: 'outline', label: 'Finalized', className: 'border-orange-500 text-orange-600' },
    paid: { variant: 'default', label: 'Paid', className: 'bg-green-600' },
    voided: { variant: 'destructive', label: 'Voided' },
  }

  const config = variants[status as StatusKey]
  if (!config) return <Badge variant="outline">{status}</Badge>
  return (
    <Badge variant={config.variant} className={config.className}>
      {config.label}
    </Badge>
  )
}

function formatTaxRate(rate: string | number): string {
  const num = typeof rate === 'string' ? parseFloat(rate) : rate
  return `${(num * 100).toFixed(2)}%`
}

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [pdfPreviewOpen, setPdfPreviewOpen] = useState(false)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)

  const { data: invoice, isLoading } = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => invoicesApi.get(id!),
    enabled: !!id,
  })

  const { data: customer } = useQuery({
    queryKey: ['customer', invoice?.customer_id],
    queryFn: () => customersApi.get(invoice!.customer_id),
    enabled: !!invoice?.customer_id,
  })

  const { data: fees = [] } = useQuery({
    queryKey: ['invoice-fees', id],
    queryFn: () => feesApi.list({ invoice_id: id! }),
    enabled: !!id,
  })

  const { data: appliedTaxes = [] } = useQuery({
    queryKey: ['invoice-taxes', id],
    queryFn: () => taxesApi.listApplied({ taxable_type: 'invoice', taxable_id: id! }),
    enabled: !!id,
  })

  const { data: settlements = [] } = useQuery({
    queryKey: ['invoice-settlements', id],
    queryFn: () => invoicesApi.listSettlements(id!),
    enabled: !!id,
  })

  const { data: creditNotes = [] } = useQuery({
    queryKey: ['invoice-credit-notes', id],
    queryFn: () => creditNotesApi.list({ invoice_id: id! }),
    enabled: !!id,
  })

  const finalizeMutation = useMutation({
    mutationFn: () => invoicesApi.finalize(id!),
    onSuccess: () => {
      toast.success('Invoice finalized successfully')
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
    onError: () => {
      toast.error('Failed to finalize invoice')
    },
  })

  const voidMutation = useMutation({
    mutationFn: () => invoicesApi.void(id!),
    onSuccess: () => {
      toast.success('Invoice voided successfully')
      queryClient.invalidateQueries({ queryKey: ['invoice', id] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
    onError: () => {
      toast.error('Failed to void invoice')
    },
  })

  const downloadPdfMutation = useMutation({
    mutationFn: () => invoicesApi.downloadPdf(id!),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `invoice-${invoice?.invoice_number ?? id}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    },
    onError: () => {
      toast.error('Failed to download PDF')
    },
  })

  const sendEmailMutation = useMutation({
    mutationFn: () => invoicesApi.sendEmail(id!),
    onSuccess: () => {
      toast.success('Invoice email sent successfully')
    },
    onError: () => {
      toast.error('Failed to send invoice email')
    },
  })

  const sendReminderMutation = useMutation({
    mutationFn: () => invoicesApi.sendReminder(id!),
    onSuccess: () => {
      toast.success('Payment reminder sent successfully')
    },
    onError: () => {
      toast.error('Failed to send payment reminder')
    },
  })

  const previewPdfMutation = useMutation({
    mutationFn: () => invoicesApi.previewPdf(id!),
    onSuccess: (blob) => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl)
      const url = URL.createObjectURL(blob)
      setPdfUrl(url)
      setPdfPreviewOpen(true)
    },
    onError: () => {
      toast.error('Failed to load PDF preview')
    },
  })

  const canDownloadOrEmail = invoice?.status === 'finalized' || invoice?.status === 'paid'
  const canFinalize = invoice?.status === 'draft'
  const canVoid = invoice?.status === 'draft' || invoice?.status === 'finalized'
  const canSendReminder = invoice?.status === 'finalized'

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!invoice) {
    return (
      <div className="text-center py-12">
        <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
        <h2 className="text-xl font-semibold mb-2">Invoice not found</h2>
        <Button variant="outline" onClick={() => navigate('/admin/invoices')}>
          Back to Invoices
        </Button>
      </div>
    )
  }

  const walletCredit = Number(invoice.prepaid_credit_amount)
  const couponDiscount = Number(invoice.coupons_amount_cents)

  const cnStatusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    draft: 'secondary',
    finalized: 'outline',
    voided: 'destructive',
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumbs */}
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/admin/invoices">Invoices</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{invoice.invoice_number}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold tracking-tight">
                Invoice {invoice.invoice_number}
              </h2>
              <StatusBadge status={invoice.status} />
              <Badge variant="outline" className="capitalize text-xs">
                {invoice.invoice_type.replace(/_/g, ' ')}
              </Badge>
            </div>
            <p className="text-muted-foreground mt-1">
              Created {format(new Date(invoice.created_at), 'MMM d, yyyy h:mm a')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canFinalize && (
            <Button
              disabled={finalizeMutation.isPending}
              onClick={() => finalizeMutation.mutate()}
            >
              {finalizeMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle className="mr-2 h-4 w-4" />
              )}
              Finalize
            </Button>
          )}
          {canSendReminder && (
            <Button
              variant="outline"
              disabled={sendReminderMutation.isPending}
              onClick={() => sendReminderMutation.mutate()}
            >
              {sendReminderMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Bell className="mr-2 h-4 w-4" />
              )}
              Send Reminder
            </Button>
          )}
          {canDownloadOrEmail && (
            <>
              <Button
                variant="outline"
                disabled={previewPdfMutation.isPending}
                onClick={() => previewPdfMutation.mutate()}
              >
                {previewPdfMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <FileText className="mr-2 h-4 w-4" />
                )}
                Preview PDF
              </Button>
              <Button
                variant="outline"
                disabled={downloadPdfMutation.isPending}
                onClick={() => downloadPdfMutation.mutate()}
              >
                {downloadPdfMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                Download PDF
              </Button>
              <Button
                variant="outline"
                disabled={sendEmailMutation.isPending}
                onClick={() => sendEmailMutation.mutate()}
              >
                {sendEmailMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Mail className="mr-2 h-4 w-4" />
                )}
                Send Email
              </Button>
            </>
          )}
          {invoice.status === 'finalized' && (
            <Button
              variant="outline"
              onClick={() => {
                navigate('/admin/credit-notes', {
                  state: { invoiceId: invoice.id, customerId: invoice.customer_id },
                })
              }}
            >
              <FileMinus className="mr-2 h-4 w-4" />
              Create Credit Note
            </Button>
          )}
          {canVoid && (
            <Button
              variant="destructive"
              disabled={voidMutation.isPending}
              onClick={() => voidMutation.mutate()}
            >
              {voidMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Ban className="mr-2 h-4 w-4" />
              )}
              Void
            </Button>
          )}
        </div>
      </div>

      {/* Invoice Info Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <User className="h-4 w-4 text-muted-foreground" />
              Customer
            </CardTitle>
          </CardHeader>
          <CardContent>
            {customer ? (
              <div className="space-y-1">
                <Link
                  to={`/admin/customers/${customer.id}`}
                  className="text-sm font-medium hover:underline text-primary"
                >
                  {customer.name || customer.external_id}
                </Link>
                {customer.email && (
                  <p className="text-xs text-muted-foreground">{customer.email}</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{invoice.customer_id}</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              Dates
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Issued</span>
                <span>{invoice.issued_at ? format(new Date(invoice.issued_at), 'MMM d, yyyy') : '\u2014'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Due</span>
                <span>{invoice.due_date ? format(new Date(invoice.due_date), 'MMM d, yyyy') : '\u2014'}</span>
              </div>
              {invoice.paid_at && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Paid</span>
                  <span>{format(new Date(invoice.paid_at), 'MMM d, yyyy')}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground">Period</span>
                <span className="text-xs">
                  {format(new Date(invoice.billing_period_start), 'MMM d')} – {format(new Date(invoice.billing_period_end), 'MMM d, yyyy')}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-muted-foreground" />
              Amount
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {formatCurrency(invoice.total, invoice.currency)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {invoice.currency} · {invoice.status}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="fees">
        <TabsList>
          <TabsTrigger value="fees">
            <Receipt className="mr-2 h-4 w-4" />
            Fees ({fees.length})
          </TabsTrigger>
          <TabsTrigger value="totals">Totals & Tax</TabsTrigger>
          <TabsTrigger value="settlements">Settlements ({settlements.length})</TabsTrigger>
          <TabsTrigger value="credit-notes">Credit Notes ({creditNotes.length})</TabsTrigger>
          <TabsTrigger value="audit">
            <ScrollText className="mr-2 h-4 w-4" />
            Activity
          </TabsTrigger>
        </TabsList>

        {/* Fees Tab */}
        <TabsContent value="fees">
          <Card>
            <CardHeader>
              <CardTitle>Fees Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              {fees.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No fees recorded for this invoice</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Description</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Metric</TableHead>
                      <TableHead className="text-right">Units</TableHead>
                      <TableHead className="text-right">Events</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead className="text-right">Tax</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {fees.map((fee) => (
                      <TableRow key={fee.id}>
                        <TableCell className="font-medium">{fee.description || '\u2014'}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">{fee.fee_type}</Badge>
                        </TableCell>
                        <TableCell>
                          {fee.metric_code ? (
                            <code className="text-xs">{fee.metric_code}</code>
                          ) : '\u2014'}
                        </TableCell>
                        <TableCell className="text-right">{fee.units}</TableCell>
                        <TableCell className="text-right">{fee.events_count}</TableCell>
                        <TableCell className="text-right">
                          {formatCurrency(fee.amount_cents, invoice.currency)}
                        </TableCell>
                        <TableCell className="text-right">
                          {formatCurrency(fee.taxes_amount_cents, invoice.currency)}
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {formatCurrency(fee.total_amount_cents, invoice.currency)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Totals & Tax Tab */}
        <TabsContent value="totals">
          <Card>
            <CardHeader>
              <CardTitle>Invoice Totals</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 max-w-md">
                <div className="flex justify-between text-sm">
                  <span>Subtotal</span>
                  <span>{formatCurrency(invoice.subtotal, invoice.currency)}</span>
                </div>

                {couponDiscount > 0 && (
                  <div className="flex justify-between text-sm text-green-600">
                    <span>Coupon Discount</span>
                    <span>-{formatCurrency(couponDiscount, invoice.currency)}</span>
                  </div>
                )}

                <div className="flex justify-between text-sm">
                  <span>Tax</span>
                  <span>{formatCurrency(invoice.tax_amount, invoice.currency)}</span>
                </div>

                {appliedTaxes.length > 0 && (
                  <div className="pl-4 space-y-1">
                    {appliedTaxes.map((at) => (
                      <div key={at.id} className="flex justify-between text-xs text-muted-foreground">
                        <span>Tax {at.tax_rate ? `(${formatTaxRate(at.tax_rate)})` : ''}</span>
                        <span>{formatCurrency(Number(at.tax_amount_cents), invoice.currency)}</span>
                      </div>
                    ))}
                  </div>
                )}

                {walletCredit > 0 && (
                  <div className="flex justify-between text-sm text-blue-600">
                    <span>Wallet Credits Applied</span>
                    <span>-{formatCurrency(walletCredit, invoice.currency)}</span>
                  </div>
                )}

                {Number(invoice.progressive_billing_credit_amount_cents) > 0 && (
                  <div className="flex justify-between text-sm text-purple-600">
                    <span>Progressive Billing Credits</span>
                    <span>-{formatCurrency(Number(invoice.progressive_billing_credit_amount_cents), invoice.currency)}</span>
                  </div>
                )}

                <Separator />
                <div className="flex justify-between font-medium text-lg">
                  <span>Total</span>
                  <span>{formatCurrency(invoice.total, invoice.currency)}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settlements Tab */}
        <TabsContent value="settlements">
          <Card>
            <CardHeader>
              <CardTitle>Settlement History</CardTitle>
            </CardHeader>
            <CardContent>
              {settlements.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No settlements recorded</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Source ID</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {settlements.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell>
                          <Badge variant="outline" className="capitalize text-xs">
                            {s.settlement_type.replace(/_/g, ' ')}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <code className="text-xs">{s.source_id.substring(0, 12)}...</code>
                        </TableCell>
                        <TableCell>
                          {format(new Date(s.created_at), 'MMM d, yyyy h:mm a')}
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {formatCurrency(Number(s.amount_cents), invoice.currency)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Credit Notes Tab */}
        <TabsContent value="credit-notes">
          <Card>
            <CardHeader>
              <CardTitle>Credit Notes</CardTitle>
            </CardHeader>
            <CardContent>
              {creditNotes.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No credit notes for this invoice</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Number</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {creditNotes.map((cn) => (
                      <TableRow key={cn.id}>
                        <TableCell className="font-medium">
                          {cn.number || cn.id.substring(0, 8)}
                        </TableCell>
                        <TableCell>
                          <Badge variant={cnStatusVariant[cn.status] ?? 'outline'} className="text-xs">
                            {cn.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm capitalize">
                          {cn.reason?.replace(/_/g, ' ') || '\u2014'}
                        </TableCell>
                        <TableCell>
                          {format(new Date(cn.created_at), 'MMM d, yyyy')}
                        </TableCell>
                        <TableCell className="text-right font-medium text-red-600">
                          -{formatCurrency(Number(cn.credit_amount_cents), invoice.currency)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit Trail Tab */}
        <TabsContent value="audit">
          <Card>
            <CardHeader>
              <CardTitle>Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <AuditTrailTimeline resourceType="invoice" resourceId={invoice.id} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

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
            <DialogTitle>Invoice {invoice.invoice_number} — PDF Preview</DialogTitle>
          </DialogHeader>
          {pdfUrl && (
            <iframe
              src={pdfUrl}
              className="w-full flex-1 rounded border"
              style={{ minHeight: '70vh' }}
              title={`Invoice ${invoice.invoice_number} PDF`}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
