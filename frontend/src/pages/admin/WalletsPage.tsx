import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Plus,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  ArrowUpCircle,
  Eye,
  Coins,
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
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { TablePagination } from '@/components/TablePagination'
import { walletsApi, customersApi, ApiError } from '@/lib/api'
import type {
  Wallet,
  WalletCreate,
  WalletUpdate,
  WalletTopUp,
} from '@/types/billing'
import { formatCents } from '@/lib/utils'

const PAGE_SIZE = 20

function formatCredits(value: number | string): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  return num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 4 })
}


// --- Create/Edit Wallet Dialog ---
function WalletFormDialog({
  open,
  onOpenChange,
  wallet,
  customers,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  wallet?: Wallet | null
  customers: Array<{ id: string; name: string }>
  onSubmit: (data: WalletCreate | WalletUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<{
    customer_id: string
    name: string
    code: string
    rate_amount: string
    currency: string
    expiration_at: string
    priority: string
    initial_granted_credits: string
  }>({
    customer_id: wallet?.customer_id ?? '',
    name: wallet?.name ?? '',
    code: wallet?.code ?? '',
    rate_amount: wallet ? String(wallet.rate_amount) : '1',
    currency: wallet?.currency ?? 'USD',
    expiration_at: wallet?.expiration_at
      ? format(new Date(wallet.expiration_at), "yyyy-MM-dd'T'HH:mm")
      : '',
    priority: wallet ? String(wallet.priority) : '1',
    initial_granted_credits: '',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (wallet) {
      const update: WalletUpdate = {}
      if (formData.name) update.name = formData.name
      if (formData.expiration_at) update.expiration_at = new Date(formData.expiration_at).toISOString()
      if (formData.priority) update.priority = parseInt(formData.priority)
      onSubmit(update)
    } else {
      const create: WalletCreate = {
        customer_id: formData.customer_id,
        rate_amount: formData.rate_amount,
        currency: formData.currency,
        priority: parseInt(formData.priority),
      }
      if (formData.name) create.name = formData.name
      if (formData.code) create.code = formData.code
      if (formData.expiration_at)
        create.expiration_at = new Date(formData.expiration_at).toISOString()
      if (formData.initial_granted_credits)
        create.initial_granted_credits = formData.initial_granted_credits
      onSubmit(create)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {wallet ? 'Edit Wallet' : 'Create Wallet'}
            </DialogTitle>
            <DialogDescription>
              {wallet
                ? 'Update wallet settings'
                : 'Create a new prepaid credit wallet for a customer'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {!wallet && (
              <div className="space-y-2">
                <Label htmlFor="customer_id">Customer *</Label>
                <Select
                  value={formData.customer_id}
                  onValueChange={(value) =>
                    setFormData({ ...formData, customer_id: value })
                  }
                >
                  <SelectTrigger id="customer_id">
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
            )}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  placeholder="e.g. Prepaid Credits"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="code">Code</Label>
                <Input
                  id="code"
                  value={formData.code}
                  onChange={(e) =>
                    setFormData({ ...formData, code: e.target.value })
                  }
                  placeholder="e.g. prepaid-usd"
                  disabled={!!wallet}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="rate_amount">Rate Amount</Label>
                <Input
                  id="rate_amount"
                  type="number"
                  step="any"
                  min="0.0001"
                  value={formData.rate_amount}
                  onChange={(e) =>
                    setFormData({ ...formData, rate_amount: e.target.value })
                  }
                  disabled={!!wallet}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="currency">Currency</Label>
                <Input
                  id="currency"
                  value={formData.currency}
                  onChange={(e) =>
                    setFormData({ ...formData, currency: e.target.value })
                  }
                  placeholder="USD"
                  maxLength={3}
                  disabled={!!wallet}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="priority">Priority (1-50)</Label>
                <Input
                  id="priority"
                  type="number"
                  min="1"
                  max="50"
                  value={formData.priority}
                  onChange={(e) =>
                    setFormData({ ...formData, priority: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="expiration_at">Expiration</Label>
                <Input
                  id="expiration_at"
                  type="datetime-local"
                  value={formData.expiration_at}
                  onChange={(e) =>
                    setFormData({ ...formData, expiration_at: e.target.value })
                  }
                />
              </div>
            </div>
            {!wallet && (
              <div className="space-y-2">
                <Label htmlFor="initial_granted_credits">
                  Initial Granted Credits
                </Label>
                <Input
                  id="initial_granted_credits"
                  type="number"
                  step="any"
                  min="0"
                  value={formData.initial_granted_credits}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      initial_granted_credits: e.target.value,
                    })
                  }
                  placeholder="0"
                />
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
            <Button
              type="submit"
              disabled={isLoading || (!wallet && !formData.customer_id)}
            >
              {isLoading ? 'Saving...' : wallet ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- Top Up Dialog ---
function TopUpDialog({
  open,
  onOpenChange,
  wallet,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  wallet: Wallet | null
  onSubmit: (data: WalletTopUp) => void
  isLoading: boolean
}) {
  const [credits, setCredits] = useState('')
  const [source, setSource] = useState('manual')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({ credits, source })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Top Up Wallet</DialogTitle>
            <DialogDescription>
              Grant credits to {wallet?.name || wallet?.code || 'this wallet'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {wallet && (
              <div className="rounded-md bg-muted p-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Current Balance</span>
                  <span className="font-medium">
                    {formatCredits(wallet.credits_balance)} credits
                  </span>
                </div>
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="credits">Credits to Grant *</Label>
              <Input
                id="credits"
                type="number"
                step="any"
                min="0.0001"
                value={credits}
                onChange={(e) => setCredits(e.target.value)}
                placeholder="100"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="source">Source</Label>
              <Select value={source} onValueChange={setSource}>
                <SelectTrigger id="source">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="manual">Manual</SelectItem>
                  <SelectItem value="interval">Interval</SelectItem>
                  <SelectItem value="threshold">Threshold</SelectItem>
                </SelectContent>
              </Select>
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
            <Button type="submit" disabled={isLoading || !credits}>
              {isLoading ? 'Processing...' : 'Top Up'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function WalletsPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [formOpen, setFormOpen] = useState(false)
  const [editingWallet, setEditingWallet] = useState<Wallet | null>(null)
  const [topUpWallet, setTopUpWallet] = useState<Wallet | null>(null)
  const [terminateWallet, setTerminateWallet] = useState<Wallet | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(PAGE_SIZE)

  // Fetch wallets
  const {
    data: paginatedData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['wallets', page, pageSize],
    queryFn: () => walletsApi.listPaginated({ skip: (page - 1) * pageSize, limit: pageSize }),
  })

  const wallets = paginatedData?.data ?? []
  const totalCount = paginatedData?.totalCount ?? 0

  // Fetch customers for display and form
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  const getCustomerName = (customerId: string) => {
    const customer = customers.find((c) => c.id === customerId)
    return customer?.name || customerId.slice(0, 8)
  }

  // Filter wallets
  const filteredWallets = wallets.filter((w) => {
    const matchesSearch =
      !search ||
      (w.name?.toLowerCase().includes(search.toLowerCase()) ?? false) ||
      (w.code?.toLowerCase().includes(search.toLowerCase()) ?? false) ||
      getCustomerName(w.customer_id).toLowerCase().includes(search.toLowerCase())
    const matchesStatus =
      statusFilter === 'all' || w.status === statusFilter
    return matchesSearch && matchesStatus
  })

  // Stats
  const stats = {
    total: wallets.length,
    active: wallets.filter((w) => w.status === 'active').length,
    totalCredits: wallets
      .filter((w) => w.status === 'active')
      .reduce((sum, w) => sum + (typeof w.credits_balance === 'string' ? parseFloat(w.credits_balance) : w.credits_balance), 0),
    totalConsumed: wallets.reduce(
      (sum, w) => sum + (typeof w.consumed_credits === 'string' ? parseFloat(w.consumed_credits) : w.consumed_credits),
      0
    ),
  }

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: WalletCreate) => walletsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
      setFormOpen(false)
      toast.success('Wallet created successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to create wallet'
      toast.error(message)
    },
  })

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: WalletUpdate }) =>
      walletsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
      setEditingWallet(null)
      setFormOpen(false)
      toast.success('Wallet updated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to update wallet'
      toast.error(message)
    },
  })

  // Top-up mutation
  const topUpMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: WalletTopUp }) =>
      walletsApi.topUp(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
      queryClient.invalidateQueries({ queryKey: ['wallet-transactions'] })
      setTopUpWallet(null)
      toast.success('Wallet topped up successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError ? error.message : 'Failed to top up wallet'
      toast.error(message)
    },
  })

  // Terminate mutation
  const terminateMutation = useMutation({
    mutationFn: (id: string) => walletsApi.terminate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
      setTerminateWallet(null)
      toast.success('Wallet terminated successfully')
    },
    onError: (error) => {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Failed to terminate wallet'
      toast.error(message)
    },
  })

  const handleSubmit = (data: WalletCreate | WalletUpdate) => {
    if (editingWallet) {
      updateMutation.mutate({ id: editingWallet.id, data: data as WalletUpdate })
    } else {
      createMutation.mutate(data as WalletCreate)
    }
  }

  const handleEdit = (wallet: Wallet) => {
    setEditingWallet(wallet)
    setFormOpen(true)
  }

  const handleCloseForm = (open: boolean) => {
    if (!open) {
      setEditingWallet(null)
    }
    setFormOpen(open)
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load wallets. Please try again.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Wallets</h2>
          <p className="text-muted-foreground">
            Manage customer prepaid credit wallets
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Wallet
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Wallets
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Wallets
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {stats.active}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Credits Balance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCredits(stats.totalCredits)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Consumed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {formatCredits(stats.totalConsumed)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name, code, or customer..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select
          value={statusFilter}
          onValueChange={setStatusFilter}
        >
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="terminated">Terminated</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Wallet</TableHead>
              <TableHead>Customer</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Credits Balance</TableHead>
              <TableHead>Currency</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Expiration</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell>
                    <Skeleton className="h-5 w-32" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-28" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-16" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-20" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-12" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-8" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-5 w-24" />
                  </TableCell>
                  <TableCell>
                    <Skeleton className="h-8 w-8" />
                  </TableCell>
                </TableRow>
              ))
            ) : filteredWallets.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={8}
                  className="h-24 text-center text-muted-foreground"
                >
                  No wallets found
                </TableCell>
              </TableRow>
            ) : (
              filteredWallets.map((wallet) => (
                <TableRow key={wallet.id}>
                  <TableCell>
                    <Link
                      to={`/admin/wallets/${wallet.id}`}
                      className="block hover:underline"
                    >
                      <div className="font-medium">
                        {wallet.name || '(unnamed)'}
                      </div>
                      {wallet.code && (
                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                          {wallet.code}
                        </code>
                      )}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {getCustomerName(wallet.customer_id)}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        wallet.status === 'active' ? 'default' : 'secondary'
                      }
                    >
                      {wallet.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Coins className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="font-medium">
                        {formatCredits(wallet.credits_balance)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{wallet.currency}</Badge>
                  </TableCell>
                  <TableCell>{wallet.priority}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {wallet.expiration_at
                      ? format(
                          new Date(wallet.expiration_at),
                          'MMM d, yyyy'
                        )
                      : '—'}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem asChild>
                          <Link to={`/admin/wallets/${wallet.id}`}>
                            <Eye className="mr-2 h-4 w-4" />
                            View Details
                          </Link>
                        </DropdownMenuItem>
                        {wallet.status === 'active' && (
                          <>
                            <DropdownMenuItem
                              onClick={() => handleEdit(wallet)}
                            >
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => setTopUpWallet(wallet)}
                            >
                              <ArrowUpCircle className="mr-2 h-4 w-4" />
                              Top Up
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => setTerminateWallet(wallet)}
                              className="text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Terminate
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

      {/* Create/Edit Dialog */}
      <WalletFormDialog
        open={formOpen}
        onOpenChange={handleCloseForm}
        wallet={editingWallet}
        customers={customers.map((c) => ({ id: c.id, name: c.name }))}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Top Up Dialog */}
      <TopUpDialog
        open={!!topUpWallet}
        onOpenChange={(open) => !open && setTopUpWallet(null)}
        wallet={topUpWallet}
        onSubmit={(data) =>
          topUpWallet && topUpMutation.mutate({ id: topUpWallet.id, data })
        }
        isLoading={topUpMutation.isPending}
      />

      {/* Terminate Confirmation */}
      <AlertDialog
        open={!!terminateWallet}
        onOpenChange={(open) => !open && setTerminateWallet(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Terminate Wallet</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to terminate "
              {terminateWallet?.name || terminateWallet?.code || 'this wallet'}
              "? This will prevent any further credit consumption from this
              wallet.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                terminateWallet &&
                terminateMutation.mutate(terminateWallet.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {terminateMutation.isPending ? 'Terminating...' : 'Terminate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
