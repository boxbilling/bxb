import { useQuery } from '@tanstack/react-query'
import { FileText, ScrollText, TrendingUp } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { invoicesApi, subscriptionsApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'

export function CustomerKPICards({ customerId, currency }: { customerId: string; currency: string }) {
  const { data: invoices } = useQuery({
    queryKey: ['customer-invoices-balance', customerId],
    queryFn: () => invoicesApi.list({ customer_id: customerId }),
  })

  const { data: subscriptions } = useQuery({
    queryKey: ['customer-subscriptions', customerId],
    queryFn: () => subscriptionsApi.list({ customer_id: customerId }),
  })

  const outstanding = (invoices ?? [])
    .filter((i) => i.status === 'finalized')
    .reduce((sum, i) => sum + Number(i.total_cents), 0)

  const overdue = (invoices ?? [])
    .filter((i) => i.status === 'finalized' && i.due_date && new Date(i.due_date) < new Date())
    .reduce((sum, i) => sum + Number(i.total_cents), 0)

  const lifetimeRevenue = (invoices ?? [])
    .filter((i) => i.status === 'paid')
    .reduce((sum, i) => sum + Number(i.total_cents), 0)

  const activeSubscriptions = (subscriptions ?? []).filter((s) => s.status === 'active').length

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Outstanding Balance</CardTitle>
          <FileText className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-orange-600">{formatCents(outstanding, currency)}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {(invoices ?? []).filter((i) => i.status === 'finalized').length} unpaid invoice(s)
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Overdue Amount</CardTitle>
          <FileText className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${overdue > 0 ? 'text-red-600' : 'text-muted-foreground'}`}>
            {formatCents(overdue, currency)}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {(invoices ?? []).filter((i) => i.status === 'finalized' && i.due_date && new Date(i.due_date) < new Date()).length} overdue invoice(s)
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Lifetime Revenue</CardTitle>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formatCents(lifetimeRevenue, currency)}</div>
          <p className="text-xs text-muted-foreground mt-1">Total paid invoices</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Active Subscriptions</CardTitle>
          <ScrollText className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{activeSubscriptions}</div>
          <p className="text-xs text-muted-foreground mt-1">Currently active</p>
        </CardContent>
      </Card>
    </div>
  )
}
