import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Users,
  CreditCard,
  DollarSign,
  FileText,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Wallet,
  UserPlus,
  UserMinus,
  BarChart3,
  CalendarIcon,
  Minus,
  ArrowRight,
  XCircle,
  FileMinus,
  ArrowUpCircle,
} from 'lucide-react'
import {
  Line,
  LineChart,
  Area,
  AreaChart,
  Bar,
  BarChart,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from 'recharts'
import { format, subDays, subMonths } from 'date-fns'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import { Button } from '@/components/ui/button'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import PageHeader from '@/components/PageHeader'
import { dashboardApi } from '@/lib/api'
import { formatCurrency } from '@/lib/utils'
import type { DashboardDateRange } from '@/lib/api'
import type { RecentActivity } from '@/types/billing'
import type { DateRange } from 'react-day-picker'

function formatRelativeTime(timestamp: string) {
  const now = new Date()
  const date = new Date(timestamp)
  const diff = now.getTime() - date.getTime()

  const minutes = Math.floor(diff / (1000 * 60))
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}

function TrendBadge({
  changePercent,
  invertColor,
}: {
  changePercent: number | null
  invertColor?: boolean
}) {
  if (changePercent === null) return null

  const isPositive = changePercent > 0
  const isNeutral = changePercent === 0

  let colorClass: string
  if (isNeutral) {
    colorClass = 'text-muted-foreground'
  } else if (invertColor ? !isPositive : isPositive) {
    colorClass = 'text-emerald-600 dark:text-emerald-400'
  } else {
    colorClass = 'text-red-600 dark:text-red-400'
  }

  const TrendIcon = isNeutral ? Minus : isPositive ? TrendingUp : TrendingDown

  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${colorClass}`}>
      <TrendIcon className="h-3 w-3" />
      {Math.abs(changePercent)}%
    </span>
  )
}

function Sparkline({
  data,
  color = 'hsl(var(--primary))',
}: {
  data: { date: string; value: number }[]
  color?: string
}) {
  if (data.length < 2) return null
  return (
    <div className="mt-2 -mx-1">
      <ResponsiveContainer width="100%" height={32}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id={`sparkFill-${color.replace(/[^a-zA-Z0-9]/g, '')}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.2} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#sparkFill-${color.replace(/[^a-zA-Z0-9]/g, '')})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function StatCard({
  title,
  value,
  description,
  icon: Icon,
  mono,
  loading,
  trend,
  invertTrendColor,
  href,
  sparklineData,
  sparklineColor,
}: {
  title: string
  value: string | number
  description: string
  icon: React.ElementType
  mono?: boolean
  loading?: boolean
  trend?: { change_percent: number | null } | null
  invertTrendColor?: boolean
  href?: string
  sparklineData?: { date: string; value: number }[]
  sparklineColor?: string
}) {
  const card = (
    <Card className={href ? 'transition-colors hover:border-primary/40 cursor-pointer' : undefined}>
      <CardContent className="pt-5 pb-4 px-5">
        {loading ? (
          <>
            <Skeleton className="h-3 w-20 mb-3" />
            <Skeleton className="h-7 w-28 mb-1" />
            <Skeleton className="h-3 w-16" />
          </>
        ) : (
          <>
            <div className="flex items-center justify-between mb-3">
              <p className="text-[13px] font-medium text-muted-foreground">{title}</p>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="flex items-baseline gap-2">
              <p className={`text-2xl font-semibold tracking-tight ${mono ? 'font-mono' : ''}`}>
                {value}
              </p>
              {trend && <TrendBadge changePercent={trend.change_percent} invertColor={invertTrendColor} />}
            </div>
            <p className="text-xs text-muted-foreground mt-1">{description}</p>
            {sparklineData && sparklineData.length >= 2 && (
              <Sparkline data={sparklineData} color={sparklineColor} />
            )}
          </>
        )}
      </CardContent>
    </Card>
  )

  if (href) {
    return (
      <Link to={href} className="no-underline">
        {card}
      </Link>
    )
  }

  return card
}

type PeriodPreset = '7d' | '30d' | '90d' | '12m' | 'custom'

const PERIOD_LABELS: Record<PeriodPreset, string> = {
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  '90d': 'Last 90 days',
  '12m': 'Last 12 months',
  custom: 'Custom range',
}

function getPresetDates(preset: PeriodPreset): { start: Date; end: Date } {
  const end = new Date()
  switch (preset) {
    case '7d':
      return { start: subDays(end, 7), end }
    case '30d':
      return { start: subDays(end, 30), end }
    case '90d':
      return { start: subDays(end, 90), end }
    case '12m':
      return { start: subMonths(end, 12), end }
    default:
      return { start: subDays(end, 30), end }
  }
}

function PeriodSelector({
  preset,
  onPresetChange,
  customRange,
  onCustomRangeChange,
}: {
  preset: PeriodPreset
  onPresetChange: (p: PeriodPreset) => void
  customRange: DateRange | undefined
  onCustomRangeChange: (r: DateRange | undefined) => void
}) {
  const [calendarOpen, setCalendarOpen] = useState(false)

  return (
    <div className="flex items-center gap-2">
      <Select
        value={preset}
        onValueChange={(v) => {
          const p = v as PeriodPreset
          onPresetChange(p)
          if (p === 'custom') setCalendarOpen(true)
        }}
      >
        <SelectTrigger size="sm" className="w-[160px]">
          <CalendarIcon className="mr-1 h-3.5 w-3.5" />
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(PERIOD_LABELS).map(([key, label]) => (
            <SelectItem key={key} value={key}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {preset === 'custom' && (
        <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
          <PopoverTrigger asChild>
            <Button variant="outline" size="sm" className="font-normal">
              {customRange?.from
                ? customRange.to
                  ? `${format(customRange.from, 'MMM d, yyyy')} - ${format(customRange.to, 'MMM d, yyyy')}`
                  : format(customRange.from, 'MMM d, yyyy')
                : 'Pick dates'}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="end">
            <Calendar
              mode="range"
              selected={customRange}
              onSelect={onCustomRangeChange}
              numberOfMonths={2}
              disabled={{ after: new Date() }}
            />
          </PopoverContent>
        </Popover>
      )}
    </div>
  )
}

const activityColors: Record<string, string> = {
  customer_created: 'text-primary',
  subscription_created: 'text-primary',
  invoice_finalized: 'text-primary',
  payment_received: 'text-green-600',
  subscription_canceled: 'text-orange-500',
  payment_failed: 'text-red-500',
  credit_note_created: 'text-purple-500',
  wallet_topped_up: 'text-blue-500',
}

const activityIcons: Record<string, React.ElementType> = {
  customer_created: Users,
  subscription_created: CreditCard,
  invoice_finalized: FileText,
  payment_received: DollarSign,
  subscription_canceled: XCircle,
  payment_failed: AlertTriangle,
  credit_note_created: FileMinus,
  wallet_topped_up: ArrowUpCircle,
}

const activityResourceRoutes: Record<string, string> = {
  customer: '/admin/customers',
  subscription: '/admin/subscriptions',
  invoice: '/admin/invoices',
  wallet: '/admin/wallets',
}

const revenueChartConfig = {
  revenue: {
    label: 'Revenue',
    color: 'hsl(var(--primary))',
  },
} satisfies ChartConfig

const planChartConfig = {
  count: {
    label: 'Subscriptions',
    color: 'hsl(var(--primary))',
  },
} satisfies ChartConfig

function InvoiceStatusBadge({ status }: { status: string }) {
  const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string; className?: string }> = {
    draft: { variant: 'secondary', label: 'Draft' },
    finalized: { variant: 'outline', label: 'Finalized', className: 'border-orange-500 text-orange-600' },
    paid: { variant: 'default', label: 'Paid', className: 'bg-green-600' },
    voided: { variant: 'destructive', label: 'Voided' },
  }
  const config = variants[status]
  if (!config) return <Badge variant="outline">{status}</Badge>
  return <Badge variant={config.variant} className={config.className}>{config.label}</Badge>
}

function SubStatusBadge({ status }: { status: string }) {
  const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
    pending: { variant: 'secondary', label: 'Pending' },
    active: { variant: 'default', label: 'Active' },
    canceled: { variant: 'outline', label: 'Canceled' },
    terminated: { variant: 'destructive', label: 'Terminated' },
  }
  const config = variants[status]
  if (!config) return <Badge variant="outline">{status}</Badge>
  return <Badge variant={config.variant}>{config.label}</Badge>
}

const usageChartConfig = {
  event_count: {
    label: 'Events',
    color: 'hsl(var(--primary))',
  },
} satisfies ChartConfig

const PLAN_COLORS = [
  'hsl(var(--primary))',
  'hsl(var(--chart-2, 160 60% 45%))',
  'hsl(var(--chart-3, 30 80% 55%))',
  'hsl(var(--chart-4, 280 65% 60%))',
  'hsl(var(--chart-5, 340 75% 55%))',
  'hsl(200 70% 50%)',
  'hsl(45 90% 50%)',
  'hsl(120 40% 50%)',
]

const revenueByPlanChartConfig = {
  revenue: {
    label: 'Revenue',
  },
} satisfies ChartConfig

export default function DashboardPage() {
  const [preset, setPreset] = useState<PeriodPreset>('30d')
  const [customRange, setCustomRange] = useState<DateRange | undefined>()
  const [activityTypeFilter, setActivityTypeFilter] = useState('all')

  const dateParams: DashboardDateRange = useMemo(() => {
    if (preset === 'custom' && customRange?.from) {
      return {
        start_date: format(customRange.from, 'yyyy-MM-dd'),
        end_date: customRange.to
          ? format(customRange.to, 'yyyy-MM-dd')
          : format(new Date(), 'yyyy-MM-dd'),
      }
    }
    const { start, end } = getPresetDates(preset)
    return {
      start_date: format(start, 'yyyy-MM-dd'),
      end_date: format(end, 'yyyy-MM-dd'),
    }
  }, [preset, customRange])

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats', dateParams],
    queryFn: () => dashboardApi.getStats(dateParams),
  })

  const { data: revenue, isLoading: revenueLoading } = useQuery({
    queryKey: ['dashboard-revenue', dateParams],
    queryFn: () => dashboardApi.getRevenue(dateParams),
  })

  const { data: customerMetrics, isLoading: customersLoading } = useQuery({
    queryKey: ['dashboard-customers', dateParams],
    queryFn: () => dashboardApi.getCustomerMetrics(dateParams),
  })

  const { data: subscriptionMetrics, isLoading: subscriptionsLoading } = useQuery({
    queryKey: ['dashboard-subscriptions', dateParams],
    queryFn: () => dashboardApi.getSubscriptionMetrics(dateParams),
  })

  const { data: usageMetrics, isLoading: usageLoading } = useQuery({
    queryKey: ['dashboard-usage', dateParams],
    queryFn: () => dashboardApi.getUsageMetrics(dateParams),
  })

  const activityParams = useMemo(
    () => (activityTypeFilter !== 'all' ? { type: activityTypeFilter } : undefined),
    [activityTypeFilter],
  )

  const { data: activity, isLoading: activityLoading } = useQuery({
    queryKey: ['dashboard-activity', activityParams],
    queryFn: () => dashboardApi.getRecentActivity(activityParams),
    refetchInterval: 30000,
  })

  const { data: recentInvoices, isLoading: recentInvoicesLoading } = useQuery({
    queryKey: ['dashboard-recent-invoices'],
    queryFn: () => dashboardApi.getRecentInvoices(),
  })

  const { data: recentSubscriptions, isLoading: recentSubscriptionsLoading } = useQuery({
    queryKey: ['dashboard-recent-subscriptions'],
    queryFn: () => dashboardApi.getRecentSubscriptions(),
  })

  const { data: sparklines } = useQuery({
    queryKey: ['dashboard-sparklines', dateParams],
    queryFn: () => dashboardApi.getSparklines(dateParams),
  })

  const { data: revenueByPlan, isLoading: revenueByPlanLoading } = useQuery({
    queryKey: ['dashboard-revenue-by-plan', dateParams],
    queryFn: () => dashboardApi.getRevenueByPlan(dateParams),
  })

  const periodLabel = preset === 'custom'
    ? (customRange?.from ? `${format(customRange.from, 'MMM d')} - ${format(customRange?.to ?? new Date(), 'MMM d')}` : 'custom period')
    : PERIOD_LABELS[preset].toLowerCase()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Overview of your billing platform"
        actions={
          <PeriodSelector
            preset={preset}
            onPresetChange={setPreset}
            customRange={customRange}
            onCustomRangeChange={setCustomRange}
          />
        }
      />

      {/* Revenue Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="MRR"
          value={
            revenue
              ? formatCurrency(revenue.mrr, revenue.currency)
              : '-'
          }
          description={`recurring revenue (${periodLabel})`}
          icon={TrendingUp}
          mono
          loading={revenueLoading}
          trend={revenue?.mrr_trend}
          href="/admin/invoices?status=paid"
          sparklineData={sparklines?.mrr}
          sparklineColor="hsl(var(--primary))"
        />
        <StatCard
          title="Outstanding Invoices"
          value={
            revenue
              ? formatCurrency(revenue.outstanding_invoices, revenue.currency)
              : '-'
          }
          description="awaiting payment"
          icon={FileText}
          mono
          loading={revenueLoading}
          href="/admin/invoices?status=finalized"
        />
        <StatCard
          title="Overdue Amount"
          value={
            revenue
              ? formatCurrency(revenue.overdue_amount, revenue.currency)
              : '-'
          }
          description="past due date"
          icon={AlertTriangle}
          mono
          loading={revenueLoading}
          href="/admin/invoices?status=finalized"
        />
        <StatCard
          title="Wallet Credits"
          value={
            stats
              ? stats.total_wallet_credits.toLocaleString(undefined, { maximumFractionDigits: 2 })
              : '-'
          }
          description="total prepaid credits"
          icon={Wallet}
          mono
          loading={statsLoading}
          href="/admin/wallets"
        />
      </div>

      {/* Customer & Subscription Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <StatCard
          title="Customers"
          value={customerMetrics?.total.toLocaleString() ?? '-'}
          description="total"
          icon={Users}
          loading={customersLoading}
          href="/admin/customers"
        />
        <StatCard
          title="New Customers"
          value={customerMetrics?.new_this_month.toLocaleString() ?? '-'}
          description={periodLabel}
          icon={UserPlus}
          loading={customersLoading}
          trend={customerMetrics?.new_trend}
          href="/admin/customers"
          sparklineData={sparklines?.new_customers}
          sparklineColor="hsl(160 60% 45%)"
        />
        <StatCard
          title="Churned"
          value={customerMetrics?.churned_this_month.toLocaleString() ?? '-'}
          description={periodLabel}
          icon={UserMinus}
          loading={customersLoading}
          trend={customerMetrics?.churned_trend}
          invertTrendColor
          href="/admin/customers"
        />
      </div>

      {/* Subscription Metrics Row */}
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Active Subscriptions"
          value={subscriptionMetrics?.active.toLocaleString() ?? '-'}
          description="currently active"
          icon={CreditCard}
          loading={subscriptionsLoading}
          href="/admin/subscriptions?status=active"
        />
        <StatCard
          title="New Subscriptions"
          value={subscriptionMetrics?.new_this_month.toLocaleString() ?? '-'}
          description={periodLabel}
          icon={CreditCard}
          loading={subscriptionsLoading}
          trend={subscriptionMetrics?.new_trend}
          href="/admin/subscriptions"
          sparklineData={sparklines?.new_subscriptions}
          sparklineColor="hsl(200 70% 50%)"
        />
        <StatCard
          title="Canceled"
          value={subscriptionMetrics?.canceled_this_month.toLocaleString() ?? '-'}
          description={periodLabel}
          icon={CreditCard}
          loading={subscriptionsLoading}
          trend={subscriptionMetrics?.canceled_trend}
          invertTrendColor
          href="/admin/subscriptions?status=canceled"
        />
      </div>

      {/* Charts Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        {/* Revenue Trend Chart */}
        <Card className="col-span-4">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-medium">Revenue Trend ({PERIOD_LABELS[preset]})</CardTitle>
            <Link to="/admin/revenue-analytics" className="text-xs text-primary hover:underline">
              Deep dive →
            </Link>
          </CardHeader>
          <CardContent>
            {revenueLoading ? (
              <div className="h-[280px] flex items-center justify-center">
                <Skeleton className="h-full w-full" />
              </div>
            ) : revenue && revenue.monthly_trend.length > 0 ? (
              <ChartContainer config={revenueChartConfig} className="h-[280px] w-full">
                <LineChart data={revenue.monthly_trend} accessibilityLayer>
                  <CartesianGrid vertical={false} />
                  <XAxis
                    dataKey="month"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    tickFormatter={(v) => v.slice(5)}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    tickFormatter={(v) => `$${v}`}
                  />
                  <ChartTooltip
                    content={
                      <ChartTooltipContent
                        formatter={(value) =>
                          formatCurrency(Number(value), revenue.currency)
                        }
                      />
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="revenue"
                    stroke="var(--color-revenue)"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ChartContainer>
            ) : (
              <div className="h-[280px] flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <TrendingUp className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No revenue data yet</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card className="col-span-3">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
              <Link to="/admin/audit-logs" className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            <Select value={activityTypeFilter} onValueChange={setActivityTypeFilter}>
              <SelectTrigger size="sm" className="w-[160px] mt-1">
                <SelectValue placeholder="Filter type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All activity</SelectItem>
                <SelectItem value="customer_created">Customers</SelectItem>
                <SelectItem value="subscription_created">Subscriptions</SelectItem>
                <SelectItem value="subscription_canceled">Canceled subs</SelectItem>
                <SelectItem value="invoice_finalized">Invoices</SelectItem>
                <SelectItem value="payment_received">Payments</SelectItem>
                <SelectItem value="payment_failed">Failed payments</SelectItem>
                <SelectItem value="credit_note_created">Credit notes</SelectItem>
                <SelectItem value="wallet_topped_up">Wallet top-ups</SelectItem>
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent>
            {activityLoading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-7 w-7 rounded-full" />
                    <div className="flex-1 space-y-1">
                      <Skeleton className="h-3.5 w-3/4" />
                      <Skeleton className="h-3 w-1/4" />
                    </div>
                  </div>
                ))}
              </div>
            ) : activity && activity.length > 0 ? (
              <div className="space-y-1">
                {activity.map((item: RecentActivity) => {
                  const Icon = activityIcons[item.type] ?? TrendingUp
                  const color = activityColors[item.type] ?? 'text-muted-foreground'
                  const route = item.resource_type ? activityResourceRoutes[item.resource_type] : null
                  const href = route && item.resource_id ? `${route}/${item.resource_id}` : null
                  const content = (
                    <>
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted shrink-0">
                        <Icon className={`h-3.5 w-3.5 ${color}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] leading-snug truncate">{item.description}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatRelativeTime(item.timestamp)}
                        </p>
                      </div>
                    </>
                  )
                  return href ? (
                    <Link
                      key={item.id}
                      to={href}
                      className="flex items-center gap-3 py-1.5 rounded-md -mx-2 px-2 hover:bg-muted/50 transition-colors"
                    >
                      {content}
                    </Link>
                  ) : (
                    <div key={item.id} className="flex items-center gap-3 py-1.5">
                      {content}
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                No recent activity
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Invoices & Recent Subscriptions Tables */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Recent Invoices */}
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-medium">Recent Invoices</CardTitle>
            <Link to="/admin/invoices" className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent>
            {recentInvoicesLoading ? (
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : recentInvoices && recentInvoices.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Invoice</TableHead>
                    <TableHead className="text-xs">Customer</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-xs text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentInvoices.map((inv) => (
                    <TableRow key={inv.id}>
                      <TableCell className="text-xs font-mono py-2">{inv.invoice_number}</TableCell>
                      <TableCell className="text-xs py-2 truncate max-w-[120px]">{inv.customer_name}</TableCell>
                      <TableCell className="py-2">
                        <InvoiceStatusBadge status={inv.status} />
                      </TableCell>
                      <TableCell className="text-xs text-right py-2 font-mono">
                        {formatCurrency(inv.total, inv.currency)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                No invoices yet
              </p>
            )}
          </CardContent>
        </Card>

        {/* Recent Subscriptions */}
        <Card>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-medium">Recent Subscriptions</CardTitle>
            <Link to="/admin/subscriptions" className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </CardHeader>
          <CardContent>
            {recentSubscriptionsLoading ? (
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : recentSubscriptions && recentSubscriptions.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">ID</TableHead>
                    <TableHead className="text-xs">Customer</TableHead>
                    <TableHead className="text-xs">Plan</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentSubscriptions.map((sub) => (
                    <TableRow key={sub.id}>
                      <TableCell className="text-xs font-mono py-2">{sub.external_id}</TableCell>
                      <TableCell className="text-xs py-2 truncate max-w-[120px]">{sub.customer_name}</TableCell>
                      <TableCell className="text-xs py-2 truncate max-w-[100px]">{sub.plan_name}</TableCell>
                      <TableCell className="py-2">
                        <SubStatusBadge status={sub.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                No subscriptions yet
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Bottom Charts Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Revenue by Plan (Donut) */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Revenue by Plan ({PERIOD_LABELS[preset]})</CardTitle>
          </CardHeader>
          <CardContent>
            {revenueByPlanLoading ? (
              <div className="h-[250px] flex items-center justify-center">
                <Skeleton className="h-full w-full" />
              </div>
            ) : revenueByPlan && revenueByPlan.by_plan.length > 0 ? (
              <ChartContainer config={revenueByPlanChartConfig} className="h-[250px] w-full">
                <PieChart accessibilityLayer>
                  <Pie
                    data={revenueByPlan.by_plan}
                    dataKey="revenue"
                    nameKey="plan_name"
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={2}
                  >
                    {revenueByPlan.by_plan.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={PLAN_COLORS[index % PLAN_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <ChartTooltip
                    content={
                      <ChartTooltipContent
                        nameKey="plan_name"
                        formatter={(value) =>
                          formatCurrency(Number(value), revenueByPlan.currency)
                        }
                      />
                    }
                  />
                </PieChart>
              </ChartContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <DollarSign className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No revenue data yet</p>
                </div>
              </div>
            )}
            {revenueByPlan && revenueByPlan.by_plan.length > 0 && (
              <div className="mt-2 space-y-1">
                {revenueByPlan.by_plan.map((plan, index) => (
                  <div key={plan.plan_name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5">
                      <div
                        className="h-2.5 w-2.5 rounded-sm shrink-0"
                        style={{ backgroundColor: PLAN_COLORS[index % PLAN_COLORS.length] }}
                      />
                      <span className="text-muted-foreground truncate max-w-[120px]">{plan.plan_name}</span>
                    </div>
                    <span className="font-mono font-medium">
                      {formatCurrency(plan.revenue, revenueByPlan.currency)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Subscriptions by Plan */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Subscriptions by Plan</CardTitle>
          </CardHeader>
          <CardContent>
            {subscriptionsLoading ? (
              <div className="h-[250px] flex items-center justify-center">
                <Skeleton className="h-full w-full" />
              </div>
            ) : subscriptionMetrics && subscriptionMetrics.by_plan.length > 0 ? (
              <ChartContainer config={planChartConfig} className="h-[250px] w-full">
                <BarChart data={subscriptionMetrics.by_plan} accessibilityLayer>
                  <CartesianGrid vertical={false} />
                  <XAxis
                    dataKey="plan_name"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    allowDecimals={false}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar
                    dataKey="count"
                    fill="var(--color-count)"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ChartContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <CreditCard className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No active subscriptions</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Billable Metrics by Usage */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Top Metrics by Usage ({PERIOD_LABELS[preset]})</CardTitle>
          </CardHeader>
          <CardContent>
            {usageLoading ? (
              <div className="h-[250px] flex items-center justify-center">
                <Skeleton className="h-full w-full" />
              </div>
            ) : usageMetrics && usageMetrics.top_metrics.length > 0 ? (
              <ChartContainer config={usageChartConfig} className="h-[250px] w-full">
                <BarChart data={usageMetrics.top_metrics} accessibilityLayer>
                  <CartesianGrid vertical={false} />
                  <XAxis
                    dataKey="metric_name"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                  />
                  <YAxis
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    allowDecimals={false}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar
                    dataKey="event_count"
                    fill="var(--color-event_count)"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ChartContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <BarChart3 className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No usage data yet</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
