import { useState, useEffect } from 'react'
import { useNavigate, useParams, useLocation, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2 } from 'lucide-react'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { creditNotesApi, customersApi, invoicesApi, feesApi, ApiError } from '@/lib/api'
import type {
  CreditNoteCreate,
  CreditNoteUpdate,
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

interface FormState {
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
}

const defaultFormState: FormState = {
  number: '',
  invoice_id: '',
  customer_id: '',
  credit_note_type: 'credit',
  reason: 'other',
  description: '',
  credit_amount_cents: '0',
  refund_amount_cents: '0',
  total_amount_cents: '0',
  taxes_amount_cents: '0',
  currency: 'USD',
}

export default function CreditNoteFormPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const isEdit = !!id

  const locationState = location.state as { invoiceId?: string; customerId?: string } | null

  const [form, setForm] = useState<FormState>(() => ({
    ...defaultFormState,
    invoice_id: locationState?.invoiceId ?? '',
    customer_id: locationState?.customerId ?? '',
  }))
  const [selectedFees, setSelectedFees] = useState<CreditNoteItemCreate[]>([])
  const [initialized, setInitialized] = useState(false)

  // Clear navigation state so it doesn't re-trigger on back navigation
  useEffect(() => {
    if (locationState?.invoiceId) {
      window.history.replaceState({}, '')
    }
  }, [locationState?.invoiceId])

  // Fetch existing credit note for edit mode
  const { data: creditNote, isLoading: loadingCreditNote } = useQuery({
    queryKey: ['credit-note', id],
    queryFn: () => creditNotesApi.get(id!),
    enabled: isEdit,
  })

  // Populate form from existing credit note
  useEffect(() => {
    if (creditNote && !initialized) {
      setForm({
        number: creditNote.number,
        invoice_id: creditNote.invoice_id,
        customer_id: creditNote.customer_id,
        credit_note_type: creditNote.credit_note_type as 'credit' | 'refund' | 'offset',
        reason: creditNote.reason,
        description: creditNote.description ?? '',
        credit_amount_cents: String(creditNote.credit_amount_cents),
        refund_amount_cents: String(creditNote.refund_amount_cents),
        total_amount_cents: String(creditNote.total_amount_cents),
        taxes_amount_cents: String(creditNote.taxes_amount_cents),
        currency: creditNote.currency,
      })
      setInitialized(true)
    }
  }, [creditNote, initialized])

  // Fetch customers
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  // Fetch invoices for the selected customer
  const { data: invoices = [] } = useQuery({
    queryKey: ['invoices-for-cn', form.customer_id],
    queryFn: () => invoicesApi.list({ customer_id: form.customer_id, status: 'finalized' as never }),
    enabled: !!form.customer_id,
  })

  // Fetch fees for selected invoice
  const { data: fees = [] } = useQuery({
    queryKey: ['fees-for-cn', form.invoice_id],
    queryFn: () => feesApi.list({ invoice_id: form.invoice_id }),
    enabled: !!form.invoice_id,
  })

  // Get the selected invoice for display
  const selectedInvoice = invoices.find((inv: Invoice) => inv.id === form.invoice_id)
  const selectedCustomer = customers.find((c: Customer) => c.id === form.customer_id)

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

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: CreditNoteCreate) => creditNotesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credit-notes'] })
      toast.success('Credit note created successfully')
      navigate('/admin/credit-notes')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create credit note'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ cnId, data }: { cnId: string; data: CreditNoteUpdate }) =>
      creditNotesApi.update(cnId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credit-notes'] })
      queryClient.invalidateQueries({ queryKey: ['credit-note', id] })
      toast.success('Credit note updated successfully')
      navigate('/admin/credit-notes')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update credit note'
      toast.error(message)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (isEdit) {
      updateMutation.mutate({
        cnId: id!,
        data: {
          description: form.description || null,
          credit_amount_cents: form.credit_amount_cents,
          refund_amount_cents: form.refund_amount_cents,
          total_amount_cents: form.total_amount_cents,
          taxes_amount_cents: form.taxes_amount_cents,
          reason: form.reason as CreditNoteUpdate['reason'],
        },
      })
    } else {
      const data: CreditNoteCreate = {
        number: form.number,
        invoice_id: form.invoice_id,
        customer_id: form.customer_id,
        credit_note_type: form.credit_note_type,
        reason: form.reason as CreditNoteCreate['reason'],
        currency: form.currency,
        credit_amount_cents: form.credit_amount_cents,
        refund_amount_cents: form.refund_amount_cents,
        total_amount_cents: form.total_amount_cents,
        taxes_amount_cents: form.taxes_amount_cents,
        items: selectedFees,
      }
      if (form.description) data.description = form.description
      createMutation.mutate(data)
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  if (isEdit && loadingCreditNote) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[600px] w-full" />
      </div>
    )
  }

  if (isEdit && creditNote && creditNote.status !== 'draft') {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold mb-2">Cannot edit this credit note</h2>
        <p className="text-muted-foreground mb-4">Only draft credit notes can be edited.</p>
        <Button variant="outline" onClick={() => navigate('/admin/credit-notes')}>
          Back to Credit Notes
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumbs */}
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/admin/credit-notes">Credit Notes</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>
              {isEdit ? `Edit ${creditNote?.number ?? ''}` : 'New Credit Note'}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/admin/credit-notes')}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {isEdit ? 'Edit Credit Note' : 'Create Credit Note'}
          </h1>
          <p className="text-muted-foreground">
            {isEdit
              ? 'Update the amounts, reason, or description for this draft credit note.'
              : 'Create a credit note for a customer invoice. Select a customer, then an invoice, then configure the credit.'}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Step 1: Customer & Invoice Selection */}
          <Card>
            <CardHeader>
              <CardTitle>Customer & Invoice</CardTitle>
              <CardDescription>
                {isEdit
                  ? 'The customer and invoice are fixed for this credit note.'
                  : 'Select the customer and the finalized invoice to credit.'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="cn_customer">Customer *</Label>
                {isEdit ? (
                  <p className="text-sm font-medium py-2">
                    {selectedCustomer?.name ?? form.customer_id}
                  </p>
                ) : (
                  <Select
                    value={form.customer_id}
                    onValueChange={(value) =>
                      setForm({ ...form, customer_id: value, invoice_id: '' })
                    }
                  >
                    <SelectTrigger id="cn_customer">
                      <SelectValue placeholder="Select a customer" />
                    </SelectTrigger>
                    <SelectContent>
                      {customers.map((c: Customer) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="cn_invoice">Invoice *</Label>
                {isEdit ? (
                  <p className="text-sm font-medium font-mono py-2">
                    {selectedInvoice?.invoice_number ?? form.invoice_id.slice(0, 8) + '...'}
                  </p>
                ) : (
                  <Select
                    value={form.invoice_id}
                    onValueChange={(value) => {
                      const inv = invoices.find((i: Invoice) => i.id === value)
                      setForm({
                        ...form,
                        invoice_id: value,
                        currency: inv?.currency ?? form.currency,
                      })
                      setSelectedFees([])
                    }}
                    disabled={!form.customer_id}
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
                )}
              </div>

              {!isEdit && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="cn_number">Number *</Label>
                    <Input
                      id="cn_number"
                      value={form.number}
                      onChange={(e) => setForm({ ...form, number: e.target.value })}
                      placeholder="e.g. CN-2024-001"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="cn_currency">Currency</Label>
                    <Input
                      id="cn_currency"
                      value={form.currency}
                      onChange={(e) => setForm({ ...form, currency: e.target.value })}
                      placeholder="USD"
                      maxLength={3}
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Step 2: Type & Reason */}
          <Card>
            <CardHeader>
              <CardTitle>Type & Reason</CardTitle>
              <CardDescription>Classify the credit note and provide a reason.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="cn_type">Type *</Label>
                {isEdit ? (
                  <p className="text-sm font-medium py-2 capitalize">{form.credit_note_type}</p>
                ) : (
                  <Select
                    value={form.credit_note_type}
                    onValueChange={(value: 'credit' | 'refund' | 'offset') =>
                      setForm({ ...form, credit_note_type: value })
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
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="cn_reason">Reason *</Label>
                <Select
                  value={form.reason}
                  onValueChange={(value) => setForm({ ...form, reason: value })}
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

              <div className="space-y-2">
                <Label htmlFor="cn_description">Description</Label>
                <Textarea
                  id="cn_description"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Optional description of the credit note"
                  rows={3}
                />
              </div>
            </CardContent>
          </Card>

          {/* Step 3: Amounts */}
          <Card>
            <CardHeader>
              <CardTitle>Amounts</CardTitle>
              <CardDescription>Specify the credit, refund, tax, and total amounts in cents.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="cn_credit_amount">Credit Amount (cents)</Label>
                  <Input
                    id="cn_credit_amount"
                    type="number"
                    min="0"
                    value={form.credit_amount_cents}
                    onChange={(e) => setForm({ ...form, credit_amount_cents: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    {formatCurrency(form.credit_amount_cents || '0', form.currency || 'USD')}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cn_refund_amount">Refund Amount (cents)</Label>
                  <Input
                    id="cn_refund_amount"
                    type="number"
                    min="0"
                    value={form.refund_amount_cents}
                    onChange={(e) => setForm({ ...form, refund_amount_cents: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    {formatCurrency(form.refund_amount_cents || '0', form.currency || 'USD')}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="cn_total_amount">Total Amount (cents) *</Label>
                  <Input
                    id="cn_total_amount"
                    type="number"
                    min="0"
                    value={form.total_amount_cents}
                    onChange={(e) => setForm({ ...form, total_amount_cents: e.target.value })}
                    required
                  />
                  <p className="text-xs text-muted-foreground">
                    {formatCurrency(form.total_amount_cents || '0', form.currency || 'USD')}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cn_taxes_amount">Taxes Amount (cents)</Label>
                  <Input
                    id="cn_taxes_amount"
                    type="number"
                    min="0"
                    value={form.taxes_amount_cents}
                    onChange={(e) => setForm({ ...form, taxes_amount_cents: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    {formatCurrency(form.taxes_amount_cents || '0', form.currency || 'USD')}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Step 4: Fee Selection (create mode only, when invoice is selected) */}
          {!isEdit && fees.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Fee Selection</CardTitle>
                <CardDescription>
                  Optionally select specific fees from the invoice to credit. Set a custom credit amount for each fee.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[40px]"></TableHead>
                        <TableHead>Fee</TableHead>
                        <TableHead className="text-right">Original Amount</TableHead>
                        <TableHead className="text-right">Credit Amount</TableHead>
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
                            <TableCell className="text-right text-sm">
                              {formatCurrency(fee.amount_cents, form.currency || 'USD')}
                            </TableCell>
                            <TableCell className="text-right">
                              {selected ? (
                                <Input
                                  type="number"
                                  min="1"
                                  value={String(selected.amount_cents)}
                                  onChange={(e) => updateFeeAmount(fee.id, e.target.value)}
                                  className="h-7 w-28 ml-auto"
                                />
                              ) : (
                                <span className="text-muted-foreground text-sm">—</span>
                              )}
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>
                {selectedFees.length > 0 && (
                  <p className="text-sm text-muted-foreground mt-2">
                    {selectedFees.length} fee{selectedFees.length > 1 ? 's' : ''} selected
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-4 mt-6">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate('/admin/credit-notes')}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={
              isPending ||
              (!isEdit && (!form.number || !form.customer_id || !form.invoice_id))
            }
          >
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isPending
              ? (isEdit ? 'Saving...' : 'Creating...')
              : (isEdit ? 'Save Changes' : 'Create Credit Note')}
          </Button>
        </div>
      </form>
    </div>
  )
}
