import { useQuery } from '@tanstack/react-query'
import {
  User,
  RefreshCw,
  Calendar,
  DollarSign,
  Wallet,
  Clock,
  TrendingUp,
  BarChart3,
  FileText,
  CreditCard,
  ArrowRight,
} from 'lucide-react'
import { format } from 'date-fns'
import { useSearchParams } from 'react-router-dom'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { portalApi } from '@/lib/api'
import type {
  PortalNextBillingInfo,
  PortalUpcomingCharge,
  PortalUsageProgress,
} from '@/lib/api'
import { formatCents, formatCurrency } from '@/lib/utils'
import { usePortalToken, usePortalBranding } from '@/layouts/PortalLayout'

function ProgressBar({ value, className }: { value: number; className?: string }) {
  const clamped = Math.max(0, Math.min(100, value))
  const color =
    clamped >= 90
      ? 'bg-red-500'
      : clamped >= 70
        ? 'bg-yellow-500'
        : 'bg-green-500'
  return (
    <div className={`h-2 w-full rounded-full bg-muted ${className ?? ''}`}>
      <div
        className={`h-2 rounded-full transition-all ${color}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}

function NextBillingCard({ info }: { info: PortalNextBillingInfo }) {
  return (
    <div className="flex items-center justify-between rounded-md border p-3">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
          <Clock className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="text-sm font-medium">{info.plan_name}</p>
          <p className="text-xs text-muted-foreground">
            {format(new Date(info.next_billing_date), 'MMM d, yyyy')}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className="text-lg font-bold text-primary">
          {info.days_until_next_billing}d
        </p>
        <p className="text-xs text-muted-foreground">
          {formatCents(info.amount_cents, info.currency)}
        </p>
      </div>
    </div>
  )
}

function UpcomingChargeCard({ charge }: { charge: PortalUpcomingCharge }) {
  return (
    <div className="rounded-md border p-3 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">{charge.plan_name}</p>
        <p className="text-sm font-bold">
          {formatCents(charge.total_estimated_cents, charge.currency)}
        </p>
      </div>
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span>Base: {formatCents(charge.base_amount_cents, charge.currency)}</span>
        {charge.usage_amount_cents > 0 && (
          <span>Usage: {formatCents(charge.usage_amount_cents, charge.currency)}</span>
        )}
      </div>
    </div>
  )
}

function UsageProgressCard({ progress }: { progress: PortalUsageProgress }) {
  return (
    <div className="rounded-md border p-3 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">{progress.feature_name}</p>
        {progress.feature_type === 'boolean' ? (
          <Badge variant={progress.entitlement_value === 'true' ? 'default' : 'outline'}>
            {progress.entitlement_value === 'true' ? 'Enabled' : 'Disabled'}
          </Badge>
        ) : progress.feature_type === 'quantity' && progress.current_usage !== null ? (
          <span className="text-xs text-muted-foreground">
            {progress.current_usage} / {progress.entitlement_value}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">
            {progress.entitlement_value}
          </span>
        )}
      </div>
      {progress.feature_type === 'quantity' && progress.usage_percentage !== null && (
        <ProgressBar value={progress.usage_percentage} />
      )}
    </div>
  )
}

function QuickActionCard({
  icon: Icon,
  title,
  description,
  href,
  token,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  description: string
  href: string
  token: string
}) {
  return (
    <a
      href={`${href}${href.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`}
      className="group flex items-center gap-3 rounded-lg border p-4 transition-colors hover:border-primary hover:bg-primary/5"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
        <Icon className="h-5 w-5 text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground truncate">{description}</p>
      </div>
      <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1" />
    </a>
  )
}

export default function PortalDashboardPage() {
  const token = usePortalToken()
  const branding = usePortalBranding()
  const [searchParams] = useSearchParams()
  const tokenParam = searchParams.get('token') || token

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

  const { data: dashboardSummary, isLoading: summaryLoading } = useQuery({
    queryKey: ['portal-dashboard-summary', token],
    queryFn: () => portalApi.getDashboardSummary(token),
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
          {branding?.welcome_message || 'Welcome to your billing portal'}
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
                  totalOutstanding,
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
                {formatCents(Number(wallet.balance_cents), wallet.currency)}
              </div>
            ) : (
              <div className="text-2xl font-bold text-muted-foreground">-</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Next Billing Date */}
      {(summaryLoading || (dashboardSummary?.next_billing?.length ?? 0) > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Next Billing
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 2 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {dashboardSummary!.next_billing.map((info) => (
                  <NextBillingCard key={info.subscription_id} info={info} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Upcoming Charges Estimate */}
      {(summaryLoading || (dashboardSummary?.upcoming_charges?.length ?? 0) > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Upcoming Charges Estimate
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 2 }).map((_, i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {dashboardSummary!.upcoming_charges.map((charge) => (
                  <UpcomingChargeCard
                    key={charge.subscription_id}
                    charge={charge}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Usage Progress vs. Plan Limits */}
      {(summaryLoading || (dashboardSummary?.usage_progress?.length ?? 0) > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Plan Limits & Usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {dashboardSummary!.usage_progress.map((progress) => (
                  <UsageProgressCard
                    key={progress.feature_code}
                    progress={progress}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Quick Action Cards */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Quick Actions</h2>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {dashboardSummary?.quick_actions.outstanding_invoice_count
            ? (
              <QuickActionCard
                icon={FileText}
                title="Pay Invoice"
                description={`${dashboardSummary.quick_actions.outstanding_invoice_count} outstanding (${formatCents(dashboardSummary.quick_actions.outstanding_amount_cents, dashboardSummary.quick_actions.currency)})`}
                href="/portal/invoices"
                token={tokenParam}
              />
            ) : !summaryLoading && (
              <QuickActionCard
                icon={FileText}
                title="View Invoices"
                description="No outstanding invoices"
                href="/portal/invoices"
                token={tokenParam}
              />
            )}
          <QuickActionCard
            icon={CreditCard}
            title="Top Up Wallet"
            description={
              dashboardSummary?.quick_actions.has_wallet
                ? `Balance: ${formatCents(dashboardSummary.quick_actions.wallet_balance_cents, dashboardSummary.quick_actions.currency)}`
                : 'Manage your wallet'
            }
            href="/portal/wallet"
            token={tokenParam}
          />
          <QuickActionCard
            icon={BarChart3}
            title="View Usage"
            description={
              dashboardSummary?.quick_actions.has_active_subscription
                ? 'Check your current usage'
                : 'No active subscriptions'
            }
            href="/portal/usage"
            token={tokenParam}
          />
        </div>
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
