import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Wallet, ArrowUpCircle, Loader2 } from 'lucide-react'
import { format } from 'date-fns'
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

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
import { portalApi, ApiError } from '@/lib/api'
import { formatCents } from '@/lib/utils'
import { usePortalToken } from '@/layouts/PortalLayout'
import { useIsMobile } from '@/hooks/use-mobile'
import type { WalletTransaction } from '@/types/billing'

function formatCredits(value: number | string): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  return num.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  })
}

export default function PortalWalletPage() {
  const token = usePortalToken()
  const queryClient = useQueryClient()
  const [topUpOpen, setTopUpOpen] = useState(false)
  const [topUpCredits, setTopUpCredits] = useState('')

  // Fetch wallets (returns list, we use the first active one)
  const { data: wallets = [], isLoading } = useQuery({
    queryKey: ['portal-wallets', token],
    queryFn: () => portalApi.getWallets(token),
    enabled: !!token,
  })

  const wallet = wallets.length > 0 ? wallets[0] : null

  // Fetch transactions for the wallet
  const { data: transactions = [], isLoading: txLoading } = useQuery({
    queryKey: ['portal-wallet-transactions', token, wallet?.id],
    queryFn: () => portalApi.getWalletTransactions(token, wallet!.id),
    enabled: !!token && !!wallet,
  })

  // Fetch balance timeline for the wallet
  const { data: timeline } = useQuery({
    queryKey: ['portal-wallet-timeline', token, wallet?.id],
    queryFn: () => portalApi.getWalletBalanceTimeline(token, wallet!.id),
    enabled: !!token && !!wallet,
  })

  // Top-up mutation
  const topUpMutation = useMutation({
    mutationFn: (credits: number) => portalApi.topUpWallet(token, wallet!.id, credits),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['portal-wallets', token] })
      queryClient.invalidateQueries({ queryKey: ['portal-wallet-transactions', token, wallet?.id] })
      queryClient.invalidateQueries({ queryKey: ['portal-wallet-timeline', token, wallet?.id] })
      setTopUpOpen(false)
      setTopUpCredits('')
      toast.success(`Added ${formatCredits(data.credits_added)} credits to your wallet`)
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.message : 'Failed to top up wallet'
      toast.error(message)
    },
  })

  // Compute running balance for transactions
  const transactionsWithBalance = (() => {
    if (transactions.length === 0) return []
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

  // Timeline chart data
  const timelineChartData = timeline?.points?.map((p) => ({
    date: p.date,
    balance: Number(p.balance),
    inbound: Number(p.inbound),
    outbound: Number(p.outbound),
  })) || []

  const isMobile = useIsMobile()

  return (
    <div className="space-y-4 md:space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl md:text-3xl font-bold">Wallet</h1>
          <p className="text-sm md:text-base text-muted-foreground">Your wallet balance and details</p>
        </div>
        {wallet && wallet.status === 'active' && (
          <Button onClick={() => setTopUpOpen(true)} className="shrink-0 min-h-[44px] md:min-h-0">
            <ArrowUpCircle className="mr-2 h-4 w-4" />
            Top Up
          </Button>
        )}
      </div>

      {isLoading ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-24" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-10 w-32" />
          </CardContent>
        </Card>
      ) : !wallet ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Wallet className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No wallet found</p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Stat Cards */}
          <div className="grid grid-cols-2 gap-3 md:gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Balance
                </CardTitle>
                <Wallet className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {formatCents(Number(wallet.balance_cents), wallet.currency)}
                </div>
              </CardContent>
            </Card>
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
                  Consumed
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {formatCents(Number(wallet.consumed_amount_cents), wallet.currency)}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {formatCredits(wallet.consumed_credits)} credits
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Badge variant={wallet.status === 'active' ? 'default' : 'secondary'}>
                  {wallet.status}
                </Badge>
                {wallet.expiration_at ? (
                  <p className="text-xs text-muted-foreground mt-2">
                    Expires {format(new Date(wallet.expiration_at), 'MMM d, yyyy')}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground mt-2">
                    No expiration
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Tabs: Transactions + Balance Chart */}
          <Tabs defaultValue="transactions">
            <TabsList>
              <TabsTrigger value="transactions">Transactions</TabsTrigger>
              <TabsTrigger value="chart">Balance Chart</TabsTrigger>
            </TabsList>

            <TabsContent value="transactions">
              <Card>
                <CardHeader>
                  <CardTitle>Transaction History</CardTitle>
                </CardHeader>
                <CardContent>
                  {txLoading ? (
                    <div className="space-y-2">
                      {[...Array(5)].map((_, i) => (
                        <Skeleton key={i} className="h-10 w-full" />
                      ))}
                    </div>
                  ) : transactionsWithBalance.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">
                      No transactions yet
                    </p>
                  ) : isMobile ? (
                    <div className="space-y-3">
                      {transactionsWithBalance.map((tx) => {
                        const credits = typeof tx.amount === 'string' ? parseFloat(tx.amount) : tx.amount
                        const isInbound = tx.transaction_type === 'inbound'
                        return (
                          <div key={tx.id} className="rounded-lg border p-3">
                            <div className="flex items-center justify-between mb-1">
                              <Badge variant={isInbound ? 'default' : 'secondary'}>
                                {tx.transaction_type}
                              </Badge>
                              <span className={`font-mono font-bold ${isInbound ? 'text-green-600' : 'text-red-600'}`}>
                                {isInbound ? '+' : '-'}{formatCredits(credits)}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                              <span>{format(new Date(tx.created_at), 'MMM d, yyyy')}</span>
                              <Badge
                                variant={
                                  tx.status === 'settled' ? 'default' :
                                  tx.status === 'failed' ? 'destructive' :
                                  'secondary'
                                }
                                className="text-[10px]"
                              >
                                {tx.status}
                              </Badge>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Type</TableHead>
                          <TableHead>Credits</TableHead>
                          <TableHead>Amount</TableHead>
                          <TableHead>Running Balance</TableHead>
                          <TableHead>Source</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Date</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {transactionsWithBalance.map((tx) => {
                          const credits = typeof tx.amount === 'string' ? parseFloat(tx.amount) : tx.amount
                          const amount = typeof tx.credit_amount === 'string' ? parseFloat(tx.credit_amount) : tx.credit_amount
                          const isInbound = tx.transaction_type === 'inbound'
                          return (
                            <TableRow key={tx.id}>
                              <TableCell>
                                <Badge variant={isInbound ? 'default' : 'secondary'}>
                                  {tx.transaction_type}
                                </Badge>
                              </TableCell>
                              <TableCell className={`font-mono ${isInbound ? 'text-green-600' : 'text-red-600'}`}>
                                {isInbound ? '+' : '-'}{formatCredits(credits)}
                              </TableCell>
                              <TableCell className={`font-mono ${isInbound ? 'text-green-600' : 'text-red-600'}`}>
                                {isInbound ? '+' : '-'}{formatCents(amount, wallet.currency)}
                              </TableCell>
                              <TableCell className="font-mono">
                                {formatCents(tx.running_balance, wallet.currency)}
                              </TableCell>
                              <TableCell>
                                <span className="capitalize">{tx.source}</span>
                              </TableCell>
                              <TableCell>
                                <Badge
                                  variant={
                                    tx.status === 'settled' ? 'default' :
                                    tx.status === 'failed' ? 'destructive' :
                                    'secondary'
                                  }
                                >
                                  {tx.status}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                {format(new Date(tx.created_at), 'MMM d, yyyy HH:mm')}
                              </TableCell>
                            </TableRow>
                          )
                        })}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="chart">
              <div className="grid gap-4 md:grid-cols-1">
                {/* Balance Over Time */}
                <Card>
                  <CardHeader>
                    <CardTitle>Balance Over Time</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {timelineChartData.length === 0 ? (
                      <p className="text-center text-muted-foreground py-8">
                        No balance data available yet
                      </p>
                    ) : (
                      <ResponsiveContainer width="100%" height={300}>
                        <AreaChart data={timelineChartData}>
                          <defs>
                            <linearGradient id="balanceGradient" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                          <YAxis tick={{ fontSize: 12 }} />
                          <Tooltip
                            formatter={(value: number) => [formatCents(value, wallet.currency), 'Balance']}
                          />
                          <Area
                            type="monotone"
                            dataKey="balance"
                            stroke="#3b82f6"
                            fill="url(#balanceGradient)"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    )}
                  </CardContent>
                </Card>

                {/* Credits In / Out */}
                <Card>
                  <CardHeader>
                    <CardTitle>Credits In / Out</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {timelineChartData.length === 0 ? (
                      <p className="text-center text-muted-foreground py-8">
                        No transaction data available yet
                      </p>
                    ) : (
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={timelineChartData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                          <YAxis tick={{ fontSize: 12 }} />
                          <Tooltip
                            formatter={(value: number, name: string) => [
                              formatCents(value, wallet.currency),
                              name === 'inbound' ? 'Credits In' : 'Credits Out',
                            ]}
                          />
                          <Legend />
                          <Bar dataKey="inbound" name="Credits In" fill="#22c55e" />
                          <Bar dataKey="outbound" name="Credits Out" fill="#ef4444" />
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </>
      )}

      {/* Top Up Dialog */}
      <Dialog open={topUpOpen} onOpenChange={setTopUpOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Top Up Wallet</DialogTitle>
            <DialogDescription>
              Add credits to your wallet balance.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="credits">Credits</Label>
              <Input
                id="credits"
                type="number"
                min="0.01"
                step="0.01"
                placeholder="Enter amount of credits"
                value={topUpCredits}
                onChange={(e) => setTopUpCredits(e.target.value)}
              />
              {wallet && topUpCredits && Number(topUpCredits) > 0 && (
                <p className="text-sm text-muted-foreground">
                  Estimated cost: {formatCents(
                    Number(topUpCredits) * Number(wallet.rate_amount),
                    wallet.currency,
                  )}
                </p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTopUpOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                const credits = parseFloat(topUpCredits)
                if (credits > 0) {
                  topUpMutation.mutate(credits)
                }
              }}
              disabled={!topUpCredits || Number(topUpCredits) <= 0 || topUpMutation.isPending}
            >
              {topUpMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Top Up
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
