import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search, Eye, FileText, Loader2, CheckCircle, Plus, Trash2 } from 'lucide-react'
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
import { Checkbox } from '@/components/ui/checkbox'
import { TablePagination } from '@/components/TablePagination'
import { SortableTableHead, useSortState } from '@/components/SortableTableHead'
import { invoicesApi, customersApi, subscriptionsApi } from '@/lib/api'
import { formatCurrency, formatCents } from '@/lib/utils'
import type { Invoice, InvoiceStatus, InvoicePreviewResponse } from '@/types/billing'

const PAGE_SIZE = 20

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

function OneOffInvoiceDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const [customerId, setCustomerId] = useState('')
  const [currency, setCurrency] = useState('USD')
  const [dueDate, setDueDate] = useState('')
  const [lineItems, setLineItems] = useState([
    { description: '', quantity: '1', unit_price: '0', amount: '0' },
  ])

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
    enabled: open,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      invoicesApi.createOneOff({
        customer_id: customerId,
        currency,
        due_date: dueDate || null,
        line_items: lineItems.map((item) => ({
          description: item.description,
          quantity: item.quantity,
          unit_price: item.unit_price,
          amount: item.amount,
        })),
      }),
    onSuccess: () => {
      toast.success('One-off invoice created')
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      handleClose()
    },
    onError: () => {
      toast.error('Failed to create invoice')
    },
  })

  const handleClose = () => {
    setCustomerId('')
    setCurrency('USD')
    setDueDate('')
    setLineItems([{ description: '', quantity: '1', unit_price: '0', amount: '0' }])
    onOpenChange(false)
  }

  const updateLineItem = (index: number, field: string, value: string) => {
    const updated = [...lineItems]
    updated[index] = { ...updated[index], [field]: value }
    // Auto-calculate amount
    const qty = parseFloat(updated[index].quantity) || 0
    const price = parseFloat(updated[index].unit_price) || 0
    updated[index].amount = (qty * price).toFixed(2)
    setLineItems(updated)
  }

  const addLineItem = () => {
    setLineItems([...lineItems, { description: '', quantity: '1', unit_price: '0', amount: '0' }])
  }

  const removeLineItem = (index: number) => {
    if (lineItems.length <= 1) return
    setLineItems(lineItems.filter((_, i) => i !== index))
  }

  const total = lineItems.reduce((sum, item) => sum + (parseFloat(item.amount) || 0), 0)

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen ? handleClose() : onOpenChange(nextOpen)}>
      <DialogContent className="sm:max-w-[650px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create One-Off Invoice</DialogTitle>
          <DialogDescription>Create an invoice with custom line items, not tied to a subscription.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Customer</Label>
              <Select value={customerId} onValueChange={setCustomerId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select customer" />
                </SelectTrigger>
                <SelectContent>
                  {customers.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name || c.external_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Currency</Label>
              <Select value={currency} onValueChange={setCurrency}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="USD">USD</SelectItem>
                  <SelectItem value="EUR">EUR</SelectItem>
                  <SelectItem value="GBP">GBP</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Due Date (optional)</Label>
            <Input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Line Items</Label>
              <Button type="button" variant="outline" size="sm" onClick={addLineItem}>
                <Plus className="mr-1 h-3 w-3" />
                Add Item
              </Button>
            </div>

            {lineItems.map((item, index) => (
              <div key={index} className="grid grid-cols-12 gap-2 items-end">
                <div className="col-span-5 space-y-1">
                  {index === 0 && <Label className="text-xs">Description</Label>}
                  <Input
                    placeholder="Description"
                    value={item.description}
                    onChange={(e) => updateLineItem(index, 'description', e.target.value)}
                  />
                </div>
                <div className="col-span-2 space-y-1">
                  {index === 0 && <Label className="text-xs">Qty</Label>}
                  <Input
                    type="number"
                    min="0"
                    step="1"
                    value={item.quantity}
                    onChange={(e) => updateLineItem(index, 'quantity', e.target.value)}
                  />
                </div>
                <div className="col-span-2 space-y-1">
                  {index === 0 && <Label className="text-xs">Unit Price</Label>}
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={item.unit_price}
                    onChange={(e) => updateLineItem(index, 'unit_price', e.target.value)}
                  />
                </div>
                <div className="col-span-2 space-y-1">
                  {index === 0 && <Label className="text-xs">Amount</Label>}
                  <Input
                    readOnly
                    value={item.amount}
                    className="bg-muted"
                  />
                </div>
                <div className="col-span-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    disabled={lineItems.length <= 1}
                    onClick={() => removeLineItem(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}

            <div className="flex justify-end text-sm font-medium pt-2 border-t">
              <span>Total: {formatCurrency(total, currency)}</span>
            </div>
          </div>

          <Button
            className="w-full"
            disabled={!customerId || lineItems.every((i) => !i.description) || createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create Invoice
          </Button>
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
          <DialogDescription>Preview an invoice for a subscription billing period.</DialogDescription>
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
                              {formatCents(fee.unit_amount_cents, previewResult.currency)}
                            </TableCell>
                            <TableCell className="text-right font-medium">
                              {formatCents(fee.amount_cents, previewResult.currency)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}

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
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>(searchParams.get('status') || 'all')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [oneOffOpen, setOneOffOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const { sort, setSort, orderBy } = useSortState()

  const { data: paginatedData, isLoading } = useQuery({
    queryKey: ['invoices', { statusFilter }, page, pageSize, orderBy],
    queryFn: () =>
      invoicesApi.listPaginated({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        status: statusFilter !== 'all' ? (statusFilter as InvoiceStatus) : undefined,
        order_by: orderBy,
      }),
  })

  const invoices = paginatedData?.data
  const totalCount = paginatedData?.totalCount ?? 0

  const bulkFinalizeMutation = useMutation({
    mutationFn: () =>
      invoicesApi.bulkFinalize({ invoice_ids: Array.from(selectedIds) }),
    onSuccess: (result) => {
      toast.success(`Finalized ${result.finalized_count} invoice(s)${result.failed_count > 0 ? `, ${result.failed_count} failed` : ''}`)
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
    },
    onError: () => {
      toast.error('Failed to bulk finalize invoices')
    },
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

  const draftInvoices = data?.filter((i) => i.status === 'draft') ?? []
  const allDraftsSelected = draftInvoices.length > 0 && draftInvoices.every((i) => selectedIds.has(i.id))

  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    setSelectedIds(next)
  }

  const toggleSelectAllDrafts = () => {
    if (allDraftsSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(draftInvoices.map((i) => i.id)))
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Invoices</h2>
          <p className="text-muted-foreground">
            View and manage customer invoices
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setPreviewOpen(true)}>
            <Eye className="mr-2 h-4 w-4" />
            Preview Invoice
          </Button>
          <Button onClick={() => setOneOffOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create One-Off Invoice
          </Button>
        </div>
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

      {/* Filters & Bulk Actions */}
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
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1) }}>
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
        {selectedIds.size > 0 && (
          <Button
            disabled={bulkFinalizeMutation.isPending}
            onClick={() => bulkFinalizeMutation.mutate()}
          >
            {bulkFinalizeMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle className="mr-2 h-4 w-4" />
            )}
            Finalize {selectedIds.size} Selected
          </Button>
        )}
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40px]">
                {draftInvoices.length > 0 && (
                  <Checkbox
                    checked={allDraftsSelected}
                    onCheckedChange={toggleSelectAllDrafts}
                    aria-label="Select all draft invoices"
                  />
                )}
              </TableHead>
              <SortableTableHead label="Invoice #" sortKey="invoice_number" sort={sort} onSort={setSort} />
              <SortableTableHead label="Type" sortKey="invoice_type" sort={sort} onSort={setSort} />
              <SortableTableHead label="Status" sortKey="status" sort={sort} onSort={setSort} />
              <SortableTableHead label="Issue Date" sortKey="issuing_date" sort={sort} onSort={setSort} />
              <SortableTableHead label="Due Date" sortKey="payment_due_date" sort={sort} onSort={setSort} />
              <SortableTableHead label="Amount" sortKey="total_amount_cents" sort={sort} onSort={setSort} className="text-right" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-4" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24 ml-auto" /></TableCell>
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
                <TableRow
                  key={invoice.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => navigate(`/admin/invoices/${invoice.id}`)}
                >
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    {invoice.status === 'draft' && (
                      <Checkbox
                        checked={selectedIds.has(invoice.id)}
                        onCheckedChange={() => toggleSelect(invoice.id)}
                        aria-label={`Select invoice ${invoice.invoice_number}`}
                      />
                    )}
                  </TableCell>
                  <TableCell>
                    <code className="text-sm font-medium">{invoice.invoice_number}</code>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm capitalize">{invoice.invoice_type.replace(/_/g, ' ')}</span>
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
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <TablePagination
          page={page}
          pageSize={pageSize}
          totalCount={totalCount}
          onPageChange={setPage}
          onPageSizeChange={(size) => { setPageSize(size); setPage(1) }}
        />
      </div>

      {/* Invoice Preview Dialog */}
      <InvoicePreviewDialog open={previewOpen} onOpenChange={setPreviewOpen} />

      {/* Create One-Off Invoice Dialog */}
      <OneOffInvoiceDialog open={oneOffOpen} onOpenChange={setOneOffOpen} />
    </div>
  )
}
