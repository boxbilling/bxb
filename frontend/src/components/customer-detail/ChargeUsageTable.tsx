import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatCents } from '@/lib/utils'
import type { CustomerCurrentUsageResponse } from '@/types/billing'

export function ChargeUsageTable({ charges, currency }: { charges: CustomerCurrentUsageResponse['charges']; currency: string }) {
  if (!charges.length) {
    return <p className="text-sm text-muted-foreground py-2">No charge data</p>
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Metric</TableHead>
            <TableHead>Units</TableHead>
            <TableHead>Charge Model</TableHead>
            <TableHead className="text-right">Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {charges.map((charge, idx) => (
            <TableRow key={`${charge.billable_metric.code}-${idx}`}>
              <TableCell>
                <div>{charge.billable_metric.name}</div>
                <div className="text-xs text-muted-foreground">{charge.billable_metric.code}</div>
              </TableCell>
              <TableCell className="font-mono">{charge.units}</TableCell>
              <TableCell>
                <Badge variant="outline">{charge.charge_model}</Badge>
              </TableCell>
              <TableCell className="text-right font-mono">{formatCents(Number(charge.amount_cents), currency)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
