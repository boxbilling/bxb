import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Users,
  CreditCard,
  DollarSign,
  FileText,
  TrendingUp,
  AlertTriangle,
  Wallet,
  UserPlus,
  UserMinus,
  BarChart3,
  CalendarIcon,
} from 'lucide-react'
import {
  Line,
  LineChart,
  Bar,
  BarChart,
  XAxis,
  YAxis,
  CartesianGrid,
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
import { dashboardApi } from '@/lib/api'
import type { DashboardDateRange } from '@/lib/api'
import type { RecentActivity } from '@/types/billing'
import type { DateRange } from 'react-day-picker'

function formatCurrencyDollars(amount: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(amount)
}

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

function StatCard({
  title,
  value,
  description,
  icon: Icon,
  mono,
  loading,
}: {
  title: string
  value: string | number
  description: string
  icon: React.ElementType
  mono?: boolean
  loading?: boolean
}) {
  return (
    <Card>
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
            <p className={`text-2xl font-semibold tracking-tight ${mono ? 'font-mono' : ''}`}>
              {value}
            </p>
            <p className="text-xs text-muted-foreground mt-1">{description}</p>
          </>
        )}
      </CardContent>
    </Card>
  )
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
  payment_received: 'text-primary',
}

const activityIcons: Record<string, React.ElementType> = {
  customer_created: Users,
  subscription_created: CreditCard,
  invoice_finalized: FileText,
  payment_received: DollarSign,
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

const usageChartConfig = {
  event_count: {
    label: 'Events',
    color: 'hsl(var(--primary))',
  },
} satisfies ChartConfig

export default function DashboardPage() {
  const [preset, setPreset] = useState<PeriodPreset>('30d')
  const [customRange, setCustomRange] = useState<DateRange | undefined>()

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

  const { data: activity, isLoading: activityLoading } = useQuery({
    queryKey: ['dashboard-activity'],
    queryFn: () => dashboardApi.getRecentActivity(),
  })

  const periodLabel = preset === 'custom'
    ? (customRange?.from ? `${format(customRange.from, 'MMM d')} - ${format(customRange?.to ?? new Date(), 'MMM d')}` : 'custom period')
    : PERIOD_LABELS[preset].toLowerCase()

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Dashboard</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Overview of your billing platform
          </p>
        </div>
        <PeriodSelector
          preset={preset}
          onPresetChange={setPreset}
          customRange={customRange}
          onCustomRangeChange={setCustomRange}
        />
      </div>

      {/* Revenue Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="MRR"
          value={
            revenue
              ? formatCurrencyDollars(revenue.mrr, revenue.currency)
              : '-'
          }
          description={`recurring revenue (${periodLabel})`}
          icon={TrendingUp}
          mono
          loading={revenueLoading}
        />
        <StatCard
          title="Outstanding Invoices"
          value={
            revenue
              ? formatCurrencyDollars(revenue.outstanding_invoices, revenue.currency)
              : '-'
          }
          description="awaiting payment"
          icon={FileText}
          mono
          loading={revenueLoading}
        />
        <StatCard
          title="Overdue Amount"
          value={
            revenue
              ? formatCurrencyDollars(revenue.overdue_amount, revenue.currency)
              : '-'
          }
          description="past due date"
          icon={AlertTriangle}
          mono
          loading={revenueLoading}
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
        />
        <StatCard
          title="New Customers"
          value={customerMetrics?.new_this_month.toLocaleString() ?? '-'}
          description={periodLabel}
          icon={UserPlus}
          loading={customersLoading}
        />
        <StatCard
          title="Churned"
          value={customerMetrics?.churned_this_month.toLocaleString() ?? '-'}
          description={periodLabel}
          icon={UserMinus}
          loading={customersLoading}
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
        />
        <StatCard
          title="New Subscriptions"
          value={subscriptionMetrics?.new_this_month.toLocaleString() ?? '-'}
          description={periodLabel}
          icon={CreditCard}
          loading={subscriptionsLoading}
        />
        <StatCard
          title="Canceled"
          value={subscriptionMetrics?.canceled_this_month.toLocaleString() ?? '-'}
          description={periodLabel}
          icon={CreditCard}
          loading={subscriptionsLoading}
        />
      </div>

      {/* Charts Row */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        {/* Revenue Trend Chart */}
        <Card className="col-span-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Revenue Trend ({PERIOD_LABELS[preset]})</CardTitle>
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
                          formatCurrencyDollars(Number(value), revenue.currency)
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
            <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
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
                  return (
                    <div key={item.id} className="flex items-center gap-3 py-1.5">
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted shrink-0">
                        <Icon className={`h-3.5 w-3.5 ${color}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] leading-snug truncate">{item.description}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatRelativeTime(item.timestamp)}
                        </p>
                      </div>
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

      {/* Bottom Charts Row */}
      <div className="grid gap-4 md:grid-cols-2">
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
