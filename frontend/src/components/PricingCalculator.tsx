import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Calculator } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { plansApi, ApiError } from '@/lib/api'
import type { BillableMetric, PlanSimulateResponse } from '@/types/billing'

function formatCurrency(cents: number, currency: string = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
  }).format(cents / 100)
}

export function PricingCalculator({
  planId,
  currency,
  metricMap,
}: {
  planId: string
  currency: string
  metricMap: Map<string, BillableMetric>
}) {
  const [units, setUnits] = useState('')
  const [result, setResult] = useState<PlanSimulateResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const simulateMutation = useMutation({
    mutationFn: (unitsValue: number) =>
      plansApi.simulate(planId, { units: unitsValue }),
    onSuccess: (data) => {
      setResult(data)
      setError(null)
    },
    onError: (err) => {
      setResult(null)
      setError(
        err instanceof ApiError ? err.message : 'Failed to simulate pricing'
      )
    },
  })

  const handleSimulate = (e: React.FormEvent) => {
    e.preventDefault()
    const unitsValue = parseFloat(units)
    if (isNaN(unitsValue) || unitsValue < 0) {
      setError('Please enter a valid number of units')
      return
    }
    simulateMutation.mutate(unitsValue)
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Calculator className="h-4 w-4" />
          Pricing Calculator
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleSimulate} className="flex items-end gap-3">
          <div className="space-y-1 flex-1">
            <Label className="text-xs">Usage Units</Label>
            <Input
              type="number"
              min="0"
              step="any"
              placeholder="e.g. 1000"
              value={units}
              onChange={(e) => setUnits(e.target.value)}
              required
            />
          </div>
          <Button
            type="submit"
            size="sm"
            disabled={simulateMutation.isPending}
          >
            {simulateMutation.isPending ? 'Calculating...' : 'Calculate'}
          </Button>
        </form>

        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}

        {result && (
          <div className="space-y-3">
            <Separator />
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Charge</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead className="text-right">Units</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow className="bg-muted/30">
                    <TableCell className="font-medium" colSpan={2}>
                      Base price
                    </TableCell>
                    <TableCell className="text-right">—</TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(result.base_amount_cents, currency)}
                    </TableCell>
                  </TableRow>
                  {result.charges.map((charge) => {
                    const metric = metricMap.get(charge.billable_metric_id)
                    return (
                      <TableRow key={charge.charge_id}>
                        <TableCell className="font-medium">
                          {metric?.name ?? 'Unknown metric'}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">
                            {charge.charge_model}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {charge.units.toLocaleString()}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {formatCurrency(charge.amount_cents, currency)}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>

            <div className="flex items-center justify-between px-2 py-2 bg-muted/50 rounded-md">
              <span className="text-sm font-medium">Total</span>
              <span className="text-lg font-semibold font-mono">
                {formatCurrency(result.total_amount_cents, currency)}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
