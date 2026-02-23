import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  Link,
  Calculator,
  Globe,
  ChevronDown,
  ChevronRight,
  Check,
  ChevronsUpDown,
  Tag,
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
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TablePagination } from '@/components/TablePagination'
import { SortableTableHead, useSortState } from '@/components/SortableTableHead'
import { cn } from '@/lib/utils'
import PageHeader from '@/components/PageHeader'
import { taxesApi, customersApi, invoicesApi, plansApi, ApiError } from '@/lib/api'
import type {
  Tax,
  TaxCreate,
  TaxUpdate,
  ApplyTaxRequest,
} from '@/lib/api'

function formatTaxRate(rate: string | number): string {
  const num = typeof rate === 'string' ? parseFloat(rate) : rate
  return `${(num * 100).toFixed(2)}%`
}

// --- Create/Edit Tax Dialog ---
function TaxFormDialog({
  open,
  onOpenChange,
  tax,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  tax?: Tax | null
  onSubmit: (data: TaxCreate | TaxUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<{
    code: string
    name: string
    rate: string
    description: string
    category: string
    applied_to_organization: boolean
  }>({
    code: tax?.code ?? '',
    name: tax?.name ?? '',
    rate: tax?.rate ? (parseFloat(tax.rate) * 100).toFixed(2) : '',
    description: tax?.description ?? '',
    category: tax?.category ?? '',
    applied_to_organization: tax?.applied_to_organization ?? false,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const rateDecimal = parseFloat(formData.rate) / 100
    if (tax) {
      const update: TaxUpdate = {}
      if (formData.name) update.name = formData.name
      if (formData.rate) update.rate = rateDecimal
      if (formData.description !== (tax.description ?? ''))
        update.description = formData.description || null
      if (formData.category !== (tax.category ?? ''))
        update.category = formData.category || null
      update.applied_to_organization = formData.applied_to_organization
      onSubmit(update)
    } else {
      const create: TaxCreate = {
        code: formData.code,
        name: formData.name,
        rate: rateDecimal,
        applied_to_organization: formData.applied_to_organization,
      }
      if (formData.description) create.description = formData.description
      if (formData.category) create.category = formData.category
      onSubmit(create)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {tax ? 'Edit Tax' : 'Create Tax'}
            </DialogTitle>
            <DialogDescription>
              {tax
                ? 'Update tax rate settings'
                : 'Define a new tax rate'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="code">Code *</Label>
                <Input
                  id="code"
                  value={formData.code}
                  onChange={(e) =>
                    setFormData({ ...formData, code: e.target.value })
                  }
                  placeholder="e.g. vat_standard"
                  disabled={!!tax}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="e.g. Standard VAT"
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="rate">Rate (%) *</Label>
                <Input
                  id="rate"
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={formData.rate}
                  onChange={(e) =>
                    setFormData({ ...formData, rate: e.target.value })
                  }
                  placeholder="e.g. 8.25"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="category">Category</Label>
                <Input
                  id="category"
                  value={formData.category}
                  onChange={(e) =>
                    setFormData({ ...formData, category: e.target.value })
                  }
                  placeholder="e.g. VAT, Sales Tax"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                placeholder="Optional description"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="applied_to_organization"
                checked={formData.applied_to_organization}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    applied_to_organization: e.target.checked,
                  })
                }
                className="h-4 w-4 rounded border-input"
              />
              <Label htmlFor="applied_to_organization">
                Apply as organization-wide default
              </Label>
            </div>
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
                isLoading || (!tax && (!formData.code || !formData.name || !formData.rate))
              }
            >
              {isLoading ? 'Saving...' : tax ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- Apply Tax to Entity Dialog ---
function ApplyTaxDialog({
  open,
  onOpenChange,
  tax,
  customers,
  invoices,
  plans,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  tax: Tax | null
  customers: Array<{ id: string; name: string }>
  invoices: Array<{ id: string; invoice_number: string }>
  plans: Array<{ id: string; name: string; code: string }>
  onSubmit: (data: ApplyTaxRequest) => void
  isLoading: boolean
}) {
  const [entityType, setEntityType] = useState<string>('customer')
  const [entityId, setEntityId] = useState('')
  const [comboboxOpen, setComboboxOpen] = useState(false)
  const [entitySearch, setEntitySearch] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!tax) return
    onSubmit({
      tax_code: tax.code,
      taxable_type: entityType,
      taxable_id: entityId,
    })
  }

  const entityOptions =
    entityType === 'customer'
      ? customers.map((c) => ({ id: c.id, label: c.name }))
      : entityType === 'invoice'
        ? invoices.map((i) => ({ id: i.id, label: i.invoice_number }))
        : plans.map((p) => ({ id: p.id, label: `${p.name} (${p.code})` }))

  const selectedLabel = entityOptions.find((e) => e.id === entityId)?.label

  const entityTypeLabel =
    entityType === 'customer' ? 'Customer' : entityType === 'invoice' ? 'Invoice' : 'Plan'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Apply Tax to Entity</DialogTitle>
            <DialogDescription>
              Apply &quot;{tax?.name}&quot; ({tax ? formatTaxRate(tax.rate) : ''}) to an entity
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {tax && (
              <div className="rounded-md bg-muted p-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Tax</span>
                  <span className="font-medium">{tax.code}</span>
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-muted-foreground">Rate</span>
                  <span className="font-medium">{formatTaxRate(tax.rate)}</span>
                </div>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="entity_type">Entity Type *</Label>
              <Select
                value={entityType}
                onValueChange={(value) => {
                  setEntityType(value)
                  setEntityId('')
                  setEntitySearch('')
                }}
              >
                <SelectTrigger id="entity_type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="customer">Customer</SelectItem>
                  <SelectItem value="invoice">Invoice</SelectItem>
                  <SelectItem value="plan">Plan</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{entityTypeLabel} *</Label>
              <Popover open={comboboxOpen} onOpenChange={setComboboxOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={comboboxOpen}
                    className="w-full justify-between font-normal"
                  >
                    {selectedLabel || `Select a ${entityType}...`}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[350px] p-0" align="start">
                  <Command>
                    <CommandInput
                      placeholder={`Search ${entityType}s...`}
                      value={entitySearch}
                      onValueChange={setEntitySearch}
                    />
                    <CommandList>
                      <CommandEmpty>No {entityType} found.</CommandEmpty>
                      <CommandGroup>
                        {entityOptions.map((option) => (
                          <CommandItem
                            key={option.id}
                            value={option.label}
                            onSelect={() => {
                              setEntityId(option.id)
                              setComboboxOpen(false)
                            }}
                          >
                            <Check
                              className={cn(
                                'mr-2 h-4 w-4',
                                entityId === option.id ? 'opacity-100' : 'opacity-0',
                              )}
                            />
                            {option.label}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !entityId}>
              {isLoading ? 'Applying...' : 'Apply'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- Applied Entities Expandable Row ---
function AppliedEntitiesRow({ tax }: { tax: Tax }) {
  const [expanded, setExpanded] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['taxes', tax.code, 'applied_entities'],
    queryFn: () => taxesApi.appliedEntities(tax.code),
    enabled: expanded,
  })

  return (
    <>
      <TableRow>
        <TableCell>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
            <code className="text-sm bg-muted px-1.5 py-0.5 rounded font-medium">
              {tax.code}
            </code>
          </div>
        </TableCell>
        <TableCell className="font-medium">{tax.name}</TableCell>
        <TableCell className="hidden md:table-cell">
          <div className="flex items-center gap-1">
            <Calculator className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-medium">
              {formatTaxRate(tax.rate)}
            </span>
          </div>
        </TableCell>
        <TableCell>
          {tax.category ? (
            <Badge variant="outline">
              <Tag className="mr-1 h-3 w-3" />
              {tax.category}
            </Badge>
          ) : (
            <span className="text-muted-foreground text-sm">—</span>
          )}
        </TableCell>
        <TableCell className="text-muted-foreground text-sm max-w-[200px] truncate">
          {tax.description || '—'}
        </TableCell>
        <TableCell className="hidden md:table-cell">
          {tax.applied_to_organization ? (
            <Badge variant="default" className="bg-blue-600">
              <Globe className="mr-1 h-3 w-3" />
              Yes
            </Badge>
          ) : (
            <Badge variant="secondary">No</Badge>
          )}
        </TableCell>
        <TableCell className="text-muted-foreground text-sm">
          {format(new Date(tax.created_at), 'MMM d, yyyy')}
        </TableCell>
        <TableCell>
          <TaxRowActions tax={tax} />
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow className="bg-muted/30 hover:bg-muted/30">
          <TableCell colSpan={8} className="py-3">
            <div className="pl-10">
              <p className="text-sm font-medium mb-2">Applied To</p>
              {isLoading ? (
                <div className="space-y-1">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-4 w-40" />
                </div>
              ) : !data?.entities.length ? (
                <p className="text-sm text-muted-foreground">
                  Not applied to any entities yet.
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {data.entities.map((entity, i) => (
                    <Badge key={i} variant="outline" className="text-xs">
                      <span className="capitalize">{entity.taxable_type}</span>
                      <span className="mx-1 text-muted-foreground">&middot;</span>
                      <code className="text-xs">{entity.taxable_id?.slice(0, 8)}...</code>
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

// --- Tax Row Actions Dropdown (extracted for use in AppliedEntitiesRow) ---
function TaxRowActions({ tax }: { tax: Tax }) {
  const page = useTaxPageContext()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => page.handleEdit(tax)}>
          <Pencil className="mr-2 h-4 w-4" />
          Edit
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => page.setApplyTax(tax)}>
          <Link className="mr-2 h-4 w-4" />
          Apply to Entity
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => page.setDeleteTax(tax)}
          className="text-destructive"
        >
          <Trash2 className="mr-2 h-4 w-4" />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// --- Page context to pass actions to extracted components ---
import { createContext, useContext } from 'react'

type TaxPageContextType = {
  handleEdit: (tax: Tax) => void
  setApplyTax: (tax: Tax) => void
  setDeleteTax: (tax: Tax) => void
}

const TaxPageContext = createContext<TaxPageContextType>(null!)

function useTaxPageContext() {
  return useContext(TaxPageContext)
}

const PAGE_SIZE = 20

export default function TaxesPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [orgFilter, setOrgFilter] = useState<string>('all')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const { sort, setSort, orderBy } = useSortState()
  const [formOpen, setFormOpen] = useState(false)
  const [editingTax, setEditingTax] = useState<Tax | null>(null)
  const [applyTax, setApplyTax] = useState<Tax | null>(null)
  const [deleteTax, setDeleteTax] = useState<Tax | null>(null)

  // Fetch taxes
  const {
    data,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['taxes', page, pageSize, orderBy],
    queryFn: () => taxesApi.listPaginated({ skip: (page - 1) * pageSize, limit: pageSize, order_by: orderBy }),
  })
  const taxes = data?.data ?? []
  const totalCount = data?.totalCount ?? 0

  // Fetch customers for apply dialog
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  // Fetch invoices for apply dialog
  const { data: invoices = [] } = useQuery({
    queryKey: ['invoices'],
    queryFn: () => invoicesApi.list(),
  })

  // Fetch plans for apply dialog
  const { data: plans = [] } = useQuery({
    queryKey: ['plans'],
    queryFn: () => plansApi.list(),
  })

  // Unique categories for filter
  const categories = [...new Set(
    taxes.map((t) => t.category).filter((c): c is string => !!c)
  )].sort()

  // Filter taxes
  const filteredTaxes = taxes.filter((t) => {
    const matchesSearch =
      !search ||
      t.code.toLowerCase().includes(search.toLowerCase()) ||
      t.name.toLowerCase().includes(search.toLowerCase())
    const matchesOrg =
      orgFilter === 'all' ||
      (orgFilter === 'org' && t.applied_to_organization) ||
      (orgFilter === 'specific' && !t.applied_to_organization)
    const matchesCategory =
      categoryFilter === 'all' ||
      (categoryFilter === 'none' && !t.category) ||
      t.category === categoryFilter
    return matchesSearch && matchesOrg && matchesCategory
  })

  // Stats
  const stats = {
    total: taxes.length,
    orgWide: taxes.filter((t) => t.applied_to_organization).length,
    avgRate:
      taxes.length > 0
        ? taxes.reduce(
            (sum, t) => sum + parseFloat(t.rate),
            0
          ) / taxes.length
        : 0,
    categories: categories.length,
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: TaxCreate) => taxesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taxes'] })
      setFormOpen(false)
      toast.success('Tax created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to create tax'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ code, data }: { code: string; data: TaxUpdate }) =>
      taxesApi.update(code, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taxes'] })
      setEditingTax(null)
      setFormOpen(false)
      toast.success('Tax updated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to update tax'
      toast.error(message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (code: string) => taxesApi.delete(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taxes'] })
      setDeleteTax(null)
      toast.success('Tax deleted successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to delete tax'
      toast.error(message)
    },
  })

  // Apply mutation
  const applyMutation = useMutation({
    mutationFn: (data: ApplyTaxRequest) => taxesApi.apply(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taxes'] })
      setApplyTax(null)
      toast.success('Tax applied successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to apply tax'
      toast.error(message)
    },
  })

  const handleSubmit = (data: TaxCreate | TaxUpdate) => {
    if (editingTax) {
      updateMutation.mutate({ code: editingTax.code, data: data as TaxUpdate })
    } else {
      createMutation.mutate(data as TaxCreate)
    }
  }

  const handleEdit = (tax: Tax) => {
    setEditingTax(tax)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingTax(null)
    }
    setFormOpen(open)
  }

  const pageContext: TaxPageContextType = {
    handleEdit,
    setApplyTax,
    setDeleteTax,
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load taxes. Please try again.
        </p>
      </div>
    )
  }

  return (
    <TaxPageContext.Provider value={pageContext}>
      <div className="space-y-6">
        {/* Header */}
        <PageHeader
          title="Taxes"
          description="Manage tax rates and apply them to entities"
          actions={
            <Button onClick={() => setFormOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Tax
            </Button>
          }
        />

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Taxes
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Organization-wide
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {stats.orgWide}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Average Rate
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatTaxRate(stats.avgRate)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Categories
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {stats.categories}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Filters */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center">
          <div className="relative flex-1 md:max-w-sm">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by code or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={orgFilter} onValueChange={setOrgFilter}>
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Scope" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Taxes</SelectItem>
              <SelectItem value="org">Organization-wide</SelectItem>
              <SelectItem value="specific">Entity-specific</SelectItem>
            </SelectContent>
          </Select>
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Categories</SelectItem>
              <SelectItem value="none">Uncategorized</SelectItem>
              {categories.map((cat) => (
                <SelectItem key={cat} value={cat}>{cat}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <SortableTableHead label="Code" sortKey="code" sort={sort} onSort={setSort} />
                <SortableTableHead label="Name" sortKey="name" sort={sort} onSort={setSort} />
                <SortableTableHead label="Rate" sortKey="rate" sort={sort} onSort={setSort} className="hidden md:table-cell" />
                <TableHead>Category</TableHead>
                <TableHead>Description</TableHead>
                <TableHead className="hidden md:table-cell">Org Default</TableHead>
                <SortableTableHead label="Created" sortKey="created_at" sort={sort} onSort={setSort} />
                <TableHead className="w-[50px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-28" /></TableCell>
                    <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-32" /></TableCell>
                    <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-12" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-20" /></TableCell>
                    <TableCell><Skeleton className="h-8 w-8" /></TableCell>
                  </TableRow>
                ))
              ) : filteredTaxes.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="h-24 text-center text-muted-foreground"
                  >
                    <Calculator className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                    No taxes found
                  </TableCell>
                </TableRow>
              ) : (
                filteredTaxes.map((tax) => (
                  <AppliedEntitiesRow key={tax.id} tax={tax} />
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

        {/* Create/Edit Dialog */}
        <TaxFormDialog
          open={formOpen}
          onOpenChange={handleCloseForm}
          tax={editingTax}
          onSubmit={handleSubmit}
          isLoading={createMutation.isPending || updateMutation.isPending}
        />

        {/* Apply Tax Dialog */}
        <ApplyTaxDialog
          open={!!applyTax}
          onOpenChange={(open) => !open && setApplyTax(null)}
          tax={applyTax}
          customers={customers.map((c) => ({ id: c.id, name: c.name }))}
          invoices={invoices.map((i) => ({ id: i.id, invoice_number: i.invoice_number }))}
          plans={plans.map((p) => ({ id: p.id, name: p.name, code: p.code }))}
          onSubmit={(data) => applyMutation.mutate(data)}
          isLoading={applyMutation.isPending}
        />

        {/* Delete Confirmation */}
        <AlertDialog
          open={!!deleteTax}
          onOpenChange={(open) => !open && setDeleteTax(null)}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Tax</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete &quot;{deleteTax?.name}&quot; (
                {deleteTax?.code})? This action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={() =>
                  deleteTax && deleteMutation.mutate(deleteTax.code)
                }
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </TaxPageContext.Provider>
  )
}
