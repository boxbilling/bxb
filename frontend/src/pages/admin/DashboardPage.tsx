import { useQuery } from '@tanstack/react-query'
import {
  Users,
  CreditCard,
  DollarSign,
  FileText,
  TrendingUp,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { dashboardApi } from '@/lib/api'
import type { RecentActivity } from '@/types/billing'

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

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => dashboardApi.getStats(),
  })

  const { data: activity, isLoading: activityLoading } = useQuery({
    queryKey: ['dashboard-activity'],
    queryFn: () => dashboardApi.getRecentActivity(),
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Dashboard</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Overview of your billing platform
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Customers"
          value={stats?.total_customers.toLocaleString() ?? '-'}
          description="total"
          icon={Users}
          loading={statsLoading}
        />
        <StatCard
          title="Active Subscriptions"
          value={stats?.active_subscriptions.toLocaleString() ?? '-'}
          description="currently active"
          icon={CreditCard}
          loading={statsLoading}
        />
        <StatCard
          title="Monthly Revenue"
          value={
            stats
              ? formatCurrency(stats.monthly_recurring_revenue * 100, stats.currency)
              : '-'
          }
          description="last 30 days"
          icon={DollarSign}
          mono
          loading={statsLoading}
        />
        <StatCard
          title="Total Invoiced"
          value={
            stats
              ? formatCurrency(stats.total_invoiced * 100, stats.currency)
              : '-'
          }
          description="all time"
          icon={FileText}
          mono
          loading={statsLoading}
        />
      </div>

      {/* Activity & Chart */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        {/* Revenue Chart Placeholder */}
        <Card className="col-span-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Revenue Overview</CardTitle>
          </CardHeader>
          <CardContent className="h-[280px] flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <TrendingUp className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">Chart coming soon</p>
            </div>
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
                {activity.map((item) => {
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
    </div>
  )
}
