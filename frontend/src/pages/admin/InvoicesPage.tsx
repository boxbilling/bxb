import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Search, Download, Eye, FileText, FileMinus, Mail, Loader2 } from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { invoicesApi, feesApi, taxesApi, creditNotesApi, subscriptionsApi } from '@/lib/api'
import type { Invoice, InvoiceStatus, InvoicePreviewResponse } from '@/types/billing'

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

function InvoiceFeesBreakdown({ invoiceId, currency }: { invoiceId: string; currency: string }) {
  const { data: fees = [], isLoading } = useQuery({
    queryKey: ['invoice-fees', invoiceId],
    queryFn: () => feesApi.list({ invoice_id: invoiceId }),
  })

  if (isLoading) return <Skeleton className="h-20 w-full" />
  if (fees.length === 0) return null

  return (
    <div>
      <h4 className="font-medium mb-3">Fees Breakdown</h4>
      <div className="space-y-2">
        {fees.map((fee) => (
          <div key={fee.id} className="border rounded-lg p-3 text-sm">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-medium">{fee.description || fee.fee_type}</span>
                <Badge variant="outline" className="ml-2 text-xs">{fee.fee_type}</Badge>
                {fee.metric_code && (
                  <span className="ml-2 text-xs text-muted-foreground">({fee.metric_code})</span>
                )}
              </div>
              <span className="font-medium">{formatCurrency(fee.amount_cents, currency)}</span>
            </div>
            <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
              <span>{fee.units} units</span>
              <span>{fee.events_count} events</span>
              <span>Tax: {formatCurrency(fee.taxes_amount_cents, currency)}</span>
              <span className="font-medium text-foreground">Total: {formatCurrency(fee.total_amount_cents, currency)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function AppliedTaxesBreakdown({ invoiceId }: { invoiceId: string }) {
  const { data: appliedTaxes = [] } = useQuery({
    queryKey: ['invoice-taxes', invoiceId],
    queryFn: () => taxesApi.listApplied({ taxable_type: 'invoice', taxable_id: invoiceId }),
  })

  if (appliedTaxes.length === 0) return null

  return (
    <>
      {appliedTaxes.map((at) => (
        <div key={at.id} className="flex justify-between text-xs text-muted-foreground pl-4">
          <span>Tax {at.tax_rate ? `(${formatTaxRate(at.tax_rate)})` : ''}</span>
          <span>{formatCurrency(Number(at.tax_amount_cents))}</span>
        </div>
      ))}
    </>
  )
}

function InvoiceSettlementsSection({ invoiceId, currency }: { invoiceId: string; currency: string }) {
  const { data: settlements = [] } = useQuery({
    queryKey: ['invoice-settlements', invoiceId],
    queryFn: () => invoicesApi.listSettlements(invoiceId),
  })

  if (settlements.length === 0) return null

  return (
    <div>
      <h4 className="font-medium mb-2 text-sm">Settlements</h4>
      <div className="space-y-1">
        {settlements.map((s) => (
          <div key={s.id} className="flex justify-between text-sm py-1 border-b last:border-0">
            <span className="capitalize">{s.settlement_type.replace(/_/g, ' ')}</span>
            <span className="font-medium">{formatCurrency(Number(s.amount_cents), currency)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function InvoiceCreditNotesSection({ invoiceId, currency }: { invoiceId: string; currency: string }) {
  const { data: creditNotes = [] } = useQuery({
    queryKey: ['invoice-credit-notes', invoiceId],
    queryFn: () => creditNotesApi.list({ invoice_id: invoiceId }),
  })

  if (creditNotes.length === 0) return null

  const cnStatusVariant: Record<string, 'default' | 'secondary' | 'outline' | 'destructive'> = {
    draft: 'secondary',
    finalized: 'outline',
    voided: 'destructive',
  }

  return (
    <div>
      <h4 className="font-medium mb-2 text-sm">Credit Notes</h4>
      <div className="space-y-1">
        {creditNotes.map((cn) => (
          <div key={cn.id} className="flex items-center justify-between text-sm py-1 border-b last:border-0">
            <div className="flex items-center gap-2">
              <span>{cn.number || cn.id.substring(0, 8)}</span>
              <Badge variant={cnStatusVariant[cn.status] ?? 'outline'} className="text-xs">{cn.status}</Badge>
            </div>
            <span className="font-medium text-red-600">-{formatCurrency(Number(cn.credit_amount_cents), currency)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function InvoiceDetailDialog({
  invoice,
  open,
  onOpenChange,
  onCreateCreditNote,
}: {
  invoice: Invoice | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreateCreditNote?: (invoice: Invoice) => void
}) {
  const canDownloadOrEmail = invoice?.status === 'finalized' || invoice?.status === 'paid'

  const downloadPdfMutation = useMutation({
    mutationFn: (id: string) => invoicesApi.downloadPdf(id),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `invoice-${invoice?.invoice_number ?? invoice?.id}.pdf`
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
    mutationFn: (id: string) => invoicesApi.sendEmail(id),
    onSuccess: () => {
      toast.success('Invoice email sent successfully')
    },
    onError: () => {
      toast.error('Failed to send invoice email')
    },
  })

  if (!invoice) return null

  const walletCredit = Number(invoice.prepaid_credit_amount)
  const couponDiscount = Number(invoice.coupons_amount_cents)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[650px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span>Invoice {invoice.invoice_number}</span>
              <Badge variant="outline" className="capitalize text-xs">{invoice.invoice_type}</Badge>
            </div>
            <StatusBadge status={invoice.status} />
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Header Info */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Customer ID</p>
              <p className="font-medium">{invoice.customer_id}</p>
            </div>
            <div className="text-right">
              <p className="text-muted-foreground">Issue Date</p>
              <p className="font-medium">
                {invoice.issued_at ? format(new Date(invoice.issued_at), 'MMM d, yyyy') : '\u2014'}
              </p>
              <p className="text-muted-foreground mt-2">Due Date</p>
              <p className="font-medium">
                {invoice.due_date ? format(new Date(invoice.due_date), 'MMM d, yyyy') : '\u2014'}
              </p>
            </div>
          </div>

          <Separator />

          {/* Fees Breakdown */}
          <InvoiceFeesBreakdown invoiceId={invoice.id} currency={invoice.currency} />

          <Separator />

          {/* Totals */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Subtotal</span>
              <span>{formatCurrency(invoice.subtotal, invoice.currency)}</span>
            </div>

            {/* Coupon Discounts */}
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
            <AppliedTaxesBreakdown invoiceId={invoice.id} />

            {/* Wallet Credits Applied */}
            {walletCredit > 0 && (
              <div className="flex justify-between text-sm text-blue-600">
                <span>Wallet Credits Applied</span>
                <span>-{formatCurrency(walletCredit, invoice.currency)}</span>
              </div>
            )}

            <Separator />
            <div className="flex justify-between font-medium text-lg">
              <span>Total</span>
              <span>{formatCurrency(invoice.total, invoice.currency)}</span>
            </div>
          </div>

          {/* Settlements */}
          <InvoiceSettlementsSection invoiceId={invoice.id} currency={invoice.currency} />

          {/* Credit Notes */}
          <InvoiceCreditNotesSection invoiceId={invoice.id} currency={invoice.currency} />

          {/* Actions */}
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1"
              disabled={!canDownloadOrEmail || downloadPdfMutation.isPending}
              onClick={() => downloadPdfMutation.mutate(invoice.id)}
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
              className="flex-1"
              disabled={!canDownloadOrEmail || sendEmailMutation.isPending}
              onClick={() => sendEmailMutation.mutate(invoice.id)}
            >
              {sendEmailMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Mail className="mr-2 h-4 w-4" />
              )}
              Send Email
            </Button>
            {invoice.status === 'finalized' && onCreateCreditNote && (
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => onCreateCreditNote(invoice)}
              >
                <FileMinus className="mr-2 h-4 w-4" />
                Create Credit Note
              </Button>
            )}
            {invoice.status === 'draft' && (
              <Button className="flex-1">Finalize Invoice</Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function InvoicePreviewDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [subscriptionId, setSubscriptionId] = useState('')
  const [billingPeriodStart, setBillingPeriodStart] = useState('')
  const [billingPeriodEnd, setBillingPeriodEnd] = useState('')
  const [previewResult, setPreviewResult] = useState<InvoicePreviewResponse | null>(null)

  const { data: subscriptions = [] } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => subscriptionsApi.list(),
    enabled: open,
  })

  const previewMutation = useMutation({
    mutationFn: () =>
      invoicesApi.preview({
        subscription_id: subscriptionId,
        billing_period_start: billingPeriodStart || null,
        billing_period_end: billingPeriodEnd || null,
      }),
    onSuccess: (data) => {
      setPreviewResult(data)
    },
    onError: () => {
      toast.error('Failed to generate invoice preview')
    },
  })

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setSubscriptionId('')
      setBillingPeriodStart('')
      setBillingPeriodEnd('')
      setPreviewResult(null)
    }
    onOpenChange(nextOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[650px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Invoice Preview</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Subscription</Label>
            <Select value={subscriptionId} onValueChange={setSubscriptionId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a subscription" />
              </SelectTrigger>
              <SelectContent>
                {subscriptions.map((sub) => (
                  <SelectItem key={sub.id} value={sub.id}>
                    {sub.external_id} ({sub.status})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Billing Period Start</Label>
              <Input
                type="datetime-local"
                value={billingPeriodStart}
                onChange={(e) => setBillingPeriodStart(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Billing Period End</Label>
              <Input
                type="datetime-local"
                value={billingPeriodEnd}
                onChange={(e) => setBillingPeriodEnd(e.target.value)}
              />
            </div>
          </div>

          <Button
            className="w-full"
            disabled={!subscriptionId || previewMutation.isPending}
            onClick={() => previewMutation.mutate()}
          >
            {previewMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Generate Preview
          </Button>

          {previewResult && (
            <>
              <Separator />
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Invoice Preview</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Fees Table */}
                  {previewResult.fees.length > 0 && (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Description</TableHead>
                          <TableHead className="text-right">Units</TableHead>
                          <TableHead className="text-right">Unit Price</TableHead>
                          <TableHead className="text-right">Amount</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {previewResult.fees.map((fee, idx) => (
                          <TableRow key={idx}>
                            <TableCell>
                              <span className="text-sm">{fee.description}</span>
                              {fee.metric_code && (
                                <span className="ml-2 text-xs text-muted-foreground">({fee.metric_code})</span>
                              )}
                            </TableCell>
                            <TableCell className="text-right">{fee.units}</TableCell>
                            <TableCell className="text-right">
                              {formatCurrency(fee.unit_amount_cents, previewResult.currency)}
                            </TableCell>
                            <TableCell className="text-right font-medium">
                              {formatCurrency(fee.amount_cents, previewResult.currency)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}

                  {/* Totals */}
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Subtotal</span>
                      <span>{formatCurrency(previewResult.subtotal, previewResult.currency)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Tax</span>
                      <span>{formatCurrency(previewResult.tax_amount, previewResult.currency)}</span>
                    </div>
                    {parseFloat(previewResult.coupons_amount) > 0 && (
                      <div className="flex justify-between text-green-600">
                        <span>Coupon Discount</span>
                        <span>-{formatCurrency(previewResult.coupons_amount, previewResult.currency)}</span>
                      </div>
                    )}
                    {parseFloat(previewResult.prepaid_credit_amount) > 0 && (
                      <div className="flex justify-between text-blue-600">
                        <span>Prepaid Credits</span>
                        <span>-{formatCurrency(previewResult.prepaid_credit_amount, previewResult.currency)}</span>
                      </div>
                    )}
                    <Separator />
                    <div className="flex justify-between font-medium text-lg">
                      <span>Total</span>
                      <span>{formatCurrency(previewResult.total, previewResult.currency)}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function InvoicesPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)

  const { data: invoices, isLoading } = useQuery({
    queryKey: ['invoices', { statusFilter }],
    queryFn: () =>
      invoicesApi.list({
        status: statusFilter !== 'all' ? (statusFilter as InvoiceStatus) : undefined,
      }),
  })

  // Client-side search filtering on invoice number
  const data = invoices?.filter(
    (i) => !search || i.invoice_number.toLowerCase().includes(search.toLowerCase())
  )

  // Calculate totals
  const totals = (data ?? []).reduce(
    (acc, inv) => {
      const total = parseFloat(inv.total)
      if (inv.status === 'paid') {
        acc.paid += total
      } else if (inv.status === 'finalized') {
        acc.outstanding += total
      } else if (inv.status === 'draft') {
        acc.draft += total
      }
      return acc
    },
    { paid: 0, outstanding: 0, draft: 0 }
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Invoices</h2>
          <p className="text-muted-foreground">
            View and manage customer invoices
          </p>
        </div>
        <Button onClick={() => setPreviewOpen(true)}>
          <Eye className="mr-2 h-4 w-4" />
          Preview Invoice
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Paid
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-green-600">
              {formatCurrency(totals.paid)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Outstanding
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-orange-600">
              {formatCurrency(totals.outstanding)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Draft
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-muted-foreground">
              {formatCurrency(totals.draft)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search invoices..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="finalized">Finalized</SelectItem>
            <SelectItem value="paid">Paid</SelectItem>
            <SelectItem value="voided">Voided</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Invoice</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Issue Date</TableHead>
              <TableHead>Due Date</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead className="w-[80px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24 ml-auto" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-16" /></TableCell>
                </TableRow>
              ))
            ) : !data || data.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center">
                  <FileText className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No invoices found
                </TableCell>
              </TableRow>
            ) : (
              data.map((invoice) => (
                <TableRow key={invoice.id}>
                  <TableCell>
                    <code className="text-sm font-medium">{invoice.invoice_number}</code>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm capitalize">{invoice.invoice_type}</span>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={invoice.status} />
                  </TableCell>
                  <TableCell>
                    {invoice.issued_at ? format(new Date(invoice.issued_at), 'MMM d, yyyy') : '\u2014'}
                  </TableCell>
                  <TableCell>
                    {invoice.due_date ? format(new Date(invoice.due_date), 'MMM d, yyyy') : '\u2014'}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {formatCurrency(invoice.total, invoice.currency)}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setSelectedInvoice(invoice)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon">
                        <Download className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Invoice Detail Dialog */}
      <InvoiceDetailDialog
        invoice={selectedInvoice}
        open={!!selectedInvoice}
        onOpenChange={(open) => !open && setSelectedInvoice(null)}
        onCreateCreditNote={(invoice) => {
          setSelectedInvoice(null)
          navigate('/admin/credit-notes', {
            state: { invoiceId: invoice.id, customerId: invoice.customer_id },
          })
        }}
      />

      {/* Invoice Preview Dialog */}
      <InvoicePreviewDialog open={previewOpen} onOpenChange={setPreviewOpen} />
    </div>
  )
}
