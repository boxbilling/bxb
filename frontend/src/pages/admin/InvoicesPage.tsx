import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Download, Eye, FileText } from 'lucide-react'
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
import type { Invoice, InvoiceStatus, Customer } from '@/types/billing'

// Mock customers matching the new schema (for invoice display only - invoices not in backend yet)
const mockCustomers: Customer[] = [
  { 
    id: '1', 
    external_id: 'cust_001', 
    name: 'Acme Corporation', 
    email: 'billing@acme.com', 
    currency: 'USD', 
    timezone: 'America/Los_Angeles', 
    billing_metadata: {}, 
    created_at: '2024-01-01T00:00:00Z', 
    updated_at: '2024-01-01T00:00:00Z' 
  },
  { 
    id: '2', 
    external_id: 'cust_002', 
    name: 'TechStart Inc', 
    email: 'accounts@techstart.io', 
    currency: 'USD', 
    timezone: 'America/New_York', 
    billing_metadata: {}, 
    created_at: '2024-01-01T00:00:00Z', 
    updated_at: '2024-01-01T00:00:00Z' 
  },
]

// Mock invoices - Invoice API not implemented in backend yet
const mockInvoices: Invoice[] = [
  {
    id: '1',
    number: 'INV-2024-0042',
    customer_id: '1',
    customer: mockCustomers[0],
    subscription_id: '1',
    status: 'finalized',
    issuing_date: '2024-02-01T00:00:00Z',
    payment_due_date: '2024-02-15T00:00:00Z',
    amount_cents: 9900,
    amount_currency: 'USD',
    taxes_amount_cents: 792,
    total_amount_cents: 10692,
    line_items: [
      { id: 'li1', description: 'Professional Plan - February 2024', amount_cents: 9900, quantity: 1, unit_amount_cents: 9900 },
    ],
    created_at: '2024-02-01T00:00:00Z',
    updated_at: '2024-02-01T00:00:00Z',
  },
  {
    id: '2',
    number: 'INV-2024-0041',
    customer_id: '2',
    customer: mockCustomers[1],
    subscription_id: '2',
    status: 'paid',
    issuing_date: '2024-01-15T00:00:00Z',
    payment_due_date: '2024-01-29T00:00:00Z',
    amount_cents: 2900,
    amount_currency: 'USD',
    taxes_amount_cents: 232,
    total_amount_cents: 3132,
    line_items: [
      { id: 'li2', description: 'Starter Plan - January 2024', amount_cents: 2900, quantity: 1, unit_amount_cents: 2900 },
    ],
    created_at: '2024-01-15T00:00:00Z',
    updated_at: '2024-01-29T10:00:00Z',
  },
]

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}

function StatusBadge({ status }: { status: InvoiceStatus }) {
  const variants: Record<InvoiceStatus, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string; className?: string }> = {
    draft: { variant: 'secondary', label: 'Draft' },
    finalized: { variant: 'outline', label: 'Finalized', className: 'border-orange-500 text-orange-600' },
    paid: { variant: 'default', label: 'Paid', className: 'bg-green-600' },
    voided: { variant: 'destructive', label: 'Voided' },
  }

  const config = variants[status]
  return (
    <Badge variant={config.variant} className={config.className}>
      {config.label}
    </Badge>
  )
}

function InvoiceDetailDialog({
  invoice,
  open,
  onOpenChange,
}: {
  invoice: Invoice | null
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  if (!invoice) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <span>Invoice {invoice.number}</span>
            <StatusBadge status={invoice.status} />
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Header Info */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Customer</p>
              <p className="font-medium">{invoice.customer?.name}</p>
              <p className="text-muted-foreground">{invoice.customer?.email}</p>
            </div>
            <div className="text-right">
              <p className="text-muted-foreground">Issue Date</p>
              <p className="font-medium">
                {format(new Date(invoice.issuing_date), 'MMM d, yyyy')}
              </p>
              <p className="text-muted-foreground mt-2">Due Date</p>
              <p className="font-medium">
                {format(new Date(invoice.payment_due_date), 'MMM d, yyyy')}
              </p>
            </div>
          </div>

          <Separator />

          {/* Line Items */}
          <div>
            <h4 className="font-medium mb-3">Line Items</h4>
            <div className="space-y-2">
              {invoice.line_items.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between py-2 border-b last:border-0"
                >
                  <div>
                    <p>{item.description}</p>
                    {item.quantity > 1 && (
                      <p className="text-sm text-muted-foreground">
                        {item.quantity} × {formatCurrency(item.unit_amount_cents, invoice.amount_currency)}
                      </p>
                    )}
                  </div>
                  <p className="font-medium">
                    {formatCurrency(item.amount_cents, invoice.amount_currency)}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          {/* Totals */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Subtotal</span>
              <span>{formatCurrency(invoice.amount_cents, invoice.amount_currency)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span>Tax</span>
              <span>{formatCurrency(invoice.taxes_amount_cents, invoice.amount_currency)}</span>
            </div>
            <Separator />
            <div className="flex justify-between font-medium text-lg">
              <span>Total</span>
              <span>{formatCurrency(invoice.total_amount_cents, invoice.amount_currency)}</span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1">
              <Download className="mr-2 h-4 w-4" />
              Download PDF
            </Button>
            {invoice.status === 'draft' && (
              <Button className="flex-1">Finalize Invoice</Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function InvoicesPage() {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null)

  // Fetch invoices - using mock data until backend implements invoices
  const { data, isLoading } = useQuery({
    queryKey: ['invoices', { search, statusFilter }],
    queryFn: async () => {
      await new Promise((r) => setTimeout(r, 300))
      let filtered = mockInvoices
      if (statusFilter !== 'all') {
        filtered = filtered.filter((i) => i.status === statusFilter)
      }
      if (search) {
        filtered = filtered.filter(
          (i) =>
            i.customer?.name.toLowerCase().includes(search.toLowerCase()) ||
            i.number.toLowerCase().includes(search.toLowerCase())
        )
      }
      return filtered
    },
  })

  // Calculate totals
  const totals = (data ?? []).reduce(
    (acc, inv) => {
      if (inv.status === 'paid') {
        acc.paid += inv.total_amount_cents
      } else if (inv.status === 'finalized') {
        acc.outstanding += inv.total_amount_cents
      } else if (inv.status === 'draft') {
        acc.draft += inv.total_amount_cents
      }
      return acc
    },
    { paid: 0, outstanding: 0, draft: 0 }
  )

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Invoices</h2>
        <p className="text-muted-foreground">
          View and manage customer invoices
        </p>
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
              <TableHead>Customer</TableHead>
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
                  <TableCell><Skeleton className="h-5 w-40" /></TableCell>
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
                    <code className="text-sm font-medium">{invoice.number}</code>
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">{invoice.customer?.name}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={invoice.status} />
                  </TableCell>
                  <TableCell>
                    {format(new Date(invoice.issuing_date), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell>
                    {format(new Date(invoice.payment_due_date), 'MMM d, yyyy')}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {formatCurrency(invoice.total_amount_cents, invoice.amount_currency)}
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
      />
    </div>
  )
}
