import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Search,
  MoreHorizontal,
  Eye,
  Send,
  CheckCircle,
  Zap,
  Clock,
  AlertCircle,
  ExternalLink,
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
import { TablePagination } from '@/components/TablePagination'
import { SortableTableHead, useSortState } from '@/components/SortableTableHead'
import PageHeader from '@/components/PageHeader'
import { paymentRequestsApi, customersApi, invoicesApi, ApiError } from '@/lib/api'
import type { PaymentRequest, PaymentRequestCreate, PaymentAttemptEntry } from '@/lib/api'
import { formatCents } from '@/lib/utils'

const PAGE_SIZE = 20

function getStatusBadge(status: string) {
  switch (status) {
    case 'pending':
      return <Badge variant="secondary">{status}</Badge>
    case 'succeeded':
      return <Badge variant="default">{status}</Badge>
    case 'failed':
      return <Badge variant="destructive">{status}</Badge>
    case 'processing':
      return <Badge variant="outline">{status}</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

// --- Attempt History Timeline ---
function AttemptHistoryTimeline({ entries }: { entries: PaymentAttemptEntry[] }) {
  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No attempt history available</p>
    )
  }

  return (
    <div className="space-y-3">
      {entries.map((entry, idx) => {
        const isSuccess = entry.new_status === 'succeeded'
        const isFailed = entry.new_status === 'failed'
        const isCreated = entry.action === 'created'

        const dotColor = isSuccess
          ? 'bg-green-500'
          : isFailed
            ? 'bg-red-500'
            : isCreated
              ? 'bg-blue-500'
              : 'bg-gray-400'

        return (
          <div key={idx} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className={`h-3 w-3 rounded-full ${dotColor} mt-1`} />
              {idx < entries.length - 1 && (
                <div className="w-0.5 flex-1 bg-border" />
              )}
            </div>
            <div className="pb-3 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium capitalize">
                  {entry.action.replace(/_/g, ' ')}
                </span>
                {entry.attempt_number != null && entry.attempt_number > 0 && (
                  <Badge variant="outline" className="text-xs">
                    Attempt #{entry.attempt_number}
                  </Badge>
                )}
              </div>
              {entry.old_status && entry.new_status && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {entry.old_status} → {entry.new_status}
                </p>
              )}
              {entry.new_status && !entry.old_status && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  Status: {entry.new_status}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                {format(new Date(entry.timestamp), 'MMM d, yyyy HH:mm:ss')}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// --- View Details Dialog ---
function ViewDetailsDialog({
  open,
  onOpenChange,
  paymentRequest,
  customerName,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  paymentRequest: PaymentRequest | null
  customerName: string
}) {
  const { data: attemptData } = useQuery({
    queryKey: ['payment-request-attempts', paymentRequest?.id],
    queryFn: () => paymentRequestsApi.getAttempts(paymentRequest!.id),
    enabled: !!paymentRequest,
  })

  if (!paymentRequest) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Payment Request Details</DialogTitle>
          <DialogDescription>
            Full details for this payment request
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="rounded-md bg-muted p-3 text-sm space-y-1">
            <div className="flex justify-between">
              <span className="text-muted-foreground">ID</span>
              <code className="font-mono text-xs">{paymentRequest.id}</code>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Customer</span>
              <Link
                to={`/admin/customers/${paymentRequest.customer_id}`}
                className="font-medium text-blue-600 hover:underline flex items-center gap-1"
                onClick={() => onOpenChange(false)}
              >
                {customerName}
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Amount</span>
              <span className="font-medium">
                {formatCents(parseInt(paymentRequest.amount_cents as unknown as string))}{' '}
                <Badge variant="outline" className="ml-1 text-xs">{paymentRequest.amount_currency}</Badge>
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Payment Status</span>
              {getStatusBadge(paymentRequest.payment_status)}
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Attempts</span>
              <span className="font-medium">{paymentRequest.payment_attempts}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Ready for Processing</span>
              <Badge variant={paymentRequest.ready_for_payment_processing ? 'default' : 'secondary'}>
                {paymentRequest.ready_for_payment_processing ? 'Ready' : 'Not Ready'}
              </Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Campaign</span>
              <span className="font-medium">
                {paymentRequest.dunning_campaign_id
                  ? paymentRequest.dunning_campaign_id.slice(0, 8) + '...'
                  : '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Created</span>
              <span className="font-medium">
                {format(new Date(paymentRequest.created_at), 'MMM d, yyyy HH:mm')}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Updated</span>
              <span className="font-medium">
                {format(new Date(paymentRequest.updated_at), 'MMM d, yyyy HH:mm')}
              </span>
            </div>
          </div>

          {/* Invoices table */}
          {paymentRequest.invoices && paymentRequest.invoices.length > 0 && (
            <div>
              <h4 className="text-sm font-medium mb-2">Invoices ({paymentRequest.invoices.length})</h4>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Invoice ID</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {paymentRequest.invoices.map((inv) => (
                      <TableRow key={inv.id}>
                        <TableCell>
                          <Link
                            to={`/admin/invoices/${inv.invoice_id}`}
                            className="font-mono text-xs text-blue-600 hover:underline flex items-center gap-1"
                            onClick={() => onOpenChange(false)}
                          >
                            {inv.invoice_id.slice(0, 8)}...
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {format(new Date(inv.created_at), 'MMM d, yyyy')}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}

          {/* Attempt History */}
          <div>
            <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Payment Attempt History
            </h4>
            {attemptData ? (
              <AttemptHistoryTimeline entries={attemptData.entries} />
            ) : (
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --- Batch Create Dialog ---
function BatchCreateDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()

  const batchMutation = useMutation({
    mutationFn: () => paymentRequestsApi.batchCreate(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests'] })
      if (data.created > 0) {
        toast.success(`Created ${data.created} payment request${data.created !== 1 ? 's' : ''} for customers with overdue invoices`)
      } else {
        toast.info('No customers with overdue invoices found')
      }
      if (data.failed > 0) {
        toast.error(`${data.failed} payment request${data.failed !== 1 ? 's' : ''} failed to create`)
      }
      onOpenChange(false)
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to batch create payment requests'
      toast.error(message)
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Batch Create Payment Requests
          </DialogTitle>
          <DialogDescription>
            Automatically create payment requests for all customers who have overdue finalized invoices (past due date).
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950">
            <div className="flex gap-2">
              <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
              <div>
                <p className="font-medium text-amber-800 dark:text-amber-200">This will:</p>
                <ul className="mt-1 text-amber-700 dark:text-amber-300 list-disc pl-4 space-y-1">
                  <li>Find all finalized invoices with a due date in the past</li>
                  <li>Group them by customer and currency</li>
                  <li>Create one payment request per customer+currency</li>
                  <li>Send webhook notifications for each created request</li>
                </ul>
              </div>
            </div>
          </div>

          {batchMutation.data && (
            <div className="mt-4 rounded-md bg-muted p-3 text-sm space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Customers processed</span>
                <span className="font-medium">{batchMutation.data.total_customers}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span className="font-medium text-green-600">{batchMutation.data.created}</span>
              </div>
              {batchMutation.data.failed > 0 && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Failed</span>
                  <span className="font-medium text-red-600">{batchMutation.data.failed}</span>
                </div>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => batchMutation.mutate()}
            disabled={batchMutation.isPending}
          >
            {batchMutation.isPending ? 'Creating...' : 'Create for All Overdue'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// --- Create Payment Request Dialog ---
function CreatePaymentRequestDialog({
  open,
  onOpenChange,
  customers,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  customers: Array<{ id: string; name: string }>
  onSubmit: (data: PaymentRequestCreate) => void
  isLoading: boolean
}) {
  const [selectedCustomerId, setSelectedCustomerId] = useState('')
  const [selectedInvoiceIds, setSelectedInvoiceIds] = useState<string[]>([])

  const { data: invoices = [] } = useQuery({
    queryKey: ['invoices', selectedCustomerId],
    queryFn: () => invoicesApi.list({ customer_id: selectedCustomerId }),
    enabled: !!selectedCustomerId,
  })

  // Filter to only show finalized invoices (the backend requires finalized status)
  const finalizedInvoices = invoices.filter((inv) => inv.status === 'finalized')

  // Identify overdue invoices (due_date in the past)
  const now = new Date()
  const overdueInvoiceIds = new Set(
    finalizedInvoices
      .filter((inv) => inv.due_date && new Date(inv.due_date) < now)
      .map((inv) => inv.id)
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      customer_id: selectedCustomerId,
      invoice_ids: selectedInvoiceIds,
    } as unknown as PaymentRequestCreate)
  }

  const handleCustomerChange = (value: string) => {
    setSelectedCustomerId(value)
    setSelectedInvoiceIds([])
  }

  const toggleInvoice = (invoiceId: string) => {
    setSelectedInvoiceIds((prev) =>
      prev.includes(invoiceId)
        ? prev.filter((id) => id !== invoiceId)
        : [...prev, invoiceId]
    )
  }

  const selectAllOverdue = () => {
    const overdueIds = finalizedInvoices
      .filter((inv) => inv.due_date && new Date(inv.due_date) < now)
      .map((inv) => inv.id)
    setSelectedInvoiceIds(overdueIds)
  }

  const allOverdueSelected =
    overdueInvoiceIds.size > 0 &&
    [...overdueInvoiceIds].every((id) => selectedInvoiceIds.includes(id))

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setSelectedCustomerId('')
      setSelectedInvoiceIds([])
    }
    onOpenChange(nextOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create Payment Request</DialogTitle>
            <DialogDescription>
              Select a customer and their invoices to create a payment request
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="customer">Customer *</Label>
              <Select value={selectedCustomerId} onValueChange={handleCustomerChange}>
                <SelectTrigger id="customer">
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

            {selectedCustomerId && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Invoices * <span className="text-muted-foreground font-normal">(finalized only)</span></Label>
                  {overdueInvoiceIds.size > 0 && (
                    <label className="flex items-center gap-2 cursor-pointer text-sm">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-input accent-destructive"
                        checked={allOverdueSelected}
                        onChange={() => {
                          if (allOverdueSelected) {
                            setSelectedInvoiceIds((prev) =>
                              prev.filter((id) => !overdueInvoiceIds.has(id))
                            )
                          } else {
                            selectAllOverdue()
                          }
                        }}
                      />
                      <span className="text-destructive font-medium">
                        Select all overdue ({overdueInvoiceIds.size})
                      </span>
                    </label>
                  )}
                </div>
                {finalizedInvoices.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No finalized invoices found for this customer
                  </p>
                ) : (
                  <div className="max-h-[200px] overflow-y-auto rounded-md border p-2 space-y-2">
                    {finalizedInvoices.map((inv) => {
                      const isOverdue = overdueInvoiceIds.has(inv.id)
                      return (
                        <label
                          key={inv.id}
                          className={`flex items-center gap-3 p-2 rounded hover:bg-muted cursor-pointer ${
                            isOverdue ? 'border-l-2 border-destructive pl-3' : ''
                          }`}
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-input"
                            checked={selectedInvoiceIds.includes(inv.id)}
                            onChange={() => toggleInvoice(inv.id)}
                          />
                          <span className="flex-1 text-sm">
                            <code className="font-mono">{inv.invoice_number}</code>
                          </span>
                          {isOverdue && (
                            <Badge variant="destructive" className="text-xs">
                              overdue
                            </Badge>
                          )}
                          <span className="text-sm text-muted-foreground">
                            {formatCents(parseInt(inv.total_cents as unknown as string), inv.currency)}
                          </span>
                        </label>
                      )
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isLoading || selectedInvoiceIds.length === 0}
            >
              {isLoading ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function PaymentRequestsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [createOpen, setCreateOpen] = useState(false)
  const [batchOpen, setBatchOpen] = useState(false)
  const [viewingPR, setViewingPR] = useState<PaymentRequest | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const { sort, setSort, orderBy } = useSortState()

  // Fetch payment requests
  const {
    data,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['payment-requests', page, pageSize, orderBy],
    queryFn: () => paymentRequestsApi.listPaginated({ skip: (page - 1) * pageSize, limit: pageSize, order_by: orderBy }),
  })

  const paymentRequests = data?.data ?? []
  const totalCount = data?.totalCount ?? 0

  // Fetch customers for lookups
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  // Build customer map for efficient lookups
  const customerMap = new Map(customers?.map((c) => [c.id, c]) ?? [])

  // Filter payment requests
  const filtered = paymentRequests.filter((pr) => {
    const customer = customerMap.get(pr.customer_id)
    const customerName = customer?.name ?? pr.customer_id
    const matchesSearch =
      !search ||
      customerName.toLowerCase().includes(search.toLowerCase()) ||
      pr.id.toLowerCase().includes(search.toLowerCase())
    const matchesStatus =
      statusFilter === 'all' || pr.payment_status === statusFilter
    return matchesSearch && matchesStatus
  })

  // Stats
  const stats = {
    total: paymentRequests.length,
    pending: paymentRequests.filter((pr) => pr.payment_status === 'pending').length,
    ready: paymentRequests.filter((pr) => pr.ready_for_payment_processing).length,
    totalAmount: paymentRequests.reduce(
      (sum, pr) => sum + parseInt(pr.amount_cents as unknown as string),
      0
    ),
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: PaymentRequestCreate) => paymentRequestsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-requests'] })
      setCreateOpen(false)
      toast.success('Payment request created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to create payment request'
      toast.error(message)
    },
  })

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load payment requests. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            Payment Requests
          </span>
        }
        description="Manage payment collection requests"
        actions={
          <>
            <Link
              to="/admin/payments"
              className="inline-flex items-center gap-1 text-sm font-normal text-muted-foreground hover:text-foreground transition-colors"
            >
              View Payments
              <ExternalLink className="h-3 w-3" />
            </Link>
            <Button variant="outline" onClick={() => setBatchOpen(true)}>
              <Zap className="mr-2 h-4 w-4" />
              Batch Create
            </Button>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Payment Request
            </Button>
          </>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Requests
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
            <div className="text-2xl font-bold text-blue-600">{stats.pending}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Ready for Processing
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats.ready}
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
            <div className="text-2xl font-bold">
              {formatCents(stats.totalAmount)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div className="relative flex-1 md:max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by customer or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="succeeded">Succeeded</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="processing">Processing</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Customer</TableHead>
              <SortableTableHead label="Amount" sortKey="amount_cents" sort={sort} onSort={setSort} />
              <SortableTableHead label="Payment Status" sortKey="payment_status" sort={sort} onSort={setSort} />
              <TableHead className="hidden md:table-cell">Attempts</TableHead>
              <TableHead className="hidden md:table-cell">Ready</TableHead>
              <TableHead>Invoices</TableHead>
              <TableHead className="hidden md:table-cell">Campaign</TableHead>
              <SortableTableHead label="Created" sortKey="created_at" sort={sort} onSort={setSort} />
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-10" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-10" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={9}
                  className="h-24 text-center text-muted-foreground"
                >
                  <Send className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No payment requests found
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((pr) => {
                const customer = customerMap.get(pr.customer_id)
                return (
                  <TableRow key={pr.id}>
                    <TableCell className="font-medium">
                      {customer?.name ?? pr.customer_id}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {formatCents(parseInt(pr.amount_cents as unknown as string))}
                        <Badge variant="outline" className="ml-1 text-xs">
                          {pr.amount_currency}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell>{getStatusBadge(pr.payment_status)}</TableCell>
                    <TableCell className="hidden md:table-cell">{pr.payment_attempts}</TableCell>
                    <TableCell className="hidden md:table-cell">
                      {pr.ready_for_payment_processing ? (
                        <Badge variant="default" className="bg-green-600">
                          <CheckCircle className="mr-1 h-3 w-3" />
                          Ready
                        </Badge>
                      ) : (
                        <Badge variant="secondary">Not Ready</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {pr.invoices?.length ?? 0}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-muted-foreground text-sm">
                      {pr.dunning_campaign_id
                        ? pr.dunning_campaign_id.slice(0, 8) + '...'
                        : '—'}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {format(new Date(pr.created_at), 'MMM d, yyyy')}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => setViewingPR(pr)}>
                            <Eye className="mr-2 h-4 w-4" />
                            View Details
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                )
              })
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

      {/* View Details Dialog */}
      <ViewDetailsDialog
        open={!!viewingPR}
        onOpenChange={(open) => !open && setViewingPR(null)}
        paymentRequest={viewingPR}
        customerName={
          viewingPR
            ? customerMap.get(viewingPR.customer_id)?.name ?? viewingPR.customer_id
            : ''
        }
      />

      {/* Create Payment Request Dialog */}
      <CreatePaymentRequestDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        customers={customers.map((c) => ({ id: c.id, name: c.name }))}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
      />

      {/* Batch Create Dialog */}
      <BatchCreateDialog
        open={batchOpen}
        onOpenChange={setBatchOpen}
      />
    </div>
  )
}
