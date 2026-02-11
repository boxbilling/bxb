import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, CreditCard, Check, X, RefreshCw, ExternalLink } from 'lucide-react'
import { format } from 'date-fns'

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
  DialogFooter,
  DialogDescription,
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
import { paymentsApi, customersApi, invoicesApi } from '@/lib/api'
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

const providerLabels: Record<string, string> = {
  stripe: 'Stripe',
  ucp: 'UCP',
  manual: 'Manual',
}

function formatAmount(amount: string, currency: string): string {
  const num = parseFloat(amount)
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(num)
}

export default function PaymentsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<PaymentStatus | 'all'>('all')
  const [providerFilter, setProviderFilter] = useState<PaymentProvider | 'all'>('all')
  const [selectedPayment, setSelectedPayment] = useState<PaymentResponse | null>(null)
  const [confirmAction, setConfirmAction] = useState<{ type: 'refund' | 'markPaid' | 'delete'; payment: PaymentResponse } | null>(null)

  // Fetch payments
  const { data: payments = [], isLoading } = useQuery({
    queryKey: ['payments', statusFilter, providerFilter],
    queryFn: () => paymentsApi.list({
      status: statusFilter === 'all' ? undefined : statusFilter,
      provider: providerFilter === 'all' ? undefined : providerFilter,
    }),
  })

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
    mutationFn: (id: string) => paymentsApi.refund(id),
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Payments</h1>
        <p className="text-muted-foreground">
          Track and manage payment transactions
        </p>
      </div>

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
              <TableHead>Amount</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
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
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
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
                    {formatAmount(payment.amount, payment.currency)}
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
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setSelectedPayment(payment)}
                        title="View details"
                      >
                        <CreditCard className="h-4 w-4" />
                      </Button>
                      {payment.status === 'pending' && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setConfirmAction({ type: 'markPaid', payment })}
                          title="Mark as paid"
                        >
                          <Check className="h-4 w-4 text-green-600" />
                        </Button>
                      )}
                      {payment.status === 'succeeded' && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setConfirmAction({ type: 'refund', payment })}
                          title="Refund"
                        >
                          <RefreshCw className="h-4 w-4 text-orange-600" />
                        </Button>
                      )}
                      {payment.status === 'pending' && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setConfirmAction({ type: 'delete', payment })}
                          title="Delete"
                        >
                          <X className="h-4 w-4 text-red-600" />
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

      {/* Payment Details Dialog */}
      <Dialog open={!!selectedPayment} onOpenChange={() => setSelectedPayment(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Payment Details</DialogTitle>
          </DialogHeader>
          {selectedPayment && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Amount</p>
                  <p className="text-lg font-semibold">
                    {formatAmount(selectedPayment.amount, selectedPayment.currency)}
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
                  <p>{getCustomerName(selectedPayment.customer_id)}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Invoice</p>
                  <p>{getInvoiceNumber(selectedPayment.invoice_id)}</p>
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
      <Dialog open={!!confirmAction} onOpenChange={() => setConfirmAction(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirmAction?.type === 'markPaid' && 'Mark Payment as Paid'}
              {confirmAction?.type === 'refund' && 'Refund Payment'}
              {confirmAction?.type === 'delete' && 'Delete Payment'}
            </DialogTitle>
            <DialogDescription>
              {confirmAction?.type === 'markPaid' && (
                <>Are you sure you want to mark this payment as paid? This will also update the invoice status.</>
              )}
              {confirmAction?.type === 'refund' && (
                <>Are you sure you want to refund this payment? This action cannot be undone.</>
              )}
              {confirmAction?.type === 'delete' && (
                <>Are you sure you want to delete this pending payment?</>
              )}
            </DialogDescription>
          </DialogHeader>
          {confirmAction && (
            <div className="py-4">
              <p className="text-sm">
                <span className="text-muted-foreground">Amount:</span>{' '}
                {formatAmount(confirmAction.payment.amount, confirmAction.payment.currency)}
              </p>
              <p className="text-sm">
                <span className="text-muted-foreground">Customer:</span>{' '}
                {getCustomerName(confirmAction.payment.customer_id)}
              </p>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmAction(null)}>
              Cancel
            </Button>
            <Button
              variant={confirmAction?.type === 'delete' ? 'destructive' : 'default'}
              onClick={() => {
                if (!confirmAction) return
                if (confirmAction.type === 'markPaid') {
                  markPaidMutation.mutate(confirmAction.payment.id)
                } else if (confirmAction.type === 'refund') {
                  refundMutation.mutate(confirmAction.payment.id)
                } else if (confirmAction.type === 'delete') {
                  deleteMutation.mutate(confirmAction.payment.id)
                }
              }}
              disabled={markPaidMutation.isPending || refundMutation.isPending || deleteMutation.isPending}
            >
              {(markPaidMutation.isPending || refundMutation.isPending || deleteMutation.isPending) ? 'Processing...' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
