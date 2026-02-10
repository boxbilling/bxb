import { useQuery } from '@tanstack/react-query'
import {
  Users,
  CreditCard,
  DollarSign,
  FileText,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { DashboardStats, RecentActivity } from '@/types/billing'

// Mock data for development
const mockStats: DashboardStats = {
  total_customers: 1247,
  active_subscriptions: 892,
  monthly_recurring_revenue: 47500,
  total_invoiced: 156000,
  currency: 'USD',
}

const mockActivity: RecentActivity[] = [
  {
    id: '1',
    type: 'customer_created',
    description: 'New customer "Acme Corp" created',
    timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
  },
  {
    id: '2',
    type: 'subscription_created',
    description: 'Subscription started for "TechStart Inc"',
    timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
  },
  {
    id: '3',
    type: 'invoice_finalized',
    description: 'Invoice #INV-2024-0042 finalized for $1,250',
    timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
  },
  {
    id: '4',
    type: 'payment_received',
    description: 'Payment received for Invoice #INV-2024-0041',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
  },
  {
    id: '5',
    type: 'subscription_created',
    description: 'Subscription upgraded for "CloudNine Ltd"',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
  },
]

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
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
  trend,
  loading,
}: {
  title: string
  value: string | number
  description: string
  icon: React.ElementType
  trend?: { value: number; positive: boolean }
  loading?: boolean
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <>
            <Skeleton className="h-8 w-24 mb-1" />
            <Skeleton className="h-4 w-32" />
          </>
        ) : (
          <>
            <div className="text-2xl font-bold">{value}</div>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              {trend && (
                <span
                  className={`flex items-center ${
                    trend.positive ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {trend.positive ? (
                    <ArrowUpRight className="h-3 w-3" />
                  ) : (
                    <ArrowDownRight className="h-3 w-3" />
                  )}
                  {trend.value}%
                </span>
              )}
              <span>{description}</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

function ActivityIcon({ type }: { type: RecentActivity['type'] }) {
  switch (type) {
    case 'customer_created':
      return <Users className="h-4 w-4 text-blue-500" />
    case 'subscription_created':
      return <CreditCard className="h-4 w-4 text-green-500" />
    case 'invoice_finalized':
      return <FileText className="h-4 w-4 text-orange-500" />
    case 'payment_received':
      return <DollarSign className="h-4 w-4 text-emerald-500" />
    default:
      return <TrendingUp className="h-4 w-4 text-gray-500" />
  }
}

export default function DashboardPage() {
  // For now, use mock data. Replace with actual API calls when backend is ready
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      // TODO: Replace with actual API call
      // return dashboardApi.getStats()
      await new Promise((r) => setTimeout(r, 500))
      return mockStats
    },
  })

  const { data: activity, isLoading: activityLoading } = useQuery({
    queryKey: ['dashboard-activity'],
    queryFn: async () => {
      // TODO: Replace with actual API call
      // return dashboardApi.getRecentActivity()
      await new Promise((r) => setTimeout(r, 500))
      return mockActivity
    },
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground">
          Overview of your billing platform
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Customers"
          value={stats?.total_customers.toLocaleString() ?? '-'}
          description="from last month"
          icon={Users}
          trend={{ value: 12.5, positive: true }}
          loading={statsLoading}
        />
        <StatCard
          title="Active Subscriptions"
          value={stats?.active_subscriptions.toLocaleString() ?? '-'}
          description="from last month"
          icon={CreditCard}
          trend={{ value: 8.2, positive: true }}
          loading={statsLoading}
        />
        <StatCard
          title="Monthly Revenue"
          value={
            stats
              ? formatCurrency(stats.monthly_recurring_revenue * 100, stats.currency)
              : '-'
          }
          description="MRR"
          icon={DollarSign}
          trend={{ value: 15.3, positive: true }}
          loading={statsLoading}
        />
        <StatCard
          title="Total Invoiced"
          value={
            stats
              ? formatCurrency(stats.total_invoiced * 100, stats.currency)
              : '-'
          }
          description="this year"
          icon={FileText}
          trend={{ value: 23.1, positive: true }}
          loading={statsLoading}
        />
      </div>

      {/* Activity & Charts */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        {/* Revenue Chart Placeholder */}
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>Revenue Overview</CardTitle>
            <CardDescription>Monthly recurring revenue trend</CardDescription>
          </CardHeader>
          <CardContent className="h-[300px] flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <TrendingUp className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>Chart coming soon</p>
              <p className="text-sm">Connect to backend for real data</p>
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Latest billing events</CardDescription>
          </CardHeader>
          <CardContent>
            {activityLoading ? (
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="flex items-center gap-4">
                    <Skeleton className="h-8 w-8 rounded-full" />
                    <div className="flex-1 space-y-1">
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-3 w-1/4" />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-4">
                {activity?.map((item) => (
                  <div key={item.id} className="flex items-center gap-4">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
                      <ActivityIcon type={item.type} />
                    </div>
                    <div className="flex-1 space-y-1">
                      <p className="text-sm leading-none">{item.description}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatRelativeTime(item.timestamp)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
