import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import {
  ArrowUpCircle,
  Pencil,
  Trash2,
  Coins,
  ArrowLeftRight,
  Clock,
  TrendingDown,
  Calendar,
  Activity,
  MoreHorizontal,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { toast } from 'sonner'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useIsMobile } from '@/components/ui/use-mobile'
import { AuditTrailTimeline } from '@/components/AuditTrailTimeline'
import { walletsApi, customersApi, ApiError } from '@/lib/api'
import type {
  Wallet,
  WalletUpdate,
  WalletTopUp,
  WalletTransaction,
} from '@/types/billing'
import { formatCents } from '@/lib/utils'

function formatCredits(value: number | string): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  return num.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  })
}


export default function WalletDetailPage() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()
  const [editOpen, setEditOpen] = useState(false)
  const [topUpOpen, setTopUpOpen] = useState(false)
  const [transferOpen, setTransferOpen] = useState(false)
  const [terminateOpen, setTerminateOpen] = useState(false)

  // Fetch wallet
  const {
    data: wallet,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['wallet', id],
    queryFn: () => walletsApi.get(id!),
    enabled: !!id,
  })

  // Fetch customer for name
  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list(),
  })

  const customerName =
    customers.find((c) => c.id === wallet?.customer_id)?.name ||
    wallet?.customer_id?.slice(0, 8) ||
    ''

  // Fetch transactions
  const { data: transactions = [], isLoading: txLoading } = useQuery({
    queryKey: ['wallet-transactions', id],
    queryFn: () => walletsApi.listTransactions(id!),
    enabled: !!id,
  })

  // Fetch balance timeline
  const { data: timeline } = useQuery({
    queryKey: ['wallet-timeline', id],
    queryFn: () => walletsApi.getBalanceTimeline(id!),
    enabled: !!id,
  })

  // Fetch depletion forecast
  const { data: forecast } = useQuery({
    queryKey: ['wallet-depletion', id],
    queryFn: () => walletsApi.getDepletionForecast(id!),
    enabled: !!id,
  })

  // Fetch other wallets for transfer
  const { data: allWallets = [] } = useQuery({
    queryKey: ['wallets'],
    queryFn: () => walletsApi.list(),
  })

  // Compute running balance for transactions
  const transactionsWithBalance = (() => {
    if (transactions.length === 0) return []
    // Transactions come newest first. Compute running balance from oldest to newest, then reverse.
    const reversed = [...transactions].reverse()
    let running = 0
    const result = reversed.map((tx: WalletTransaction) => {
      const amount =
        typeof tx.credit_amount === 'string'
          ? parseFloat(tx.credit_amount)
          : tx.credit_amount
      if (tx.transaction_type === 'inbound') {
        running += amount
      } else {
        running -= amount
      }
      return { ...tx, running_balance: running }
    })
    return result.reverse()
  })()

  // Edit mutation
  const editForm = useState<{ name: string; priority: string; expiration_at: string }>({
    name: '',
    priority: '1',
    expiration_at: '',
  })

  const updateMutation = useMutation({
    mutationFn: (data: WalletUpdate) => walletsApi.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallet', id] })
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
      setEditOpen(false)
      toast.success('Wallet updated successfully')
    },
    onError: (err) => {
      const message =
        err instanceof ApiError ? err.message : 'Failed to update wallet'
      toast.error(message)
    },
  })

  // Top up mutation
  const topUpMutation = useMutation({
    mutationFn: (data: WalletTopUp) => walletsApi.topUp(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallet', id] })
      queryClient.invalidateQueries({ queryKey: ['wallet-transactions', id] })
      queryClient.invalidateQueries({ queryKey: ['wallet-timeline', id] })
      queryClient.invalidateQueries({ queryKey: ['wallet-depletion', id] })
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
      setTopUpOpen(false)
      toast.success('Wallet topped up successfully')
    },
    onError: (err) => {
      const message =
        err instanceof ApiError ? err.message : 'Failed to top up wallet'
      toast.error(message)
    },
  })

  // Transfer mutation
  const transferMutation = useMutation({
    mutationFn: (data: { target_wallet_id: string; credits: string }) =>
      walletsApi.transfer({
        source_wallet_id: id!,
        target_wallet_id: data.target_wallet_id,
        credits: data.credits,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallet', id] })
      queryClient.invalidateQueries({ queryKey: ['wallet-transactions', id] })
      queryClient.invalidateQueries({ queryKey: ['wallet-timeline', id] })
      queryClient.invalidateQueries({ queryKey: ['wallet-depletion', id] })
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
      setTransferOpen(false)
      toast.success('Credits transferred successfully')
    },
    onError: (err) => {
      const message =
        err instanceof ApiError ? err.message : 'Failed to transfer credits'
      toast.error(message)
    },
  })

  // Terminate mutation
  const terminateMutation = useMutation({
    mutationFn: () => walletsApi.terminate(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallet', id] })
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
      setTerminateOpen(false)
      toast.success('Wallet terminated successfully')
    },
    onError: (err) => {
      const message =
        err instanceof ApiError ? err.message : 'Failed to terminate wallet'
      toast.error(message)
    },
  })

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-destructive">
          Failed to load wallet. Please try again.
        </p>
      </div>
    )
  }

  if (isLoading || !wallet) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const otherActiveWallets = allWallets.filter(
    (w) => w.id !== wallet.id && w.status === 'active'
  )

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/admin">Admin</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/admin/wallets">Wallets</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>
              {wallet.name || wallet.code || wallet.id.slice(0, 8)}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="flex items-center gap-3 flex-wrap">
          <Coins className="h-8 w-8 text-muted-foreground" />
          <div>
            <h2 className="text-2xl font-bold tracking-tight">
              {wallet.name || wallet.code || 'Unnamed Wallet'}
            </h2>
            <div className="flex items-center gap-2 text-muted-foreground flex-wrap">
              {wallet.code && (
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                  {wallet.code}
                </code>
              )}
              <span>
                Customer:{' '}
                <Link
                  to={`/admin/customers/${wallet.customer_id}`}
                  className="text-primary hover:underline"
                >
                  {customerName}
                </Link>
              </span>
            </div>
          </div>
          <Badge
            variant={wallet.status === 'active' ? 'default' : 'secondary'}
            className="ml-2"
          >
            {wallet.status}
          </Badge>
        </div>
        {wallet.status === 'active' && (
          isMobile ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="w-full">
                  <MoreHorizontal className="mr-2 h-4 w-4" />
                  Actions
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuItem
                  onClick={() => {
                    editForm[1]({
                      name: wallet.name || '',
                      priority: String(wallet.priority),
                      expiration_at: wallet.expiration_at
                        ? format(
                            new Date(wallet.expiration_at),
                            "yyyy-MM-dd'T'HH:mm"
                          )
                        : '',
                    })
                    setEditOpen(true)
                  }}
                >
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setTopUpOpen(true)}>
                  <ArrowUpCircle className="mr-2 h-4 w-4" />
                  Top Up
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setTransferOpen(true)}>
                  <ArrowLeftRight className="mr-2 h-4 w-4" />
                  Transfer
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant="destructive"
                  onClick={() => setTerminateOpen(true)}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Terminate
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  editForm[1]({
                    name: wallet.name || '',
                    priority: String(wallet.priority),
                    expiration_at: wallet.expiration_at
                      ? format(
                          new Date(wallet.expiration_at),
                          "yyyy-MM-dd'T'HH:mm"
                        )
                      : '',
                  })
                  setEditOpen(true)
                }}
              >
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setTopUpOpen(true)}
              >
                <ArrowUpCircle className="mr-2 h-4 w-4" />
                Top Up
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setTransferOpen(true)}
              >
                <ArrowLeftRight className="mr-2 h-4 w-4" />
                Transfer
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setTerminateOpen(true)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Terminate
              </Button>
            </div>
          )
        )}
      </div>

      {/* Depletion Forecast Card */}
      {forecast &&
        wallet.status === 'active' &&
        parseFloat(String(wallet.balance_cents)) > 0 && (
          <Card className="border-primary/20 bg-primary/5">
            <CardContent className="pt-6">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:gap-6">
                <div className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-primary" />
                  <span className="text-sm font-medium">
                    Depletion Forecast
                  </span>
                </div>
                <Separator orientation="vertical" className="hidden md:block h-8" />
                <Separator className="md:hidden" />
                {forecast.days_remaining !== null &&
                forecast.projected_depletion_date ? (
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-6">
                    <div>
                      <div className="text-2xl font-bold text-primary">
                        {forecast.days_remaining} days
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Projected depletion:{' '}
                        {format(
                          new Date(forecast.projected_depletion_date),
                          'MMM d, yyyy'
                        )}
                      </div>
                    </div>
                    <Separator orientation="vertical" className="hidden md:block h-8" />
                    <div>
                      <div className="text-sm font-medium">
                        {formatCents(
                          forecast.avg_daily_consumption,
                          wallet.currency
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Avg. daily consumption
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">
                    {parseFloat(String(forecast.avg_daily_consumption)) === 0
                      ? 'No consumption recorded yet'
                      : 'Balance depleted'}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

      {/* Info Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Credits Balance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCredits(wallet.credits_balance)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Balance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCents(wallet.balance_cents, wallet.currency)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Consumed Credits
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {formatCredits(wallet.consumed_credits)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Consumed Amount
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {formatCents(wallet.consumed_amount_cents, wallet.currency)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Wallet Details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Wallet Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Rate</p>
              <p className="font-medium">
                1 credit = {formatCredits(wallet.rate_amount)} cents{' '}
                <Badge variant="outline">{wallet.currency}</Badge>
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Priority</p>
              <p className="font-medium">{wallet.priority}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Expiration</p>
              <p className="font-medium">
                {wallet.expiration_at
                  ? format(
                      new Date(wallet.expiration_at),
                      'MMM d, yyyy HH:mm'
                    )
                  : 'Never'}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Created</p>
              <p className="font-medium">
                {format(new Date(wallet.created_at), 'MMM d, yyyy')}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="transactions">
        <TabsList className="overflow-x-auto">
          <TabsTrigger value="transactions">
            <Activity className="mr-2 h-4 w-4" />
            Transactions
          </TabsTrigger>
          <TabsTrigger value="timeline">
            <TrendingDown className="mr-2 h-4 w-4" />
            Balance Timeline
          </TabsTrigger>
          <TabsTrigger value="activity">
            <Calendar className="mr-2 h-4 w-4" />
            Activity
          </TabsTrigger>
        </TabsList>

        {/* Transactions Tab */}
        <TabsContent value="transactions" className="space-y-4">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Credits</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead className="hidden md:table-cell">Running Balance</TableHead>
                  <TableHead className="hidden md:table-cell">Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="hidden md:table-cell">Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {txLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 7 }).map((_, j) => (
                        <TableCell key={j}>
                          <Skeleton className="h-4 w-16" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : transactionsWithBalance.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={7}
                      className="h-24 text-center text-muted-foreground"
                    >
                      No transactions yet
                    </TableCell>
                  </TableRow>
                ) : (
                  transactionsWithBalance.map(
                    (tx: WalletTransaction & { running_balance: number }) => (
                      <TableRow key={tx.id}>
                        <TableCell>
                          <Badge
                            variant={
                              tx.transaction_type === 'inbound'
                                ? 'default'
                                : 'secondary'
                            }
                          >
                            {tx.transaction_type}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span
                            className={
                              tx.transaction_type === 'inbound'
                                ? 'text-green-600 font-medium'
                                : 'text-red-600 font-medium'
                            }
                          >
                            {tx.transaction_type === 'inbound' ? '+' : '-'}
                            {formatCredits(tx.amount)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span
                            className={
                              tx.transaction_type === 'inbound'
                                ? 'text-green-600'
                                : 'text-red-600'
                            }
                          >
                            {tx.transaction_type === 'inbound' ? '+' : '-'}
                            {formatCents(tx.credit_amount, wallet.currency)}
                          </span>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          <span className="font-mono text-sm">
                            {formatCents(
                              tx.running_balance * 100,
                              wallet.currency
                            )}
                          </span>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          <span className="text-sm capitalize">
                            {tx.source}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{tx.status}</Badge>
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-muted-foreground text-sm">
                          {format(
                            new Date(tx.created_at),
                            'MMM d, yyyy HH:mm'
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  )
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {/* Balance Timeline Tab */}
        <TabsContent value="timeline" className="space-y-4">
          {timeline && timeline.points.length > 0 ? (
            <div className="space-y-6">
              {/* Running balance area chart */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    Balance Over Time
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={timeline.points}>
                        <defs>
                          <linearGradient
                            id="balanceGradient"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="5%"
                              stopColor="var(--primary)"
                              stopOpacity={0.3}
                            />
                            <stop
                              offset="95%"
                              stopColor="var(--primary)"
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          className="stroke-muted"
                        />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 12 }}
                          className="fill-muted-foreground"
                        />
                        <YAxis
                          tick={{ fontSize: 12 }}
                          className="fill-muted-foreground"
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: 'var(--popover)',
                            borderColor: 'var(--border)',
                            borderRadius: '8px',
                          }}
                          formatter={(value: number) => [
                            formatCents(value, wallet.currency),
                            'Balance',
                          ]}
                        />
                        <Area
                          type="monotone"
                          dataKey="balance"
                          stroke="var(--primary)"
                          fill="url(#balanceGradient)"
                          strokeWidth={2}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* Inbound/Outbound bar chart */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    Credits In / Out
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={timeline.points}>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          className="stroke-muted"
                        />
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 12 }}
                          className="fill-muted-foreground"
                        />
                        <YAxis
                          tick={{ fontSize: 12 }}
                          className="fill-muted-foreground"
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: 'var(--popover)',
                            borderColor: 'var(--border)',
                            borderRadius: '8px',
                          }}
                          formatter={(value: number, name: string) => [
                            formatCents(value, wallet.currency),
                            name === 'inbound' ? 'Credits In' : 'Credits Out',
                          ]}
                        />
                        <Legend />
                        <Bar
                          dataKey="inbound"
                          fill="oklch(0.72 0.19 150)"
                          name="Credits In"
                          radius={[4, 4, 0, 0]}
                        />
                        <Bar
                          dataKey="outbound"
                          fill="oklch(0.70 0.19 25)"
                          name="Credits Out"
                          radius={[4, 4, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : (
            <Card>
              <CardContent className="flex items-center justify-center h-48 text-muted-foreground">
                No transaction history available for timeline
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Activity Tab */}
        <TabsContent value="activity">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Audit Trail</CardTitle>
            </CardHeader>
            <CardContent>
              <AuditTrailTimeline
                resourceType="wallet"
                resourceId={id!}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit Dialog */}
      <EditWalletDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        wallet={wallet}
        formState={editForm}
        onSubmit={(data) => updateMutation.mutate(data)}
        isLoading={updateMutation.isPending}
      />

      {/* Top Up Dialog */}
      <TopUpDialogInline
        open={topUpOpen}
        onOpenChange={setTopUpOpen}
        wallet={wallet}
        onSubmit={(data) => topUpMutation.mutate(data)}
        isLoading={topUpMutation.isPending}
      />

      {/* Transfer Dialog */}
      <TransferDialog
        open={transferOpen}
        onOpenChange={setTransferOpen}
        wallet={wallet}
        otherWallets={otherActiveWallets}
        customers={customers}
        onSubmit={(data) => transferMutation.mutate(data)}
        isLoading={transferMutation.isPending}
      />

      {/* Terminate Confirmation */}
      <AlertDialog open={terminateOpen} onOpenChange={setTerminateOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Terminate Wallet</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to terminate &ldquo;
              {wallet.name || wallet.code || 'this wallet'}
              &rdquo;? This will prevent any further credit consumption from
              this wallet.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => terminateMutation.mutate()}
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

// --- Edit Wallet Dialog ---
function EditWalletDialog({
  open,
  onOpenChange,
  wallet,
  formState,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  wallet: Wallet
  formState: [
    { name: string; priority: string; expiration_at: string },
    React.Dispatch<
      React.SetStateAction<{
        name: string
        priority: string
        expiration_at: string
      }>
    >,
  ]
  onSubmit: (data: WalletUpdate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = formState

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const update: WalletUpdate = {}
    if (formData.name) update.name = formData.name
    if (formData.expiration_at)
      update.expiration_at = new Date(formData.expiration_at).toISOString()
    if (formData.priority) update.priority = parseInt(formData.priority)
    onSubmit(update)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Edit Wallet</DialogTitle>
            <DialogDescription>
              Update wallet settings for{' '}
              {wallet.name || wallet.code || 'this wallet'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Name</Label>
              <Input
                id="edit-name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-priority">Priority (1-50)</Label>
              <Input
                id="edit-priority"
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
              <Label htmlFor="edit-expiration">Expiration</Label>
              <Input
                id="edit-expiration"
                type="datetime-local"
                value={formData.expiration_at}
                onChange={(e) =>
                  setFormData({ ...formData, expiration_at: e.target.value })
                }
              />
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
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Saving...' : 'Update'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// --- Top Up Dialog ---
function TopUpDialogInline({
  open,
  onOpenChange,
  wallet,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  wallet: Wallet
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
              Grant credits to {wallet.name || wallet.code || 'this wallet'}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="rounded-md bg-muted p-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Current Balance</span>
                <span className="font-medium">
                  {formatCredits(wallet.credits_balance)} credits
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="topup-credits">Credits to Grant *</Label>
              <Input
                id="topup-credits"
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
              <Label htmlFor="topup-source">Source</Label>
              <Select value={source} onValueChange={setSource}>
                <SelectTrigger id="topup-source">
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

// --- Transfer Dialog ---
function TransferDialog({
  open,
  onOpenChange,
  wallet,
  otherWallets,
  customers,
  onSubmit,
  isLoading,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  wallet: Wallet
  otherWallets: Wallet[]
  customers: Array<{ id: string; name: string }>
  onSubmit: (data: { target_wallet_id: string; credits: string }) => void
  isLoading: boolean
}) {
  const [targetId, setTargetId] = useState('')
  const [credits, setCredits] = useState('')

  const getCustomerName = (customerId: string) =>
    customers.find((c) => c.id === customerId)?.name || customerId.slice(0, 8)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({ target_wallet_id: targetId, credits })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Transfer Credits</DialogTitle>
            <DialogDescription>
              Transfer credits from{' '}
              {wallet.name || wallet.code || 'this wallet'} to another wallet
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="rounded-md bg-muted p-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">
                  Available Credits
                </span>
                <span className="font-medium">
                  {formatCredits(wallet.credits_balance)}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="transfer-target">Target Wallet *</Label>
              <Select value={targetId} onValueChange={setTargetId}>
                <SelectTrigger id="transfer-target">
                  <SelectValue placeholder="Select target wallet" />
                </SelectTrigger>
                <SelectContent>
                  {otherWallets.map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name || w.code || w.id.slice(0, 8)} (
                      {getCustomerName(w.customer_id)})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="transfer-credits">Credits to Transfer *</Label>
              <Input
                id="transfer-credits"
                type="number"
                step="any"
                min="0.0001"
                value={credits}
                onChange={(e) => setCredits(e.target.value)}
                placeholder="50"
                required
              />
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
              disabled={isLoading || !targetId || !credits}
            >
              {isLoading ? 'Transferring...' : 'Transfer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
