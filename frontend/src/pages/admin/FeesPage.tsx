import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Search,
  MoreHorizontal,
  Pencil,
  Eye,
  DollarSign,
  FileText,
  User,
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
import { feesApi, taxesApi, customersApi, invoicesApi, ApiError } from '@/lib/api'
import type { Fee, FeeUpdate, FeeType, FeePaymentStatus } from '@/types/billing'
import { formatCents } from '@/lib/utils'

const feeTypeBadge: Record<string, { variant: 'default' | 'secondary' | 'outline' | 'destructive'; className: string }> = {
  charge: { variant: 'default', className: 'bg-blue-600' },
  subscription: { variant: 'default', className: 'bg-purple-600' },
  add_on: { variant: 'default', className: 'bg-green-600' },
  credit: { variant: 'default', className: 'bg-orange-600' },
  commitment: { variant: 'default', className: 'bg-pink-600' },
}

const paymentStatusBadge: Record<string, { variant: 'default' | 'secondary' | 'outline' | 'destructive'; className?: string }> = {
  succeeded: { variant: 'default', className: 'bg-green-600' },
  pending: { variant: 'secondary', className: 'text-yellow-700' },
  failed: { variant: 'destructive' },
  refunded: { variant: 'outline', className: 'text-blue-600 border-blue-600' },
}

function formatTaxRate(rate: string | number): string {
  const num = typeof rate === 'string' ? parseFloat(rate) : rate
  return `${(num * 100).toFixed(2)}%`
}

function AppliedTaxesSection({ feeId }: { feeId: string }) {
  const { data: appliedTaxes = [], isLoading } = useQuery({
    queryKey: ['fee-taxes', feeId],
    queryFn: () => taxesApi.listApplied({ taxable_type: 'fee', taxable_id: feeId }),
  })

  if (isLoading) {
    return <Skeleton className="h-8 w-full" />
  }

  if (appliedTaxes.length === 0) {
    return null
  }

  return (
    <>
      <div className="flex justify-between items-center pt-2">
        <span className="text-muted-foreground font-medium">Applied Taxes</span>
      </div>
      {appliedTaxes.map((at) => (
        <div key={at.id} className="flex justify-between pl-4">
          <span className="text-muted-foreground">
            {at.tax_name || 'Tax'} {at.tax_rate ? `(${formatTaxRate(at.tax_rate)})` : ''}
          </span>
          <span className="font-medium">{formatCents(parseInt(at.tax_amount_cents))}</span>
        </div>
      ))}
    </>
  )
}

const PAGE_SIZE = 20

const feeTypes: FeeType[] = ['charge', 'subscription', 'add_on', 'credit', 'commitment']
const paymentStatuses: FeePaymentStatus[] = ['pending', 'succeeded', 'failed', 'refunded']

export default function FeesPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [feeTypeFilter, setFeeTypeFilter] = useState<string>('all')
  const [paymentStatusFilter, setPaymentStatusFilter] = useState<string>('all')
  const [editingFee, setEditingFee] = useState<Fee | null>(null)
  const [viewingFee, setViewingFee] = useState<Fee | null>(null)
  const [editForm, setEditForm] = useState<{
    payment_status: string
    description: string
    taxes_amount_cents: string
    total_amount_cents: string
  }>({ payment_status: '', description: '', taxes_amount_cents: '', total_amount_cents: '' })
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const { sort, setSort, orderBy } = useSortState()

  const {
    data: paginatedData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['fees', feeTypeFilter, paymentStatusFilter, page, pageSize, orderBy],
    queryFn: () =>
      feesApi.listPaginated({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        fee_type: feeTypeFilter !== 'all' ? (feeTypeFilter as FeeType) : undefined,
        payment_status: paymentStatusFilter !== 'all' ? (paymentStatusFilter as FeePaymentStatus) : undefined,
        order_by: orderBy,
      }),
  })

  const fees = paginatedData?.data ?? []
  const totalCount = paginatedData?.totalCount ?? 0

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  const { data: invoices = [] } = useQuery({
    queryKey: ['invoices'],
    queryFn: () => invoicesApi.list(),
  })

  const customerMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const c of customers) {
      map[c.id] = c.name || c.external_id
    }
    return map
  }, [customers])

  const invoiceMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const inv of invoices) {
      map[inv.id] = inv.invoice_number || inv.id
    }
    return map
  }, [invoices])

  const filteredFees = fees.filter((f) => {
    if (!search) return true
    const s = search.toLowerCase()
    return (
      (f.description && f.description.toLowerCase().includes(s)) ||
      (f.metric_code && f.metric_code.toLowerCase().includes(s))
    )
  })

  const stats = {
    total: fees.length,
    pending: fees.filter((f) => f.payment_status === 'pending').length,
    failed: fees.filter((f) => f.payment_status === 'failed').length,
    totalAmount: fees.reduce((sum, f) => sum + parseInt(f.total_amount_cents), 0),
  }

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: FeeUpdate }) =>
      feesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fees'] })
      setEditingFee(null)
      toast.success('Fee updated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to update fee'
      toast.error(message)
    },
  })

  const handleEdit = (fee: Fee) => {
    setEditForm({
      payment_status: fee.payment_status,
      description: fee.description ?? '',
      taxes_amount_cents: fee.taxes_amount_cents,
      total_amount_cents: fee.total_amount_cents,
    })
    setEditingFee(fee)
  }

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingFee) return
    const data: FeeUpdate = {
      payment_status: editForm.payment_status as FeePaymentStatus,
      description: editForm.description || null,
      taxes_amount_cents: editForm.taxes_amount_cents ? Number(editForm.taxes_amount_cents) : null,
      total_amount_cents: editForm.total_amount_cents ? Number(editForm.total_amount_cents) : null,
    }
    updateMutation.mutate({ id: editingFee.id, data })
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load fees. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Fees</h2>
        <p className="text-muted-foreground">
          View and manage billing fees
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Fees
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
            <div className="text-2xl font-bold text-yellow-600">
              {stats.pending}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Failed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {stats.failed}
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
            <div className="text-2xl font-bold text-green-600">
              {formatCents(stats.totalAmount)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by description or metric code..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={feeTypeFilter} onValueChange={setFeeTypeFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Fee Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {feeTypes.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={paymentStatusFilter} onValueChange={setPaymentStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Payment Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {paymentStatuses.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <SortableTableHead label="Fee Type" sortKey="fee_type" sort={sort} onSort={setSort} />
              <TableHead>Description</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Invoice</TableHead>
              <SortableTableHead label="Amount" sortKey="amount_cents" sort={sort} onSort={setSort} />
              <TableHead>Tax</TableHead>
              <TableHead>Total</TableHead>
              <SortableTableHead label="Payment Status" sortKey="payment_status" sort={sort} onSort={setSort} />
              <SortableTableHead label="Created" sortKey="created_at" sort={sort} onSort={setSort} />
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                </TableRow>
              ))
            ) : filteredFees.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={10}
                  className="h-24 text-center text-muted-foreground"
                >
                  <DollarSign className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  No fees found
                </TableCell>
              </TableRow>
            ) : (
              filteredFees.map((fee) => {
                const typeBadge = feeTypeBadge[fee.fee_type] ?? { variant: 'secondary' as const, className: '' }
                const statusBadge = paymentStatusBadge[fee.payment_status] ?? { variant: 'secondary' as const }
                return (
                  <TableRow key={fee.id}>
                    <TableCell>
                      <Badge variant={typeBadge.variant} className={typeBadge.className}>
                        {fee.fee_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate">
                      {fee.description || fee.metric_code || '—'}
                    </TableCell>
                    <TableCell>
                      <Link
                        to={`/admin/customers/${fee.customer_id}`}
                        className="flex items-center gap-1 text-sm text-primary hover:underline"
                      >
                        <User className="h-3 w-3" />
                        {customerMap[fee.customer_id] || fee.customer_id.slice(0, 8)}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {fee.invoice_id ? (
                        <Link
                          to={`/admin/invoices/${fee.invoice_id}`}
                          className="flex items-center gap-1 text-sm text-primary hover:underline"
                        >
                          <FileText className="h-3 w-3" />
                          {invoiceMap[fee.invoice_id] || fee.invoice_id.slice(0, 8)}
                        </Link>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>{formatCents(parseInt(fee.amount_cents))}</TableCell>
                    <TableCell>{formatCents(parseInt(fee.taxes_amount_cents))}</TableCell>
                    <TableCell>{formatCents(parseInt(fee.total_amount_cents))}</TableCell>
                    <TableCell>
                      <Badge variant={statusBadge.variant} className={statusBadge.className}>
                        {fee.payment_status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {format(new Date(fee.created_at), 'MMM d, yyyy')}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleEdit(fee)}>
                            <Pencil className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => setViewingFee(fee)}>
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

      {/* Edit Dialog */}
      <Dialog open={!!editingFee} onOpenChange={(open) => !open && setEditingFee(null)}>
        <DialogContent className="sm:max-w-[450px]">
          <form onSubmit={handleEditSubmit}>
            <DialogHeader>
              <DialogTitle>Edit Fee</DialogTitle>
              <DialogDescription>
                Update fee payment status and details
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="payment_status">Payment Status</Label>
                <Select
                  value={editForm.payment_status}
                  onValueChange={(value) =>
                    setEditForm({ ...editForm, payment_status: value })
                  }
                >
                  <SelectTrigger id="payment_status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {paymentStatuses.map((s) => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Input
                  id="description"
                  value={editForm.description}
                  onChange={(e) =>
                    setEditForm({ ...editForm, description: e.target.value })
                  }
                  placeholder="Optional description"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="taxes_amount_cents">Taxes Amount (cents)</Label>
                <Input
                  id="taxes_amount_cents"
                  type="number"
                  value={editForm.taxes_amount_cents}
                  onChange={(e) =>
                    setEditForm({ ...editForm, taxes_amount_cents: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="total_amount_cents">Total Amount (cents)</Label>
                <Input
                  id="total_amount_cents"
                  type="number"
                  value={editForm.total_amount_cents}
                  onChange={(e) =>
                    setEditForm({ ...editForm, total_amount_cents: e.target.value })
                  }
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditingFee(null)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? 'Saving...' : 'Update'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* View Details Dialog */}
      <Dialog open={!!viewingFee} onOpenChange={(open) => !open && setViewingFee(null)}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Fee Details</DialogTitle>
            <DialogDescription>
              Complete fee information
            </DialogDescription>
          </DialogHeader>
          {viewingFee && (
            <div className="grid gap-3 py-4 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">ID</span>
                <span className="font-mono text-xs">{viewingFee.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Fee Type</span>
                <span className="font-medium">{viewingFee.fee_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Payment Status</span>
                <span className="font-medium">{viewingFee.payment_status}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Amount</span>
                <span className="font-medium">{formatCents(parseInt(viewingFee.amount_cents))}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Tax</span>
                <span className="font-medium">{formatCents(parseInt(viewingFee.taxes_amount_cents))}</span>
              </div>
              <AppliedTaxesSection feeId={viewingFee.id} />
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total</span>
                <span className="font-medium">{formatCents(parseInt(viewingFee.total_amount_cents))}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Units</span>
                <span className="font-medium">{viewingFee.units}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Events Count</span>
                <span className="font-medium">{viewingFee.events_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Unit Amount</span>
                <span className="font-medium">{formatCents(parseInt(viewingFee.unit_amount_cents))}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Description</span>
                <span className="font-medium">{viewingFee.description || '—'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Metric Code</span>
                <span className="font-medium">{viewingFee.metric_code || '—'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground">Customer</span>
                <Link
                  to={`/admin/customers/${viewingFee.customer_id}`}
                  className="flex items-center gap-1 text-primary hover:underline"
                  onClick={() => setViewingFee(null)}
                >
                  {customerMap[viewingFee.customer_id] || viewingFee.customer_id.slice(0, 8)}
                  <ExternalLink className="h-3 w-3" />
                </Link>
              </div>
              {viewingFee.invoice_id && (
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Invoice</span>
                  <Link
                    to={`/admin/invoices/${viewingFee.invoice_id}`}
                    className="flex items-center gap-1 text-primary hover:underline"
                    onClick={() => setViewingFee(null)}
                  >
                    {invoiceMap[viewingFee.invoice_id] || viewingFee.invoice_id.slice(0, 8)}
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              )}
              {viewingFee.subscription_id && (
                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Subscription</span>
                  <Link
                    to={`/admin/subscriptions/${viewingFee.subscription_id}`}
                    className="flex items-center gap-1 text-primary hover:underline"
                    onClick={() => setViewingFee(null)}
                  >
                    {viewingFee.subscription_id.slice(0, 8)}...
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              )}
              {viewingFee.charge_id && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Charge ID</span>
                  <span className="font-mono text-xs">{viewingFee.charge_id}</span>
                </div>
              )}
              {viewingFee.commitment_id && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Commitment ID</span>
                  <span className="font-mono text-xs">{viewingFee.commitment_id}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground">Properties</span>
                <span className="font-mono text-xs">
                  {Object.keys(viewingFee.properties).length > 0
                    ? JSON.stringify(viewingFee.properties)
                    : '—'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span className="font-medium">{format(new Date(viewingFee.created_at), 'MMM d, yyyy HH:mm')}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Updated</span>
                <span className="font-medium">{format(new Date(viewingFee.updated_at), 'MMM d, yyyy HH:mm')}</span>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewingFee(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
