import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  MoreHorizontal,
  Download,
  Eye,
  FileDown,
  Loader2,
} from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { dataExportsApi, customersApi, ApiError } from '@/lib/api'
import type { DataExport, DataExportEstimate, ExportType } from '@/types/billing'

const EXPORT_TYPES: ExportType[] = [
  'invoices',
  'customers',
  'subscriptions',
  'events',
  'fees',
  'credit_notes',
]

const EXPORT_TYPE_DESCRIPTIONS: Record<ExportType, string> = {
  invoices:
    'Invoice number, customer, status, amounts, currency, and dates (issued, due, paid). Filterable by status and customer.',
  customers:
    'Customer external ID, name, email, currency, timezone, and creation date.',
  subscriptions:
    'Subscription external ID, customer, plan, status, billing time, and lifecycle dates. Filterable by status and customer.',
  events:
    'Usage event transaction ID, customer, billable metric code, and timestamps. Filterable by customer and code.',
  fees:
    'Fee ID, invoice, type, amount, units, event count, payment status, and creation date. Filterable by fee type and invoice.',
  credit_notes:
    'Credit note number, invoice, customer, type, status, amount, currency, and dates. Filterable by status.',
}

type FilterFieldConfig = {
  key: string
  label: string
  type: 'select' | 'text' | 'customer'
  options?: { value: string; label: string }[]
  placeholder?: string
}

const INVOICE_STATUSES = [
  { value: 'draft', label: 'Draft' },
  { value: 'finalized', label: 'Finalized' },
  { value: 'paid', label: 'Paid' },
  { value: 'voided', label: 'Voided' },
]

const SUBSCRIPTION_STATUSES = [
  { value: 'pending', label: 'Pending' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'canceled', label: 'Canceled' },
  { value: 'terminated', label: 'Terminated' },
]

const CREDIT_NOTE_STATUSES = [
  { value: 'draft', label: 'Draft' },
  { value: 'finalized', label: 'Finalized' },
]

const FEE_TYPES = [
  { value: 'charge', label: 'Charge' },
  { value: 'subscription', label: 'Subscription' },
  { value: 'add_on', label: 'Add-on' },
  { value: 'credit', label: 'Credit' },
  { value: 'commitment', label: 'Commitment' },
]

const EXPORT_TYPE_FILTERS: Record<ExportType, FilterFieldConfig[]> = {
  invoices: [
    { key: 'status', label: 'Status', type: 'select', options: INVOICE_STATUSES },
    { key: 'customer_id', label: 'Customer', type: 'customer' },
  ],
  customers: [],
  subscriptions: [
    { key: 'status', label: 'Status', type: 'select', options: SUBSCRIPTION_STATUSES },
    { key: 'customer_id', label: 'Customer', type: 'customer' },
  ],
  events: [
    { key: 'external_customer_id', label: 'External Customer ID', type: 'text', placeholder: 'e.g. cust_123' },
    { key: 'code', label: 'Billable Metric Code', type: 'text', placeholder: 'e.g. api_calls' },
  ],
  fees: [
    { key: 'fee_type', label: 'Fee Type', type: 'select', options: FEE_TYPES },
    { key: 'invoice_id', label: 'Invoice ID', type: 'text', placeholder: 'UUID of the invoice' },
  ],
  credit_notes: [
    { key: 'status', label: 'Status', type: 'select', options: CREDIT_NOTE_STATUSES },
  ],
}

function capitalize(s: string): string {
  return s
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'pending':
      return <Badge variant="secondary">Pending</Badge>
    case 'processing':
      return (
        <Badge variant="outline" className="text-blue-600">
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          Processing
        </Badge>
      )
    case 'completed':
      return <Badge className="bg-green-600">Completed</Badge>
    case 'failed':
      return <Badge variant="destructive">Failed</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

// --- View Details Dialog ---
function ViewDetailsDialog({
  open,
  onOpenChange,
  exportItem,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  exportItem: DataExport | null
}) {
  if (!exportItem) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Export Details</DialogTitle>
          <DialogDescription>
            Details for export {exportItem.id}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 py-4 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">ID</span>
            <span className="font-mono">{exportItem.id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Organization ID</span>
            <span className="font-mono">{exportItem.organization_id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Export Type</span>
            <Badge>{capitalize(exportItem.export_type)}</Badge>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Status</span>
            <StatusBadge status={exportItem.status} />
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Record Count</span>
            <span>{exportItem.record_count ?? '—'}</span>
          </div>
          {exportItem.file_path && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">File Path</span>
              <span className="font-mono text-xs max-w-[250px] truncate">
                {exportItem.file_path}
              </span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-muted-foreground">Started At</span>
            <span>
              {exportItem.started_at
                ? format(new Date(exportItem.started_at), 'MMM d, yyyy HH:mm')
                : '—'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Completed At</span>
            <span>
              {exportItem.completed_at
                ? format(
                    new Date(exportItem.completed_at),
                    'MMM d, yyyy HH:mm'
                  )
                : '—'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Created At</span>
            <span>
              {format(new Date(exportItem.created_at), 'MMM d, yyyy HH:mm')}
            </span>
          </div>
          {exportItem.error_message && (
            <div className="space-y-1">
              <span className="text-muted-foreground">Error Message</span>
              <p className="text-sm text-destructive bg-destructive/10 rounded-md p-2">
                {exportItem.error_message}
              </p>
            </div>
          )}
          {exportItem.filters && (
            <div className="space-y-1">
              <span className="text-muted-foreground">Filters</span>
              <pre className="text-xs bg-muted rounded-md p-2 overflow-auto max-h-[200px]">
                {JSON.stringify(exportItem.filters, null, 2)}
              </pre>
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

// --- Structured Filter Fields ---
function ExportFilterFields({
  exportType,
  filterValues,
  onFilterChange,
}: {
  exportType: ExportType
  filterValues: Record<string, string>
  onFilterChange: (key: string, value: string) => void
}) {
  const fields = EXPORT_TYPE_FILTERS[exportType]

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
    enabled: fields.some((f) => f.type === 'customer'),
  })

  if (fields.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-2">
        No filters available for this export type.
      </p>
    )
  }

  return (
    <div className="grid gap-3">
      {fields.map((field) => (
        <div key={field.key} className="space-y-1.5">
          <Label htmlFor={`filter-${field.key}`}>{field.label}</Label>
          {field.type === 'select' && field.options && (
            <Select
              value={filterValues[field.key] || '__all__'}
              onValueChange={(v) => onFilterChange(field.key, v === '__all__' ? '' : v)}
            >
              <SelectTrigger id={`filter-${field.key}`}>
                <SelectValue placeholder={`All ${field.label.toLowerCase()}s`} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All</SelectItem>
                {field.options.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {field.type === 'customer' && (
            <Select
              value={filterValues[field.key] || '__all__'}
              onValueChange={(v) => onFilterChange(field.key, v === '__all__' ? '' : v)}
            >
              <SelectTrigger id={`filter-${field.key}`}>
                <SelectValue placeholder="All customers" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All</SelectItem>
                {customers.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name || c.external_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {field.type === 'text' && (
            <Input
              id={`filter-${field.key}`}
              value={filterValues[field.key] || ''}
              onChange={(e) => onFilterChange(field.key, e.target.value)}
              placeholder={field.placeholder}
            />
          )}
        </div>
      ))}
    </div>
  )
}

// --- New Export Dialog ---
function NewExportDialog({
  open,
  onOpenChange,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: { export_type: ExportType; filters?: Record<string, unknown> }) => void
  isLoading: boolean
}) {
  const [exportType, setExportType] = useState<ExportType | ''>('')
  const [filterValues, setFilterValues] = useState<Record<string, string>>({})

  const nonEmptyFilters = Object.fromEntries(
    Object.entries(filterValues).filter(([, v]) => v.trim() !== '')
  )
  const hasFilters = Object.keys(nonEmptyFilters).length > 0

  const { data: estimate, isFetching: isEstimating } = useQuery<DataExportEstimate>({
    queryKey: ['data-export-estimate', exportType, nonEmptyFilters],
    queryFn: () =>
      dataExportsApi.estimate({
        export_type: exportType as ExportType,
        filters: hasFilters ? nonEmptyFilters : undefined,
      }),
    enabled: !!exportType,
  })

  const handleFilterChange = (key: string, value: string) => {
    setFilterValues((prev) => ({ ...prev, [key]: value }))
  }

  const handleExportTypeChange = (value: ExportType) => {
    setExportType(value)
    setFilterValues({})
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!exportType) return

    onSubmit({
      export_type: exportType,
      filters: hasFilters ? nonEmptyFilters : undefined,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>New Export</DialogTitle>
            <DialogDescription>
              Create a new data export
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="export_type">Export Type *</Label>
              <Select
                value={exportType}
                onValueChange={(value) => handleExportTypeChange(value as ExportType)}
              >
                <SelectTrigger id="export_type">
                  <SelectValue placeholder="Select export type" />
                </SelectTrigger>
                <SelectContent>
                  {EXPORT_TYPES.map((type) => (
                    <SelectItem key={type} value={type}>
                      <div className="flex flex-col gap-0.5">
                        <span>{capitalize(type)}</span>
                        <span className="text-xs text-muted-foreground font-normal">
                          {EXPORT_TYPE_DESCRIPTIONS[type]}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {exportType && (
                <p className="text-xs text-muted-foreground">
                  {EXPORT_TYPE_DESCRIPTIONS[exportType]}
                </p>
              )}
            </div>
            {exportType && (
              <div className="space-y-2">
                <Label>Filters</Label>
                <ExportFilterFields
                  exportType={exportType}
                  filterValues={filterValues}
                  onFilterChange={handleFilterChange}
                />
              </div>
            )}
            {exportType && (
              <div className="rounded-md border bg-muted/50 p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Estimated records</span>
                  <span className="font-medium">
                    {isEstimating ? (
                      <Loader2 className="h-4 w-4 animate-spin inline" />
                    ) : estimate ? (
                      estimate.record_count.toLocaleString()
                    ) : (
                      '—'
                    )}
                  </span>
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
            <Button type="submit" disabled={isLoading || !exportType}>
              {isLoading ? 'Creating...' : 'Create Export'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function DataExportsPage() {
  const queryClient = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [viewExport, setViewExport] = useState<DataExport | null>(null)

  // Fetch exports with auto-refresh when exports are in progress
  const {
    data: allExports = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ['data-exports'],
    queryFn: () => dataExportsApi.list(),
    refetchInterval: (query) => {
      const data = query.state.data
      const hasInProgress =
        data?.some(
          (e) => e.status === 'pending' || e.status === 'processing'
        ) ?? false
      return hasInProgress ? 5000 : false
    },
  })

  // Stats
  const stats = {
    total: allExports.length,
    completed: allExports.filter((e) => e.status === 'completed').length,
    inProgress: allExports.filter(
      (e) => e.status === 'processing' || e.status === 'pending'
    ).length,
    totalRecords: allExports
      .filter((e) => e.record_count != null)
      .reduce((sum, e) => sum + (e.record_count ?? 0), 0),
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: {
      export_type: ExportType
      filters?: Record<string, unknown>
    }) => dataExportsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['data-exports'] })
      setCreateOpen(false)
      toast.success('Export created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to create export'
      toast.error(message)
    },
  })

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load exports. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Data Exports</h2>
          <p className="text-muted-foreground">
            Export your billing data
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Export
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Exports
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Completed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats.completed}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              In Progress
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {stats.inProgress}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Records
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.totalRecords.toLocaleString()}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Export Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Record Count</TableHead>
              <TableHead>Started At</TableHead>
              <TableHead>Completed At</TableHead>
              <TableHead>Error</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-5 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-20" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-8 w-8" />
                  </TableCell>
                </TableRow>
              ))
            ) : allExports.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="h-24 text-center text-muted-foreground"
                >
                  <FileDown className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  <p>No exports yet</p>
                  <p className="text-sm">Create your first data export</p>
                </TableCell>
              </TableRow>
            ) : (
              allExports.map((exportItem) => (
                <TableRow key={exportItem.id}>
                  <TableCell>
                    <Badge variant="secondary">
                      {capitalize(exportItem.export_type)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={exportItem.status} />
                  </TableCell>
                  <TableCell>
                    {exportItem.record_count != null
                      ? exportItem.record_count
                      : '—'}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {exportItem.started_at
                      ? format(
                          new Date(exportItem.started_at),
                          'MMM d, yyyy'
                        )
                      : '—'}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {exportItem.completed_at
                      ? format(
                          new Date(exportItem.completed_at),
                          'MMM d, yyyy'
                        )
                      : '—'}
                  </TableCell>
                  <TableCell>
                    {exportItem.error_message ? (
                      <span className="text-destructive text-sm max-w-[150px] truncate block">
                        {exportItem.error_message}
                      </span>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {exportItem.status === 'completed' && (
                          <DropdownMenuItem
                            onClick={() =>
                              window.open(
                                dataExportsApi.downloadUrl(exportItem.id),
                                '_blank'
                              )
                            }
                          >
                            <Download className="mr-2 h-4 w-4" />
                            Download
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem
                          onClick={() => setViewExport(exportItem)}
                        >
                          <Eye className="mr-2 h-4 w-4" />
                          View Details
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* New Export Dialog */}
      <NewExportDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
      />

      {/* View Details Dialog */}
      <ViewDetailsDialog
        open={!!viewExport}
        onOpenChange={(open) => !open && setViewExport(null)}
        exportItem={viewExport}
      />
    </div>
  )
}
