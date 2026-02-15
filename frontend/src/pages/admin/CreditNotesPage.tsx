import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Search,
  MoreHorizontal,
  Eye,
  CheckCircle,
  XCircle,
  FileText,
  Download,
  Mail,
  Loader2,
} from 'lucide-react'
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { creditNotesApi, customersApi, invoicesApi, feesApi, ApiError } from '@/lib/api'
import type {
  CreditNote,
  CreditNoteCreate,
  CreditNoteItemCreate,
  Customer,
  Invoice,
  Fee,
} from '@/types/billing'

function formatCurrency(cents: number | string, currency: string = 'USD'): string {
  const num = typeof cents === 'string' ? parseFloat(cents) : cents
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(num / 100)
}

const REASON_LABELS: Record<string, string> = {
  duplicated_charge: 'Duplicated Charge',
  product_unsatisfactory: 'Product Unsatisfactory',
  order_change: 'Order Change',
  order_cancellation: 'Order Cancellation',
  fraudulent_charge: 'Fraudulent Charge',
  other: 'Other',
}

const TYPE_LABELS: Record<string, string> = {
  credit: 'Credit',
  refund: 'Refund',
  offset: 'Offset',
}

function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; className?: string }> = {
    draft: { variant: 'secondary' },
    finalized: { variant: 'default', className: 'bg-green-600' },
  }
  const config = variants[status]
  if (!config) return <Badge variant="outline">{status}</Badge>
  return (
    <Badge variant={config.variant} className={config.className}>
      {status}
    </Badge>
  )
}

function CreditStatusBadge({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="text-muted-foreground">—</span>
  const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; className?: string }> = {
    available: { variant: 'outline', className: 'border-green-500 text-green-600' },
    consumed: { variant: 'secondary' },
    voided: { variant: 'destructive' },
  }
  const config = variants[status]
  if (!config) return <Badge variant="outline">{status}</Badge>
  return (
    <Badge variant={config.variant} className={config.className}>
      {status}
    </Badge>
  )
}

// --- Create Credit Note Dialog ---
function CreateCreditNoteDialog({
  open,
  onOpenChange,
  customers,
  onSubmit,
  isLoading,
  preselectedInvoiceId,
  preselectedCustomerId,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  customers: Customer[]
  onSubmit: (data: CreditNoteCreate) => void
  isLoading: boolean
  preselectedInvoiceId?: string
  preselectedCustomerId?: string
}) {
  const [formData, setFormData] = useState<{
    number: string
    invoice_id: string
    customer_id: string
    credit_note_type: 'credit' | 'refund' | 'offset'
    reason: string
    description: string
    credit_amount_cents: string
    refund_amount_cents: string
    total_amount_cents: string
    taxes_amount_cents: string
    currency: string
  }>({
    number: '',
    invoice_id: preselectedInvoiceId ?? '',
    customer_id: preselectedCustomerId ?? '',
    credit_note_type: 'credit',
    reason: 'other',
    description: '',
    credit_amount_cents: '0',
    refund_amount_cents: '0',
    total_amount_cents: '0',
    taxes_amount_cents: '0',
    currency: 'USD',
  })

  const [selectedFees, setSelectedFees] = useState<CreditNoteItemCreate[]>([])

  // Fetch invoices for the selected customer
  const { data: invoices = [] } = useQuery({
    queryKey: ['invoices-for-cn', formData.customer_id],
    queryFn: () => invoicesApi.list({ customer_id: formData.customer_id, status: 'finalized' as never }),
    enabled: !!formData.customer_id,
  })

  // Fetch fees for selected invoice
  const { data: fees = [] } = useQuery({
    queryKey: ['fees-for-cn', formData.invoice_id],
    queryFn: () => feesApi.list({ invoice_id: formData.invoice_id }),
    enabled: !!formData.invoice_id,
  })

  const toggleFee = (fee: Fee) => {
    setSelectedFees((prev) => {
      const exists = prev.find((f) => f.fee_id === fee.id)
      if (exists) {
        return prev.filter((f) => f.fee_id !== fee.id)
      }
      return [...prev, { fee_id: fee.id, amount_cents: fee.amount_cents }]
    })
  }

  const updateFeeAmount = (feeId: string, amount: string) => {
    setSelectedFees((prev) =>
      prev.map((f) => (f.fee_id === feeId ? { ...f, amount_cents: amount } : f))
    )
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const data: CreditNoteCreate = {
      number: formData.number,
      invoice_id: formData.invoice_id,
      customer_id: formData.customer_id,
      credit_note_type: formData.credit_note_type,
      reason: formData.reason as CreditNoteCreate['reason'],
      currency: formData.currency,
      credit_amount_cents: formData.credit_amount_cents,
      refund_amount_cents: formData.refund_amount_cents,
      total_amount_cents: formData.total_amount_cents,
      taxes_amount_cents: formData.taxes_amount_cents,
      items: selectedFees,
    }
    if (formData.description) data.description = formData.description
    onSubmit(data)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create Credit Note</DialogTitle>
            <DialogDescription>
              Create a credit note for an invoice
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="cn_number">Number *</Label>
                <Input
                  id="cn_number"
                  value={formData.number}
                  onChange={(e) =>
                    setFormData({ ...formData, number: e.target.value })
                  }
                  placeholder="e.g. CN-2024-001"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cn_currency">Currency</Label>
                <Input
                  id="cn_currency"
                  value={formData.currency}
                  onChange={(e) =>
                    setFormData({ ...formData, currency: e.target.value })
                  }
                  placeholder="USD"
                  maxLength={3}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="cn_customer">Customer *</Label>
                <Select
                  value={formData.customer_id}
                  onValueChange={(value) =>
                    setFormData({ ...formData, customer_id: value, invoice_id: '' })
                  }
                >
                  <SelectTrigger id="cn_customer">
                    <SelectValue placeholder="Select a customer" />
                  </SelectTrigger>
                  <SelectContent>
                    {customers.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="cn_invoice">Invoice *</Label>
                <Select
                  value={formData.invoice_id}
                  onValueChange={(value) =>
                    setFormData({ ...formData, invoice_id: value })
                  }
                  disabled={!formData.customer_id}
                >
                  <SelectTrigger id="cn_invoice">
                    <SelectValue placeholder="Select an invoice" />
                  </SelectTrigger>
                  <SelectContent>
                    {invoices.map((inv: Invoice) => (
                      <SelectItem key={inv.id} value={inv.id}>
                        {inv.invoice_number} — {formatCurrency(inv.total, inv.currency)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="cn_type">Type *</Label>
                <Select
                  value={formData.credit_note_type}
                  onValueChange={(value: 'credit' | 'refund' | 'offset') =>
                    setFormData({ ...formData, credit_note_type: value })
                  }
                >
                  <SelectTrigger id="cn_type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="credit">Credit</SelectItem>
                    <SelectItem value="refund">Refund</SelectItem>
                    <SelectItem value="offset">Offset</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="cn_reason">Reason *</Label>
                <Select
                  value={formData.reason}
                  onValueChange={(value) =>
                    setFormData({ ...formData, reason: value })
                  }
                >
                  <SelectTrigger id="cn_reason">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(REASON_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="cn_description">Description</Label>
              <Textarea
                id="cn_description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Optional description of the credit note"
                rows={2}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="cn_credit_amount">Credit Amount (cents)</Label>
                <Input
                  id="cn_credit_amount"
                  type="number"
                  min="0"
                  value={formData.credit_amount_cents}
                  onChange={(e) =>
                    setFormData({ ...formData, credit_amount_cents: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cn_refund_amount">Refund Amount (cents)</Label>
                <Input
                  id="cn_refund_amount"
                  type="number"
                  min="0"
                  value={formData.refund_amount_cents}
                  onChange={(e) =>
                    setFormData({ ...formData, refund_amount_cents: e.target.value })
                  }
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="cn_total_amount">Total Amount (cents) *</Label>
                <Input
                  id="cn_total_amount"
                  type="number"
                  min="0"
                  value={formData.total_amount_cents}
                  onChange={(e) =>
                    setFormData({ ...formData, total_amount_cents: e.target.value })
                  }
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cn_taxes_amount">Taxes Amount (cents)</Label>
                <Input
                  id="cn_taxes_amount"
                  type="number"
                  min="0"
                  value={formData.taxes_amount_cents}
                  onChange={(e) =>
                    setFormData({ ...formData, taxes_amount_cents: e.target.value })
                  }
                />
              </div>
            </div>

            {/* Fee selection for credit note items */}
            {fees.length > 0 && (
              <div className="space-y-2">
                <Label>Select Fees to Credit</Label>
                <div className="rounded-md border max-h-40 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[40px]"></TableHead>
                        <TableHead>Fee</TableHead>
                        <TableHead>Amount</TableHead>
                        <TableHead>Credit Amount</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {fees.map((fee: Fee) => {
                        const selected = selectedFees.find((f) => f.fee_id === fee.id)
                        return (
                          <TableRow key={fee.id}>
                            <TableCell>
                              <input
                                type="checkbox"
                                checked={!!selected}
                                onChange={() => toggleFee(fee)}
                                className="h-4 w-4 rounded border-input"
                              />
                            </TableCell>
                            <TableCell className="text-sm">
                              {fee.fee_type} — {fee.description || fee.id.slice(0, 8)}
                            </TableCell>
                            <TableCell className="text-sm">
                              {formatCurrency(fee.amount_cents)}
                            </TableCell>
                            <TableCell>
                              {selected && (
                                <Input
                                  type="number"
                                  min="1"
                                  value={String(selected.amount_cents)}
                                  onChange={(e) => updateFeeAmount(fee.id, e.target.value)}
                                  className="h-7 w-24"
                                />
                              )}
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={
                isLoading ||
                !formData.number ||
                !formData.customer_id ||
                !formData.invoice_id
              }
            >
              {isLoading ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- Credit Note Detail Dialog ---
function CreditNoteDetailDialog({
  creditNote,
  open,
  onOpenChange,
  customers,
}: {
  creditNote: CreditNote | null
  open: boolean
  onOpenChange: (open: boolean) => void
  customers: Customer[]
}) {
  const canDownloadOrEmail = creditNote?.status === 'finalized'

  const downloadPdfMutation = useMutation({
    mutationFn: (id: string) => creditNotesApi.downloadPdf(id),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `credit-note-${creditNote?.number ?? creditNote?.id}.pdf`
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
    mutationFn: (id: string) => creditNotesApi.sendEmail(id),
    onSuccess: () => {
      toast.success('Credit note email sent successfully')
    },
    onError: () => {
      toast.error('Failed to send credit note email')
    },
  })

  if (!creditNote) return null

  const customer = customers.find((c) => c.id === creditNote.customer_id)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <span>Credit Note {creditNote.number}</span>
            <StatusBadge status={creditNote.status} />
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Header Info */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Customer</p>
              <p className="font-medium">{customer?.name ?? creditNote.customer_id}</p>
            </div>
            <div className="text-right">
              <p className="text-muted-foreground">Invoice ID</p>
              <p className="font-medium font-mono text-xs">{creditNote.invoice_id.slice(0, 8)}...</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Type</p>
              <Badge variant="outline">
                {TYPE_LABELS[creditNote.credit_note_type] ?? creditNote.credit_note_type}
              </Badge>
            </div>
            <div>
              <p className="text-muted-foreground">Reason</p>
              <p className="font-medium">
                {REASON_LABELS[creditNote.reason] ?? creditNote.reason}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Currency</p>
              <p className="font-medium">{creditNote.currency}</p>
            </div>
          </div>

          {creditNote.description && (
            <div className="text-sm">
              <p className="text-muted-foreground">Description</p>
              <p>{creditNote.description}</p>
            </div>
          )}

          <Separator />

          {/* Amounts breakdown */}
          <div className="space-y-2">
            <h4 className="font-medium text-sm">Amounts</h4>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Credit Amount</span>
              <span>{formatCurrency(creditNote.credit_amount_cents, creditNote.currency)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Refund Amount</span>
              <span>{formatCurrency(creditNote.refund_amount_cents, creditNote.currency)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Taxes</span>
              <span>{formatCurrency(creditNote.taxes_amount_cents, creditNote.currency)}</span>
            </div>
            <Separator />
            <div className="flex justify-between font-medium">
              <span>Total</span>
              <span>{formatCurrency(creditNote.total_amount_cents, creditNote.currency)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Balance Remaining</span>
              <span className="font-medium text-blue-600">
                {formatCurrency(creditNote.balance_amount_cents, creditNote.currency)}
              </span>
            </div>
          </div>

          <Separator />

          {/* Status details */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Credit Status</p>
              <CreditStatusBadge status={creditNote.credit_status} />
            </div>
            <div>
              <p className="text-muted-foreground">Refund Status</p>
              {creditNote.refund_status ? (
                <Badge variant="outline">{creditNote.refund_status}</Badge>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Issued At</p>
              <p className="font-medium">
                {creditNote.issued_at
                  ? format(new Date(creditNote.issued_at), 'MMM d, yyyy HH:mm')
                  : '—'}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Voided At</p>
              <p className="font-medium">
                {creditNote.voided_at
                  ? format(new Date(creditNote.voided_at), 'MMM d, yyyy HH:mm')
                  : '—'}
              </p>
            </div>
          </div>

          <div className="text-sm text-muted-foreground">
            Created {format(new Date(creditNote.created_at), 'MMM d, yyyy HH:mm')}
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1"
              disabled={!canDownloadOrEmail || downloadPdfMutation.isPending}
              onClick={() => downloadPdfMutation.mutate(creditNote.id)}
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
              onClick={() => sendEmailMutation.mutate(creditNote.id)}
            >
              {sendEmailMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Mail className="mr-2 h-4 w-4" />
              )}
              Send Email
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function CreditNotesPage() {
  const queryClient = useQueryClient()
  const location = useLocation()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)
  const [detailCreditNote, setDetailCreditNote] = useState<CreditNote | null>(null)
  const [finalizeCreditNote, setFinalizeCreditNote] = useState<CreditNote | null>(null)
  const [voidCreditNote, setVoidCreditNote] = useState<CreditNote | null>(null)

  // Read navigation state from InvoicesPage to pre-select invoice/customer
  const locationState = location.state as { invoiceId?: string; customerId?: string } | null
  const [preselectedInvoiceId, setPreselectedInvoiceId] = useState<string | undefined>(undefined)
  const [preselectedCustomerId, setPreselectedCustomerId] = useState<string | undefined>(undefined)

  useEffect(() => {
    if (locationState?.invoiceId) {
      setPreselectedInvoiceId(locationState.invoiceId)
      setPreselectedCustomerId(locationState.customerId)
      setFormOpen(true)
      // Clear the navigation state so it doesn't re-trigger
      window.history.replaceState({}, '')
    }
  }, [locationState?.invoiceId, locationState?.customerId])

  // Fetch credit notes
  const {
    data: creditNotes = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['credit-notes'],
    queryFn: () => creditNotesApi.list(),
  })

  // Fetch customers for display and create dialog
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  // Filter credit notes
  const filteredCreditNotes = creditNotes.filter((cn) => {
    const customer = customers.find((c) => c.id === cn.customer_id)
    const matchesSearch =
      !search ||
      cn.number.toLowerCase().includes(search.toLowerCase()) ||
      (customer?.name ?? '').toLowerCase().includes(search.toLowerCase())
    const matchesStatus =
      statusFilter === 'all' || cn.status === statusFilter
    return matchesSearch && matchesStatus
  })

  // Stats
  const stats = {
    total: creditNotes.length,
    draft: creditNotes.filter((cn) => cn.status === 'draft').length,
    finalized: creditNotes.filter((cn) => cn.status === 'finalized').length,
    totalAmount: creditNotes.reduce(
      (acc, cn) => acc + parseFloat(cn.total_amount_cents),
      0
    ),
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: CreditNoteCreate) => creditNotesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credit-notes'] })
      setFormOpen(false)
      toast.success('Credit note created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to create credit note'
      toast.error(message)
    },
  })

  // Finalize mutation
  const finalizeMutation = useMutation({
    mutationFn: (id: string) => creditNotesApi.finalize(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credit-notes'] })
      setFinalizeCreditNote(null)
      toast.success('Credit note finalized successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to finalize credit note'
      toast.error(message)
    },
  })

  // Void mutation
  const voidMutation = useMutation({
    mutationFn: (id: string) => creditNotesApi.void(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credit-notes'] })
      setVoidCreditNote(null)
      toast.success('Credit note voided successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to void credit note'
      toast.error(message)
    },
  })

  const getCustomerName = (customerId: string) => {
    const customer = customers.find((c) => c.id === customerId)
    return customer?.name ?? customerId.slice(0, 8) + '...'
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load credit notes. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Credit Notes</h2>
          <p className="text-muted-foreground">
            Manage credit notes for customer invoices
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Credit Note
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Credit Notes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Draft
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-muted-foreground">
              {stats.draft}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Finalized
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats.finalized}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Amount
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {formatCurrency(stats.totalAmount)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by number or customer..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="finalized">Finalized</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Number</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Credit Status</TableHead>
              <TableHead className="text-right">Total</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : filteredCreditNotes.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={8}
                  className="h-24 text-center text-muted-foreground"
                >
                  <FileText className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No credit notes found
                </TableCell>
              </TableRow>
            ) : (
              filteredCreditNotes.map((cn) => (
                <TableRow key={cn.id}>
                  <TableCell>
                    <code className="text-sm bg-muted px-1.5 py-0.5 rounded font-medium">
                      {cn.number}
                    </code>
                  </TableCell>
                  <TableCell className="font-medium">
                    {getCustomerName(cn.customer_id)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {TYPE_LABELS[cn.credit_note_type] ?? cn.credit_note_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm">
                    {REASON_LABELS[cn.reason] ?? cn.reason}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={cn.status} />
                  </TableCell>
                  <TableCell>
                    <CreditStatusBadge status={cn.credit_status} />
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {formatCurrency(cn.total_amount_cents, cn.currency)}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => setDetailCreditNote(cn)}
                        >
                          <Eye className="mr-2 h-4 w-4" />
                          View Details
                        </DropdownMenuItem>
                        {cn.status === 'draft' && (
                          <DropdownMenuItem
                            onClick={() => setFinalizeCreditNote(cn)}
                          >
                            <CheckCircle className="mr-2 h-4 w-4" />
                            Finalize
                          </DropdownMenuItem>
                        )}
                        {cn.status === 'finalized' && cn.credit_status !== 'voided' && (
                          <DropdownMenuItem
                            onClick={() => setVoidCreditNote(cn)}
                            className="text-destructive"
                          >
                            <XCircle className="mr-2 h-4 w-4" />
                            Void
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Create Dialog */}
      <CreateCreditNoteDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open)
          if (!open) {
            setPreselectedInvoiceId(undefined)
            setPreselectedCustomerId(undefined)
          }
        }}
        customers={customers}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
        preselectedInvoiceId={preselectedInvoiceId}
        preselectedCustomerId={preselectedCustomerId}
      />

      {/* Detail Dialog */}
      <CreditNoteDetailDialog
        creditNote={detailCreditNote}
        open={!!detailCreditNote}
        onOpenChange={(open) => !open && setDetailCreditNote(null)}
        customers={customers}
      />

      {/* Finalize Confirmation */}
      <AlertDialog
        open={!!finalizeCreditNote}
        onOpenChange={(open) => !open && setFinalizeCreditNote(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Finalize Credit Note</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to finalize credit note "{finalizeCreditNote?.number}"?
              Once finalized, the credit will become available and the note cannot be edited.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                finalizeCreditNote &&
                finalizeMutation.mutate(finalizeCreditNote.id)
              }
            >
              {finalizeMutation.isPending ? 'Finalizing...' : 'Finalize'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Void Confirmation */}
      <AlertDialog
        open={!!voidCreditNote}
        onOpenChange={(open) => !open && setVoidCreditNote(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Void Credit Note</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to void credit note "{voidCreditNote?.number}"?
              This will set the balance to zero and the credit will no longer be available.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                voidCreditNote && voidMutation.mutate(voidCreditNote.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {voidMutation.isPending ? 'Voiding...' : 'Void'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
