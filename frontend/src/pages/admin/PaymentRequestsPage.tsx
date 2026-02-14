import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Search,
  MoreHorizontal,
  Eye,
  Send,
  CheckCircle,
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
import { paymentRequestsApi, customersApi, invoicesApi, ApiError } from '@/lib/api'
import type { PaymentRequest, PaymentRequestCreate } from '@/types/billing'

function formatCurrency(cents: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}

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
  if (!paymentRequest) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
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
              <span className="font-medium">{customerName}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Amount</span>
              <span className="font-medium">
                {formatCurrency(parseInt(paymentRequest.amount_cents as unknown as string))}{' '}
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
                          <code className="font-mono text-xs">
                            {inv.invoice_id.slice(0, 8)}...
                          </code>
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
                <Label>Invoices *</Label>
                {invoices.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No invoices found for this customer
                  </p>
                ) : (
                  <div className="max-h-[200px] overflow-y-auto rounded-md border p-2 space-y-2">
                    {invoices.map((inv) => (
                      <label
                        key={inv.id}
                        className="flex items-center gap-3 p-2 rounded hover:bg-muted cursor-pointer"
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
                        <Badge variant="secondary" className="text-xs">
                          {inv.status}
                        </Badge>
                        <span className="text-sm text-muted-foreground">
                          {formatCurrency(parseInt(inv.total as unknown as string), inv.currency)}
                        </span>
                      </label>
                    ))}
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
  const [viewingPR, setViewingPR] = useState<PaymentRequest | null>(null)

  // Fetch payment requests
  const {
    data: paymentRequests = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['payment-requests'],
    queryFn: () => paymentRequestsApi.list(),
  })

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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Payment Requests</h2>
          <p className="text-muted-foreground">
            Manage payment collection requests
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Payment Request
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
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
            placeholder="Search by customer or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
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
              <TableHead>Amount</TableHead>
              <TableHead>Payment Status</TableHead>
              <TableHead>Attempts</TableHead>
              <TableHead>Ready</TableHead>
              <TableHead>Invoices</TableHead>
              <TableHead>Campaign</TableHead>
              <TableHead>Created</TableHead>
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
                  <TableCell><Skeleton className="h-5 w-10" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-10" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
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
                        {formatCurrency(parseInt(pr.amount_cents as unknown as string))}
                        <Badge variant="outline" className="ml-1 text-xs">
                          {pr.amount_currency}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell>{getStatusBadge(pr.payment_status)}</TableCell>
                    <TableCell>{pr.payment_attempts}</TableCell>
                    <TableCell>
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
                    <TableCell className="text-muted-foreground text-sm">
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
    </div>
  )
}
