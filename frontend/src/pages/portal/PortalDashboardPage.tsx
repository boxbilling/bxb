import { useQuery } from '@tanstack/react-query'
import { User, RefreshCw, Calendar, DollarSign, Wallet } from 'lucide-react'
import { format } from 'date-fns'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { portalApi } from '@/lib/api'
import { usePortalToken } from '@/layouts/PortalLayout'

function formatCurrency(amount: string | number, currency: string): string {
  const value = typeof amount === 'number' ? amount / 100 : parseFloat(amount)
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(value)
}

export default function PortalDashboardPage() {
  const token = usePortalToken()

  const { data: customer, isLoading: customerLoading } = useQuery({
    queryKey: ['portal-customer', token],
    queryFn: () => portalApi.getCustomer(token),
    enabled: !!token,
  })

  const { data: invoices = [], isLoading: invoicesLoading } = useQuery({
    queryKey: ['portal-invoices', token],
    queryFn: () => portalApi.listInvoices(token),
    enabled: !!token,
  })

  const { data: wallet, isLoading: walletLoading } = useQuery({
    queryKey: ['portal-wallet', token],
    queryFn: () => portalApi.getWallet(token),
    enabled: !!token,
  })

  const outstandingInvoices = invoices.filter(
    (inv) => inv.status === 'finalized' || inv.status === 'pending'
  )
  const totalOutstanding = outstandingInvoices.reduce(
    (sum, inv) => sum + parseFloat(inv.total),
    0
  )

  const isLoading = customerLoading || invoicesLoading || walletLoading

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Overview</h1>
        <p className="text-muted-foreground">
          Welcome to your billing portal
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Customer Name */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Customer
            </CardTitle>
            <User className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-7 w-32" />
            ) : (
              <div className="text-2xl font-bold">{customer?.name}</div>
            )}
          </CardContent>
        </Card>

        {/* Grace Period */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Grace Period
            </CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-7 w-32" />
            ) : (
              <div className="text-2xl font-bold">
                {customer?.invoice_grace_period ?? 0}d
              </div>
            )}
          </CardContent>
        </Card>

        {/* Outstanding Amount */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Outstanding
            </CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-7 w-24" />
            ) : (
              <div className="text-2xl font-bold">
                {formatCurrency(
                  String(totalOutstanding),
                  customer?.currency || 'USD'
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Wallet Balance */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Wallet Balance
            </CardTitle>
            <Wallet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-7 w-24" />
            ) : wallet ? (
              <div className="text-2xl font-bold">
                {formatCurrency(Number(wallet.balance_cents), wallet.currency)}
              </div>
            ) : (
              <div className="text-2xl font-bold text-muted-foreground">-</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Invoices */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="h-5 w-5" />
            Recent Invoices
          </CardTitle>
        </CardHeader>
        <CardContent>
          {invoicesLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : invoices.length === 0 ? (
            <p className="text-sm text-muted-foreground">No invoices yet</p>
          ) : (
            <div className="space-y-3">
              {invoices.slice(0, 5).map((invoice) => (
                <div
                  key={invoice.id}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div>
                    <p className="text-sm font-medium">
                      {invoice.invoice_number}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {format(new Date(invoice.created_at), 'MMM d, yyyy')}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium">
                      {formatCurrency(invoice.total, invoice.currency)}
                    </span>
                    <Badge
                      variant={
                        invoice.status === 'paid'
                          ? 'default'
                          : invoice.status === 'voided'
                            ? 'outline'
                            : 'secondary'
                      }
                    >
                      {invoice.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
