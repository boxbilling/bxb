import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Mail, Users, Clock, Globe } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
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
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { customersApi, ApiError } from '@/lib/api'
import { CustomerFormDialog } from '@/components/CustomerFormDialog'
import PageHeader from '@/components/PageHeader'
import { CustomerAvatar } from '@/components/CustomerAvatar'
import { CustomerHealthBadge } from '@/components/CustomerHealthBadge'
import { TablePagination } from '@/components/TablePagination'
import { SortableTableHead, useSortState } from '@/components/SortableTableHead'
import type { Customer, CustomerCreate, CustomerUpdate } from '@/types/billing'

const PAGE_SIZE = 20

export default function CustomersPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null)
  const [deleteCustomer, setDeleteCustomer] = useState<Customer | null>(null)
  const [currencyFilter, setCurrencyFilter] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const { sort, setSort, orderBy } = useSortState()

  // Fetch customers from API with pagination
  const { data, isLoading, error } = useQuery({
    queryKey: ['customers', page, pageSize, orderBy],
    queryFn: () => customersApi.listPaginated({ skip: (page - 1) * pageSize, limit: pageSize, order_by: orderBy }),
  })

  const customers = data?.data
  const totalCount = data?.totalCount ?? 0

  // Derive unique currencies from current page
  const uniqueCurrencies = [...new Set(customers?.map(c => c.currency) ?? [])]

  // Filter customers by search and currency (client-side, within current page)
  const filteredCustomers = customers?.filter((c) => {
    const matchesSearch = !search ||
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.email?.toLowerCase().includes(search.toLowerCase()) ||
      c.external_id.toLowerCase().includes(search.toLowerCase())
    const matchesCurrency = currencyFilter === 'all' || c.currency === currencyFilter
    return matchesSearch && matchesCurrency
  }) ?? []

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: CustomerCreate) => customersApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      setFormOpen(false)
      toast.success('Customer created successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to create customer'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CustomerUpdate }) =>
      customersApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      setEditingCustomer(null)
      setFormOpen(false)
      toast.success('Customer updated successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to update customer'
      toast.error(message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => customersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] })
      setDeleteCustomer(null)
      toast.success('Customer deleted successfully')
    },
    onError: (error) => {
      const message = error instanceof ApiError ? error.message : 'Failed to delete customer'
      toast.error(message)
    },
  })

  const handleSubmit = (data: CustomerCreate | CustomerUpdate) => {
    if (editingCustomer) {
      updateMutation.mutate({ id: editingCustomer.id, data })
    } else {
      createMutation.mutate(data as CustomerCreate)
    }
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingCustomer(null)
    }
    setFormOpen(open)
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">Failed to load customers. Please try again.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Customers"
        description="Manage your customers and their billing information"
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Customer
          </Button>
        }
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Customers</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{customers?.length ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Unique Currencies</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{uniqueCurrencies.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">With Email</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{customers?.filter(c => c.email).length ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recently Added</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{customers?.filter(c => { const d = new Date(c.created_at); const now = new Date(); return (now.getTime() - d.getTime()) < 30 * 24 * 60 * 60 * 1000 }).length ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-4">
        <div className="relative flex-1 max-w-none md:max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search customers..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={currencyFilter} onValueChange={setCurrencyFilter}>
          <SelectTrigger className="w-full md:w-40">
            <SelectValue placeholder="Currency" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All currencies</SelectItem>
            {uniqueCurrencies.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <SortableTableHead label="Customer" sortKey="name" sort={sort} onSort={setSort} />
              <SortableTableHead label="External ID" sortKey="external_id" sort={sort} onSort={setSort} />
              <SortableTableHead label="Email" sortKey="email" sort={sort} onSort={setSort} className="hidden md:table-cell" />
              <SortableTableHead label="Timezone" sortKey="timezone" sort={sort} onSort={setSort} className="hidden md:table-cell" />
              <SortableTableHead label="Currency" sortKey="currency" sort={sort} onSort={setSort} />
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              [...Array(5)].map((_, i) => (
                <TableRow key={i}>
                  <TableCell><Skeleton className="h-5 w-40" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-24" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-32" /></TableCell>
                  <TableCell className="hidden md:table-cell"><Skeleton className="h-5 w-28" /></TableCell>
                  <TableCell><Skeleton className="h-5 w-12" /></TableCell>
                </TableRow>
              ))
            ) : filteredCustomers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center">
                  No customers found
                </TableCell>
              </TableRow>
            ) : (
              filteredCustomers.map((customer) => (
                <TableRow
                  key={customer.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/admin/customers/${customer.id}`)}
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <CustomerAvatar name={customer.name} size="sm" />
                      {customer.name}
                      <CustomerHealthBadge customerId={customer.id} />
                    </div>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                      {customer.external_id}
                    </code>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {customer.email ? (
                      <div className="flex items-center gap-1 text-sm">
                        <Mail className="h-3 w-3 text-muted-foreground" />
                        {customer.email}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">&mdash;</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <span className="text-sm">{customer.timezone}</span>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{customer.currency}</Badge>
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

      {/* Create/Edit Dialog */}
      <CustomerFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        customer={editingCustomer}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteCustomer}
        onOpenChange={(open) => !open && setDeleteCustomer(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Customer</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &ldquo;{deleteCustomer?.name}&rdquo;? This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteCustomer && deleteMutation.mutate(deleteCustomer.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
