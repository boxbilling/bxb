import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Search, Landmark, Star, Trash2, Users, MoreHorizontal } from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'
import { Link } from 'react-router-dom'

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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { TablePagination } from '@/components/TablePagination'
import { CardBrandIcon } from '@/components/CardBrandIcon'
import { PaymentMethodFormDialog } from '@/components/PaymentMethodFormDialog'
import { customersApi, paymentMethodsApi, ApiError } from '@/lib/api'
import type { PaymentMethod, PaymentMethodCreate } from '@/types/billing'

const providerLabels: Record<string, string> = {
  stripe: 'Stripe',
  gocardless: 'GoCardless',
  adyen: 'Adyen',
}

const providerVariants: Record<string, 'default' | 'secondary' | 'outline'> = {
  stripe: 'default',
  gocardless: 'secondary',
  adyen: 'outline',
}

type PaymentMethodDetails = {
  last4?: string
  brand?: string
  exp_month?: number
  exp_year?: number
} | null

function getDetails(method: PaymentMethod): PaymentMethodDetails {
  return method.details as PaymentMethodDetails
}

function formatDetails(method: PaymentMethod): string {
  const details = getDetails(method)
  if (!details) return method.type
  if (details.brand && details.last4) {
    const parts = [`${details.brand} ending in ${details.last4}`]
    if (details.exp_month && details.exp_year) {
      parts.push(`exp ${String(details.exp_month).padStart(2, '0')}/${String(details.exp_year).slice(-2)}`)
    }
    return parts.join(', ')
  }
  if (details.last4) return `**** ${details.last4}`
  return method.type
}

const PAGE_SIZE = 20

export default function PaymentMethodsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [customerFilter, setCustomerFilter] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)
  const [groupByCustomer, setGroupByCustomer] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [deleteMethod, setDeleteMethod] = useState<PaymentMethod | null>(null)
  const [setDefaultMethod, setSetDefaultMethod] = useState<PaymentMethod | null>(null)

  // Fetch payment methods
  const { data, isLoading } = useQuery({
    queryKey: ['payment-methods', customerFilter, page, pageSize],
    queryFn: () =>
      paymentMethodsApi.listPaginated({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        ...(customerFilter !== 'all' ? { customer_id: customerFilter } : {}),
      }),
  })
  const paymentMethods = data?.data ?? []
  const totalCount = data?.totalCount ?? 0

  // Fetch customers for display and filtering
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  const customerMap = new Map(customers.map((c) => [c.id, c]))

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: PaymentMethodCreate) => paymentMethodsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] })
      setFormOpen(false)
      toast.success('Payment method created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to create payment method'
      toast.error(message)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => paymentMethodsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] })
      setDeleteMethod(null)
      toast.success('Payment method deleted successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to delete payment method'
      toast.error(message)
    },
  })

  // Set default mutation
  const setDefaultMutation = useMutation({
    mutationFn: (id: string) => paymentMethodsApi.setDefault(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] })
      setSetDefaultMethod(null)
      toast.success('Default payment method updated')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to set default payment method'
      toast.error(message)
    },
  })

  // Filter by search
  const filteredMethods = paymentMethods.filter((pm) => {
    if (!search) return true
    const customer = customerMap.get(pm.customer_id)
    const customerName = customer?.name?.toLowerCase() ?? ''
    const details = formatDetails(pm).toLowerCase()
    const searchLower = search.toLowerCase()
    return customerName.includes(searchLower) || details.includes(searchLower)
  })

  // Group by customer
  const groupedMethods = groupByCustomer
    ? Array.from(
        filteredMethods.reduce((groups, pm) => {
          const key = pm.customer_id
          if (!groups.has(key)) groups.set(key, [])
          groups.get(key)!.push(pm)
          return groups
        }, new Map<string, PaymentMethod[]>())
      ).sort(([aId], [bId]) => {
        const aName = customerMap.get(aId)?.name ?? ''
        const bName = customerMap.get(bId)?.name ?? ''
        return aName.localeCompare(bName)
      })
    : null

  function renderMethodRow(pm: PaymentMethod, showCustomer: boolean) {
    const customer = customerMap.get(pm.customer_id)
    const details = getDetails(pm)
    const brand = details?.brand
    const last4 = details?.last4
    const expMonth = details?.exp_month
    const expYear = details?.exp_year

    return (
      <TableRow key={pm.id}>
        {showCustomer && (
          <TableCell className="font-medium">
            <Link
              to={`/admin/customers/${pm.customer_id}`}
              className="text-blue-600 hover:underline"
            >
              {customer?.name ?? pm.customer_id.slice(0, 8)}
            </Link>
          </TableCell>
        )}
        <TableCell>
          <div className="flex items-center gap-2">
            {pm.type === 'card' && brand ? (
              <CardBrandIcon brand={brand} size={24} />
            ) : pm.type === 'card' ? (
              <CardBrandIcon brand="generic" size={24} />
            ) : (
              <Landmark className="h-5 w-5 text-muted-foreground" />
            )}
            <span className="text-sm text-muted-foreground">
              {pm.type === 'bank_account'
                ? 'Bank Account'
                : pm.type === 'direct_debit'
                  ? 'Direct Debit'
                  : 'Card'}
            </span>
          </div>
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-2">
            {last4 ? (
              <div>
                <span className="font-mono text-base font-semibold tracking-wider">
                  {'•••• •••• •••• '}
                  {last4}
                </span>
                {expMonth && expYear && (
                  <span className="ml-3 text-sm text-muted-foreground">
                    {String(expMonth).padStart(2, '0')}/{String(expYear).slice(-2)}
                  </span>
                )}
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">
                {pm.type === 'bank_account' ? 'Bank account' : pm.type === 'direct_debit' ? 'Direct debit' : 'No card details'}
              </span>
            )}
          </div>
        </TableCell>
        <TableCell>
          <Badge variant={providerVariants[pm.provider] ?? 'outline'}>
            {providerLabels[pm.provider] ?? pm.provider}
          </Badge>
        </TableCell>
        <TableCell>
          {pm.is_default && (
            <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
          )}
        </TableCell>
        <TableCell className="text-muted-foreground">
          {format(new Date(pm.created_at), 'MMM d, yyyy')}
        </TableCell>
        <TableCell>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {!pm.is_default && (
                <DropdownMenuItem onClick={() => setSetDefaultMethod(pm)}>
                  <Star className="mr-2 h-4 w-4" />
                  Set as Default
                </DropdownMenuItem>
              )}
              {!pm.is_default && <DropdownMenuSeparator />}
              <DropdownMenuItem
                variant="destructive"
                disabled={pm.is_default}
                onClick={() => setDeleteMethod(pm)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </TableCell>
      </TableRow>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Payment Methods</h1>
          <p className="text-muted-foreground">
            Manage customer payment methods
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Payment Method
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search payment methods..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={customerFilter} onValueChange={(v) => { setCustomerFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Filter by customer" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Customers</SelectItem>
            {customers.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant={groupByCustomer ? 'default' : 'outline'}
          size="sm"
          onClick={() => setGroupByCustomer(!groupByCustomer)}
          title="Group by customer"
        >
          <Users className="mr-2 h-4 w-4" />
          Group
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {!groupByCustomer && <TableHead>Customer</TableHead>}
              <TableHead>Type</TableHead>
              <TableHead>Card Number</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Default</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {!groupByCustomer && <TableCell><Skeleton className="h-4 w-24" /></TableCell>}
                  <TableCell><Skeleton className="h-6 w-20" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-8" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                </TableRow>
              ))
            ) : filteredMethods.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={groupByCustomer ? 6 : 7}
                  className="h-24 text-center text-muted-foreground"
                >
                  No payment methods found
                </TableCell>
              </TableRow>
            ) : groupByCustomer && groupedMethods ? (
              groupedMethods.map(([customerId, methods]) => {
                const customer = customerMap.get(customerId)
                return [
                  <TableRow key={`group-${customerId}`} className="bg-muted/50">
                    <TableCell colSpan={6} className="font-semibold py-2">
                      <Link
                        to={`/admin/customers/${customerId}`}
                        className="text-blue-600 hover:underline"
                      >
                        {customer?.name ?? customerId.slice(0, 8)}
                      </Link>
                      <span className="ml-2 text-xs text-muted-foreground font-normal">
                        {methods.length} payment method{methods.length !== 1 ? 's' : ''}
                      </span>
                    </TableCell>
                  </TableRow>,
                  ...methods.map((pm) => renderMethodRow(pm, false)),
                ]
              })
            ) : (
              filteredMethods.map((pm) => renderMethodRow(pm, true))
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

      {/* Add Payment Method Dialog */}
      <PaymentMethodFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
        customers={customers.map((c) => ({ id: c.id, name: c.name }))}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteMethod}
        onOpenChange={(open) => !open && setDeleteMethod(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Payment Method</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this payment method? This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteMethod && deleteMutation.mutate(deleteMethod.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Set Default Confirmation */}
      <AlertDialog
        open={!!setDefaultMethod}
        onOpenChange={(open) => !open && setSetDefaultMethod(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Set as Default</AlertDialogTitle>
            <AlertDialogDescription>
              Set this payment method as the default for{' '}
              {customerMap.get(setDefaultMethod?.customer_id ?? '')?.name ??
                'this customer'}
              ? The current default will be unset.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                setDefaultMethod &&
                setDefaultMutation.mutate(setDefaultMethod.id)
              }
            >
              {setDefaultMutation.isPending ? 'Updating...' : 'Set Default'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
