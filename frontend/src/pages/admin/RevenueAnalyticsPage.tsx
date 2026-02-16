import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  DollarSign,
  TrendingUp,
  Users,
  FileText,
  Clock,
  AlertTriangle,
  CalendarIcon,
  ArrowLeft,
  BarChart3,
} from 'lucide-react'
import {
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
import { Progress } from '@/components/ui/progress'
import { dashboardApi } from '@/lib/api'
import { formatCurrency } from '@/lib/utils'
import type { DashboardDateRange } from '@/lib/api'
import type { DateRange } from 'react-day-picker'

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

const INVOICE_TYPE_LABELS: Record<string, string> = {
  subscription: 'Subscription',
  add_on: 'Add-on',
  one_off: 'One-off',
  credit: 'Credit',
  progressive_billing: 'Progressive',
}

const PIE_COLORS = [
  'hsl(var(--primary))',
  'hsl(var(--chart-2, 220 70% 55%))',
  'hsl(var(--chart-3, 150 60% 45%))',
  'hsl(var(--chart-4, 40 90% 55%))',
  'hsl(var(--chart-5, 340 70% 55%))',
]

const revenueChartConfig = {
  revenue: {
    label: 'Revenue',
    color: 'hsl(var(--primary))',
  },
} satisfies ChartConfig

const netRevenueChartConfig = {
  gross: {
    label: 'Gross Revenue',
    color: 'hsl(var(--primary))',
  },
  refunds: {
    label: 'Refunds',
    color: 'hsl(var(--destructive, 0 72% 51%))',
  },
  credit_notes: {
    label: 'Credit Notes',
    color: 'hsl(var(--chart-4, 40 90% 55%))',
  },
} satisfies ChartConfig

export default function RevenueAnalyticsPage() {
  const [preset, setPreset] = useState<PeriodPreset>('30d')
  const [customRange, setCustomRange] = useState<DateRange | undefined>()
  const [calendarOpen, setCalendarOpen] = useState(false)

  const dateParams: DashboardDateRange = useMemo(() => {
    if (preset === 'custom' && customRange?.from) {
      return {
        start_date: format(customRange.from, 'yyyy-MM-dd'),
        end_date: customRange.to
          ? format(customRange.to, 'yyyy-MM-dd')
          : format(customRange.from, 'yyyy-MM-dd'),
      }
    }
    const { start, end } = getPresetDates(preset)
    return {
      start_date: format(start, 'yyyy-MM-dd'),
      end_date: format(end, 'yyyy-MM-dd'),
    }
  }, [preset, customRange])

  const { data, isLoading } = useQuery({
    queryKey: ['revenue-analytics', dateParams],
    queryFn: () => dashboardApi.getRevenueAnalytics(dateParams),
  })

  const netRevenueBarData = useMemo(() => {
    if (!data) return []
    return [
      { name: 'Gross', value: data.net_revenue.gross_revenue, fill: 'hsl(var(--primary))' },
      { name: 'Refunds', value: data.net_revenue.refunds, fill: 'hsl(var(--destructive, 0 72% 51%))' },
      { name: 'Credits', value: data.net_revenue.credit_notes, fill: 'hsl(var(--chart-4, 40 90% 55%))' },
      { name: 'Net', value: data.net_revenue.net_revenue, fill: 'hsl(var(--chart-3, 150 60% 45%))' },
    ]
  }, [data])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link to="/admin">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Revenue Analytics</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Deep-dive into revenue trends, customer spending, and collection efficiency
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={preset}
            onValueChange={(v) => {
              const p = v as PeriodPreset
              setPreset(p)
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
                  onSelect={setCustomRange}
                  numberOfMonths={2}
                  disabled={{ after: new Date() }}
                />
              </PopoverContent>
            </Popover>
          )}
        </div>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Net Revenue"
          value={data ? formatCurrency(data.net_revenue.net_revenue, data.currency) : '—'}
          icon={DollarSign}
          loading={isLoading}
          description="After refunds & credits"
        />
        <StatCard
          title="Collection Rate"
          value={data ? `${data.collection.collection_rate}%` : '—'}
          icon={TrendingUp}
          loading={isLoading}
          description={data ? `${formatCurrency(data.collection.total_collected, data.currency)} collected` : ''}
          color={data ? (data.collection.collection_rate >= 90 ? 'green' : data.collection.collection_rate >= 70 ? 'yellow' : 'red') : undefined}
        />
        <StatCard
          title="Avg Days to Payment"
          value={data?.collection.average_days_to_payment != null ? `${data.collection.average_days_to_payment}d` : '—'}
          icon={Clock}
          loading={isLoading}
          description="From issue to payment"
        />
        <StatCard
          title="Overdue"
          value={data ? formatCurrency(data.collection.overdue_amount, data.currency) : '—'}
          icon={AlertTriangle}
          loading={isLoading}
          description={data ? `${data.collection.overdue_count} invoice${data.collection.overdue_count !== 1 ? 's' : ''}` : ''}
          color={data && data.collection.overdue_count > 0 ? 'red' : undefined}
        />
      </div>

      {/* Revenue Trend Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Daily Revenue
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-[300px] w-full" />
          ) : data && data.daily_revenue.length > 0 ? (
            <ChartContainer config={revenueChartConfig} className="h-[300px] w-full">
              <AreaChart data={data.daily_revenue} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-revenue)" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="var(--color-revenue)" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(v) => format(new Date(v + 'T00:00:00'), 'MMM d')}
                  tick={{ fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tickFormatter={(v) => `$${(v / 1).toLocaleString()}`}
                  tick={{ fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                  width={70}
                />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value) => formatCurrency(Number(value), data.currency)}
                    />
                  }
                />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  stroke="var(--color-revenue)"
                  strokeWidth={2}
                  fill="url(#revenueFill)"
                  dot={false}
                />
              </AreaChart>
            </ChartContainer>
          ) : (
            <div className="h-[300px] flex items-center justify-center text-muted-foreground">
              No revenue data for this period
            </div>
          )}
        </CardContent>
      </Card>

      {/* Two-column: Revenue by Type + Net Revenue Breakdown */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Revenue by Invoice Type */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Revenue by Type
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-[250px] w-full" />
            ) : data && data.revenue_by_type.length > 0 ? (
              <div className="flex flex-col items-center gap-4">
                <ChartContainer config={revenueChartConfig} className="h-[200px] w-full max-w-[250px]">
                  <PieChart>
                    <Pie
                      data={data.revenue_by_type}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      dataKey="revenue"
                      nameKey="invoice_type"
                    >
                      {data.revenue_by_type.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          formatter={(value) => formatCurrency(Number(value), data.currency)}
                        />
                      }
                    />
                  </PieChart>
                </ChartContainer>
                <div className="flex flex-wrap justify-center gap-3">
                  {data.revenue_by_type.map((item, i) => (
                    <div key={item.invoice_type} className="flex items-center gap-1.5 text-sm">
                      <div
                        className="h-3 w-3 rounded-full"
                        style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                      />
                      <span className="text-muted-foreground">
                        {INVOICE_TYPE_LABELS[item.invoice_type] || item.invoice_type}
                      </span>
                      <span className="font-medium">{formatCurrency(item.revenue, data.currency)}</span>
                      <Badge variant="outline" className="text-xs ml-1">{item.count}</Badge>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-muted-foreground">
                No revenue data for this period
              </div>
            )}
          </CardContent>
        </Card>

        {/* Net Revenue Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="h-5 w-5" />
              Net Revenue Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-[250px] w-full" />
            ) : data ? (
              <div className="space-y-4">
                <ChartContainer config={netRevenueChartConfig} className="h-[180px] w-full">
                  <BarChart data={netRevenueBarData} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
                    <YAxis
                      tickFormatter={(v) => `$${(v / 1).toLocaleString()}`}
                      tick={{ fontSize: 12 }}
                      tickLine={false}
                      axisLine={false}
                      width={70}
                    />
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          formatter={(value) => formatCurrency(Number(value), data.currency)}
                        />
                      }
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {netRevenueBarData.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ChartContainer>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Gross Revenue</span>
                    <span className="font-medium">{formatCurrency(data.net_revenue.gross_revenue, data.currency)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Refunds</span>
                    <span className="font-medium text-destructive">
                      {data.net_revenue.refunds > 0 ? '-' : ''}{formatCurrency(data.net_revenue.refunds, data.currency)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Credit Notes</span>
                    <span className="font-medium text-orange-600 dark:text-orange-400">
                      {data.net_revenue.credit_notes > 0 ? '-' : ''}{formatCurrency(data.net_revenue.credit_notes, data.currency)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between border-t pt-2">
                    <span className="font-semibold">Net Revenue</span>
                    <span className="font-semibold">{formatCurrency(data.net_revenue.net_revenue, data.currency)}</span>
                  </div>
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      {/* Collection Metrics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Collection Efficiency
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : data ? (
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Collection Rate</span>
                    <span className={`text-sm font-semibold ${
                      data.collection.collection_rate >= 90
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : data.collection.collection_rate >= 70
                          ? 'text-yellow-600 dark:text-yellow-400'
                          : 'text-red-600 dark:text-red-400'
                    }`}>
                      {data.collection.collection_rate}%
                    </span>
                  </div>
                  <Progress
                    value={data.collection.collection_rate}
                    className="h-3"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
                <div>
                  <p className="text-xs text-muted-foreground">Total Invoiced</p>
                  <p className="text-lg font-semibold">{formatCurrency(data.collection.total_invoiced, data.currency)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Total Collected</p>
                  <p className="text-lg font-semibold text-emerald-600 dark:text-emerald-400">
                    {formatCurrency(data.collection.total_collected, data.currency)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Avg Days to Payment</p>
                  <p className="text-lg font-semibold">
                    {data.collection.average_days_to_payment != null
                      ? `${data.collection.average_days_to_payment} days`
                      : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Overdue Amount</p>
                  <p className={`text-lg font-semibold ${data.collection.overdue_count > 0 ? 'text-red-600 dark:text-red-400' : ''}`}>
                    {formatCurrency(data.collection.overdue_amount, data.currency)}
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Top Customers by Revenue */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Top Customers by Revenue
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : data && data.top_customers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">#</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead className="text-right">Revenue</TableHead>
                  <TableHead className="text-right">Invoices</TableHead>
                  <TableHead className="text-right">Share</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.top_customers.map((customer, i) => {
                  const totalRevenue = data.top_customers.reduce((sum, c) => sum + c.revenue, 0)
                  const share = totalRevenue > 0 ? ((customer.revenue / totalRevenue) * 100).toFixed(1) : '0.0'
                  return (
                    <TableRow key={customer.customer_id}>
                      <TableCell className="font-medium text-muted-foreground">{i + 1}</TableCell>
                      <TableCell>
                        <Link
                          to={`/admin/customers/${customer.customer_id}`}
                          className="text-primary hover:underline font-medium"
                        >
                          {customer.customer_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right font-mono font-medium">
                        {formatCurrency(customer.revenue, data.currency)}
                      </TableCell>
                      <TableCell className="text-right">{customer.invoice_count}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Progress value={parseFloat(share)} className="h-2 w-16" />
                          <span className="text-xs text-muted-foreground w-12 text-right">{share}%</span>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              No customer revenue data for this period
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function StatCard({
  title,
  value,
  icon: Icon,
  loading,
  description,
  color,
}: {
  title: string
  value: string
  icon: React.ElementType
  loading?: boolean
  description: string
  color?: 'green' | 'yellow' | 'red'
}) {
  const colorClass = color === 'green'
    ? 'text-emerald-600 dark:text-emerald-400'
    : color === 'yellow'
      ? 'text-yellow-600 dark:text-yellow-400'
      : color === 'red'
        ? 'text-red-600 dark:text-red-400'
        : ''

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
            <p className={`text-2xl font-semibold tracking-tight font-mono ${colorClass}`}>
              {value}
            </p>
            <p className="text-xs text-muted-foreground mt-1">{description}</p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
