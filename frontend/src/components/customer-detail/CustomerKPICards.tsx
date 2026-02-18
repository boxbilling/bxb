import { useQuery } from '@tanstack/react-query'
import { FileText } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { invoicesApi } from '@/lib/api'
import { formatCents } from '@/lib/utils'

export function CustomerKPICards({ customerId, currency }: { customerId: string; currency: string }) {
  const { data: invoices } = useQuery({
    queryKey: ['customer-invoices-balance', customerId],
    queryFn: () => invoicesApi.list({ customer_id: customerId }),
  })

  const outstanding = (invoices ?? [])
    .filter((i) => i.status === 'finalized')
    .reduce((sum, i) => sum + Number(i.total), 0)

  const overdue = (invoices ?? [])
    .filter((i) => i.status === 'finalized' && i.due_date && new Date(i.due_date) < new Date())
    .reduce((sum, i) => sum + Number(i.total), 0)

  return (
    <div className="grid grid-cols-2 gap-3 md:gap-4">
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
    </div>
  )
}
