import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, CreditCard, Check, Trash2, RefreshCw, ExternalLink, MoreHorizontal, Eye, RotateCcw, Send, Plus, Loader2 } from 'lucide-react'
import { format } from 'date-fns'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
  DialogFooter,
  DialogDescription,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
import { TablePagination } from '@/components/TablePagination'
import { SortableTableHead, useSortState } from '@/components/SortableTableHead'
import PageHeader from '@/components/PageHeader'
import { paymentsApi, customersApi, invoicesApi } from '@/lib/api'
import { formatCurrency } from '@/lib/utils'
import type { components } from '@/lib/schema'

type PaymentResponse = components['schemas']['PaymentResponse']
type PaymentStatus = components['schemas']['PaymentStatus']
type PaymentProvider = components['schemas']['PaymentProvider']

const statusColors: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  pending: 'secondary',
  processing: 'secondary',
  succeeded: 'default',
  failed: 'destructive',
  refunded: 'outline',
  canceled: 'outline',
}

const PAGE_SIZE = 20

const providerLabels: Record<string, string> = {
  stripe: 'Stripe',
  ucp: 'UCP',
  manual: 'Manual',
}

export default function PaymentsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<PaymentStatus | 'all'>('all')
  const [providerFilter, setProviderFilter] = useState<PaymentProvider | 'all'>('all')
  const [selectedPayment, setSelectedPayment] = useState<PaymentResponse | null>(null)
  const [confirmAction, setConfirmAction] = useState<{ type: 'refund' | 'markPaid' | 'delete' | 'retry'; payment: PaymentResponse } | null>(null)
  const [refundAmount, setRefundAmount] = useState<string>('')
  const [refundType, setRefundType] = useState<'full' | 'partial'>('full')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const { sort, setSort, orderBy } = useSortState()
  const [showRecordDialog, setShowRecordDialog] = useState(false)
  const [recordInvoiceId, setRecordInvoiceId] = useState('')
  const [recordAmount, setRecordAmount] = useState('')
  const [recordCurrency, setRecordCurrency] = useState('USD')
  const [recordReference, setRecordReference] = useState('')
  const [recordNotes, setRecordNotes] = useState('')

  // Fetch payments
  const { data: paginatedData, isLoading } = useQuery({
    queryKey: ['payments', statusFilter, providerFilter, page, pageSize, orderBy],
    queryFn: () => paymentsApi.listPaginated({
      skip: (page - 1) * pageSize,
      limit: pageSize,
      status: statusFilter === 'all' ? undefined : statusFilter,
      provider: providerFilter === 'all' ? undefined : providerFilter,
      order_by: orderBy,
    }),
  })

  const payments = paginatedData?.data ?? []
  const totalCount = paginatedData?.totalCount ?? 0

  // Fetch customers for display
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  // Fetch invoices for display
  const { data: invoices = [] } = useQuery({
    queryKey: ['invoices'],
    queryFn: () => invoicesApi.list(),
  })

  // Mutations
  const markPaidMutation = useMutation({
    mutationFn: (id: string) => paymentsApi.markPaid(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payments'] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      setConfirmAction(null)
    },
  })

  const refundMutation = useMutation({
    mutationFn: ({ id, amount }: { id: string; amount?: number }) =>
      paymentsApi.refund(id, amount),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payments'] })
      setConfirmAction(null)
      setRefundAmount('')
      setRefundType('full')
    },
  })

  const retryMutation = useMutation({
    mutationFn: (id: string) => paymentsApi.retry(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payments'] })
      setConfirmAction(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => paymentsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payments'] })
      setConfirmAction(null)
    },
  })

  const recordManualMutation = useMutation({
    mutationFn: (data: { invoice_id: string; amount: number; currency: string; reference?: string; notes?: string }) =>
      paymentsApi.recordManual(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payments'] })
      queryClient.invalidateQueries({ queryKey: ['invoices'] })
      setShowRecordDialog(false)
      setRecordInvoiceId('')
      setRecordAmount('')
      setRecordCurrency('USD')
      setRecordReference('')
      setRecordNotes('')
    },
  })

  // Helpers
  const getCustomerName = (customerId: string) => {
    const customer = customers.find(c => c.id === customerId)
    return customer?.name || customerId.slice(0, 8)
  }

  const getInvoiceNumber = (invoiceId: string) => {
    const invoice = invoices.find(i => i.id === invoiceId)
    return invoice?.invoice_number || invoiceId.slice(0, 8)
  }

  // Filter payments
  const filteredPayments = payments.filter(payment => {
    if (!search) return true
    const customerName = getCustomerName(payment.customer_id).toLowerCase()
    const invoiceNumber = getInvoiceNumber(payment.invoice_id).toLowerCase()
    const searchLower = search.toLowerCase()
    return customerName.includes(searchLower) || invoiceNumber.includes(searchLower)
  })

  // Stats
  const stats = {
    total: payments.length,
    pending: payments.filter(p => p.status === 'pending').length,
    succeeded: payments.filter(p => p.status === 'succeeded').length,
    failed: payments.filter(p => p.status === 'failed').length,
  }

  const isActionPending = markPaidMutation.isPending || refundMutation.isPending || deleteMutation.isPending || retryMutation.isPending

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Payments"
        description="Track and manage payment transactions"
        actions={
          <>
            <Button onClick={() => setShowRecordDialog(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Record Payment
            </Button>
            <Link
              to="/admin/payment-requests"
              className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <Send className="h-4 w-4" />
              Payment Requests
            </Link>
          </>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Payments
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Pending
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{stats.pending}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Succeeded
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.succeeded}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Failed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats.failed}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by customer or invoice..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select
          value={statusFilter}
          onValueChange={(value) => setStatusFilter(value as PaymentStatus | 'all')}
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="processing">Processing</SelectItem>
            <SelectItem value="succeeded">Succeeded</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="refunded">Refunded</SelectItem>
            <SelectItem value="canceled">Canceled</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={providerFilter}
          onValueChange={(value) => setProviderFilter(value as PaymentProvider | 'all')}
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Provider" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Providers</SelectItem>
            <SelectItem value="stripe">Stripe</SelectItem>
            <SelectItem value="ucp">UCP</SelectItem>
            <SelectItem value="manual">Manual</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Payments Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <TableHead>Invoice</TableHead>
              <SortableTableHead label="Amount" sortKey="amount_cents" sort={sort} onSort={setSort} />
              <SortableTableHead label="Provider" sortKey="provider" sort={sort} onSort={setSort} />
              <SortableTableHead label="Status" sortKey="status" sort={sort} onSort={setSort} />
              <SortableTableHead label="Created" sortKey="created_at" sort={sort} onSort={setSort} />
              <TableHead className="w-[60px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                </TableRow>
              ))
            ) : filteredPayments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                  No payments found
                </TableCell>
              </TableRow>
            ) : (
              filteredPayments.map((payment) => (
                <TableRow key={payment.id}>
                  <TableCell className="font-medium">
                    {getCustomerName(payment.customer_id)}
                  </TableCell>
                  <TableCell>
                    <code className="text-xs">{getInvoiceNumber(payment.invoice_id)}</code>
                  </TableCell>
                  <TableCell>
                    {formatCurrency(payment.amount, payment.currency)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {providerLabels[payment.provider] || payment.provider}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={statusColors[payment.status] || 'secondary'}>
                      {payment.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {format(new Date(payment.created_at), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setSelectedPayment(payment)}>
                          <Eye className="mr-2 h-4 w-4" />
                          View Details
                        </DropdownMenuItem>
                        {payment.status === 'pending' && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => setConfirmAction({ type: 'markPaid', payment })}>
                              <Check className="mr-2 h-4 w-4 text-green-600" />
                              Mark as Paid
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() => setConfirmAction({ type: 'delete', payment })}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </>
                        )}
                        {payment.status === 'succeeded' && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => {
                              setRefundType('full')
                              setRefundAmount('')
                              setConfirmAction({ type: 'refund', payment })
                            }}>
                              <RefreshCw className="mr-2 h-4 w-4 text-orange-600" />
                              Refund
                            </DropdownMenuItem>
                          </>
                        )}
                        {payment.status === 'failed' && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onClick={() => setConfirmAction({ type: 'retry', payment })}>
                              <RotateCcw className="mr-2 h-4 w-4 text-blue-600" />
                              Retry Payment
                            </DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
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

      {/* Payment Details Dialog */}
      <Dialog open={!!selectedPayment} onOpenChange={() => setSelectedPayment(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5" />
              Payment Details
            </DialogTitle>
            <DialogDescription>
              View payment information and related entities.
            </DialogDescription>
          </DialogHeader>
          {selectedPayment && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Amount</p>
                  <p className="text-lg font-semibold">
                    {formatCurrency(selectedPayment.amount, selectedPayment.currency)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Status</p>
                  <Badge variant={statusColors[selectedPayment.status] || 'secondary'}>
                    {selectedPayment.status}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Provider</p>
                  <p>{providerLabels[selectedPayment.provider] || selectedPayment.provider}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Customer</p>
                  <Link
                    to={`/admin/customers/${selectedPayment.customer_id}`}
                    className="text-sm text-blue-600 hover:underline flex items-center gap-1"
                    onClick={() => setSelectedPayment(null)}
                  >
                    {getCustomerName(selectedPayment.customer_id)}
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Invoice</p>
                  <Link
                    to={`/admin/invoices/${selectedPayment.invoice_id}`}
                    className="text-sm text-blue-600 hover:underline flex items-center gap-1"
                    onClick={() => setSelectedPayment(null)}
                  >
                    {getInvoiceNumber(selectedPayment.invoice_id)}
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Created</p>
                  <p>{format(new Date(selectedPayment.created_at), 'PPpp')}</p>
                </div>
              </div>

              {selectedPayment.provider_payment_id && (
                <div>
                  <p className="text-sm text-muted-foreground">Provider Payment ID</p>
                  <code className="text-xs">{selectedPayment.provider_payment_id}</code>
                </div>
              )}

              {selectedPayment.provider_checkout_url && (
                <div>
                  <p className="text-sm text-muted-foreground">Checkout URL</p>
                  <a
                    href={selectedPayment.provider_checkout_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:underline flex items-center gap-1"
                  >
                    Open checkout <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}

              {selectedPayment.failure_reason && (
                <div>
                  <p className="text-sm text-muted-foreground">Failure Reason</p>
                  <p className="text-sm text-red-600">{selectedPayment.failure_reason}</p>
                </div>
              )}

              {selectedPayment.completed_at && (
                <div>
                  <p className="text-sm text-muted-foreground">Completed</p>
                  <p>{format(new Date(selectedPayment.completed_at), 'PPpp')}</p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Confirmation Dialog */}
      <Dialog open={!!confirmAction} onOpenChange={() => {
        setConfirmAction(null)
        setRefundAmount('')
        setRefundType('full')
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirmAction?.type === 'markPaid' && 'Mark Payment as Paid'}
              {confirmAction?.type === 'refund' && 'Refund Payment'}
              {confirmAction?.type === 'delete' && 'Delete Payment'}
              {confirmAction?.type === 'retry' && 'Retry Payment'}
            </DialogTitle>
            <DialogDescription>
              {confirmAction?.type === 'markPaid' && (
                <>Are you sure you want to mark this payment as paid? This will also update the invoice status.</>
              )}
              {confirmAction?.type === 'refund' && (
                <>Choose a full or partial refund. This action cannot be undone.</>
              )}
              {confirmAction?.type === 'delete' && (
                <>Are you sure you want to delete this pending payment?</>
              )}
              {confirmAction?.type === 'retry' && (
                <>Are you sure you want to retry this failed payment? It will be reset to pending status.</>
              )}
            </DialogDescription>
          </DialogHeader>
          {confirmAction && (
            <div className="space-y-4 py-4">
              <div className="space-y-1">
                <p className="text-sm">
                  <span className="text-muted-foreground">Amount:</span>{' '}
                  {formatCurrency(confirmAction.payment.amount, confirmAction.payment.currency)}
                </p>
                <p className="text-sm">
                  <span className="text-muted-foreground">Customer:</span>{' '}
                  {getCustomerName(confirmAction.payment.customer_id)}
                </p>
              </div>

              {/* Partial Refund UI */}
              {confirmAction.type === 'refund' && (
                <div className="space-y-3 border-t pt-3">
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="refundType"
                        checked={refundType === 'full'}
                        onChange={() => {
                          setRefundType('full')
                          setRefundAmount('')
                        }}
                        className="accent-primary"
                      />
                      <span className="text-sm">Full refund</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="refundType"
                        checked={refundType === 'partial'}
                        onChange={() => setRefundType('partial')}
                        className="accent-primary"
                      />
                      <span className="text-sm">Partial refund</span>
                    </label>
                  </div>
                  {refundType === 'partial' && (
                    <div className="space-y-1">
                      <Label htmlFor="refundAmount">Refund amount ({confirmAction.payment.currency})</Label>
                      <Input
                        id="refundAmount"
                        type="number"
                        step="0.01"
                        min="0.01"
                        max={confirmAction.payment.amount}
                        value={refundAmount}
                        onChange={(e) => setRefundAmount(e.target.value)}
                        placeholder={`Max ${formatCurrency(confirmAction.payment.amount, confirmAction.payment.currency)}`}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setConfirmAction(null)
              setRefundAmount('')
              setRefundType('full')
            }}>
              Cancel
            </Button>
            <Button
              variant={confirmAction?.type === 'delete' ? 'destructive' : 'default'}
              onClick={() => {
                if (!confirmAction) return
                if (confirmAction.type === 'markPaid') {
                  markPaidMutation.mutate(confirmAction.payment.id)
                } else if (confirmAction.type === 'refund') {
                  const amount = refundType === 'partial' && refundAmount
                    ? parseFloat(refundAmount)
                    : undefined
                  refundMutation.mutate({ id: confirmAction.payment.id, amount })
                } else if (confirmAction.type === 'retry') {
                  retryMutation.mutate(confirmAction.payment.id)
                } else if (confirmAction.type === 'delete') {
                  deleteMutation.mutate(confirmAction.payment.id)
                }
              }}
              disabled={isActionPending || (confirmAction?.type === 'refund' && refundType === 'partial' && (!refundAmount || parseFloat(refundAmount) <= 0 || parseFloat(refundAmount) > parseFloat(confirmAction.payment.amount)))}
            >
              {isActionPending ? 'Processing...' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Record Manual Payment Dialog */}
      <Dialog open={showRecordDialog} onOpenChange={(open) => {
        if (!open) {
          setShowRecordDialog(false)
          setRecordInvoiceId('')
          setRecordAmount('')
          setRecordCurrency('USD')
          setRecordReference('')
          setRecordNotes('')
        }
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5" />
              Record Manual Payment
            </DialogTitle>
            <DialogDescription>
              Record an offline payment such as a check, wire transfer, or cash payment.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="recordInvoice">Invoice</Label>
              <Select value={recordInvoiceId} onValueChange={(id) => {
                setRecordInvoiceId(id)
                const inv = invoices.find(i => i.id === id)
                if (inv) {
                  setRecordAmount(String(inv.total))
                  setRecordCurrency(inv.currency)
                }
              }}>
                <SelectTrigger id="recordInvoice">
                  <SelectValue placeholder="Select an invoice..." />
                </SelectTrigger>
                <SelectContent>
                  {invoices
                    .filter(inv => inv.status === 'finalized')
                    .map(inv => (
                      <SelectItem key={inv.id} value={inv.id}>
                        {inv.invoice_number || inv.id.slice(0, 8)} — {formatCurrency(inv.total, inv.currency)}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="recordAmount">Amount</Label>
                <Input
                  id="recordAmount"
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={recordAmount}
                  onChange={(e) => setRecordAmount(e.target.value)}
                  placeholder="0.00"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="recordCurrency">Currency</Label>
                <Input
                  id="recordCurrency"
                  value={recordCurrency}
                  onChange={(e) => setRecordCurrency(e.target.value.toUpperCase())}
                  maxLength={3}
                  placeholder="USD"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="recordReference">Reference (optional)</Label>
              <Input
                id="recordReference"
                value={recordReference}
                onChange={(e) => setRecordReference(e.target.value)}
                placeholder="e.g. Check #1234, Wire transfer ID"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="recordNotes">Notes (optional)</Label>
              <Input
                id="recordNotes"
                value={recordNotes}
                onChange={(e) => setRecordNotes(e.target.value)}
                placeholder="Additional notes about this payment"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowRecordDialog(false)
              setRecordInvoiceId('')
              setRecordAmount('')
              setRecordCurrency('USD')
              setRecordReference('')
              setRecordNotes('')
            }}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (!recordInvoiceId || !recordAmount) return
                recordManualMutation.mutate({
                  invoice_id: recordInvoiceId,
                  amount: parseFloat(recordAmount),
                  currency: recordCurrency,
                  reference: recordReference || undefined,
                  notes: recordNotes || undefined,
                })
              }}
              disabled={!recordInvoiceId || !recordAmount || parseFloat(recordAmount) <= 0 || recordManualMutation.isPending}
            >
              {recordManualMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Recording...
                </>
              ) : (
                'Record Payment'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
