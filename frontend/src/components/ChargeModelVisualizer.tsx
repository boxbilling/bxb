import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import type { Charge } from '@/types/billing'

interface TierData {
  label: string
  unitPrice: number
  flatAmount: number
}

function extractGraduatedTiers(properties: Record<string, unknown>): TierData[] {
  const ranges = properties.graduated_ranges as Array<Record<string, unknown>> | undefined
  if (ranges?.length) {
    return ranges.map((r) => {
      const from = Number(r.from_value ?? 0)
      const to = r.to_value != null ? Number(r.to_value) : null
      return {
        label: to != null ? `${from}–${to}` : `${from}+`,
        unitPrice: Number(r.per_unit_amount ?? 0),
        flatAmount: Number(r.flat_amount ?? 0),
      }
    })
  }

  const tiers = properties.tiers as Array<Record<string, unknown>> | undefined
  if (tiers?.length) {
    let prev = 0
    return tiers.map((t) => {
      const upTo = t.up_to != null ? Number(t.up_to) : null
      const label = upTo != null ? `${prev}–${upTo}` : `${prev}+`
      const result = {
        label,
        unitPrice: Number(t.unit_price ?? 0),
        flatAmount: Number(t.flat_amount ?? 0),
      }
      if (upTo != null) prev = upTo
      return result
    })
  }

  return []
}

function extractVolumeTiers(properties: Record<string, unknown>): TierData[] {
  const ranges = properties.volume_ranges as Array<Record<string, unknown>> | undefined
  if (ranges?.length) {
    return ranges.map((r) => {
      const from = Number(r.from_value ?? 0)
      const to = r.to_value != null ? Number(r.to_value) : null
      return {
        label: to != null ? `${from}–${to}` : `${from}+`,
        unitPrice: Number(r.per_unit_amount ?? 0),
        flatAmount: Number(r.flat_amount ?? 0),
      }
    })
  }

  const tiers = properties.tiers as Array<Record<string, unknown>> | undefined
  if (tiers?.length) {
    let prev = 0
    return tiers.map((t) => {
      const upTo = t.up_to != null ? Number(t.up_to) : null
      const label = upTo != null ? `${prev}–${upTo}` : `${prev}+`
      const result = {
        label,
        unitPrice: Number(t.unit_price ?? 0),
        flatAmount: Number(t.flat_amount ?? 0),
      }
      if (upTo != null) prev = upTo
      return result
    })
  }

  return []
}

function extractGraduatedPercentageTiers(
  properties: Record<string, unknown>
): { label: string; rate: number; flatAmount: number }[] {
  const ranges = properties.graduated_percentage_ranges as
    | Array<Record<string, unknown>>
    | undefined
  if (!ranges?.length) return []

  return ranges.map((r) => {
    const from = Number(r.from_value ?? 0)
    const to = r.to_value != null ? Number(r.to_value) : null
    return {
      label: to != null ? `${from}–${to}` : `${from}+`,
      rate: Number(r.rate ?? 0),
      flatAmount: Number(r.flat_amount ?? 0),
    }
  })
}

const TIER_COLORS = [
  'hsl(var(--primary))',
  'hsl(var(--chart-2, 160 60% 45%))',
  'hsl(var(--chart-3, 30 80% 55%))',
  'hsl(var(--chart-4, 280 65% 60%))',
  'hsl(var(--chart-5, 340 75% 55%))',
  'hsl(200 70% 50%)',
]

const chartConfig = {
  unitPrice: {
    label: 'Unit Price',
    color: 'hsl(var(--primary))',
  },
  rate: {
    label: 'Rate (%)',
    color: 'hsl(var(--primary))',
  },
} satisfies ChartConfig

function GraduatedChart({ tiers }: { tiers: TierData[] }) {
  const data = tiers.map((t) => ({
    tier: t.label,
    unitPrice: t.unitPrice,
    flatAmount: t.flatAmount,
  }))

  return (
    <ChartContainer config={chartConfig} className="h-[180px] w-full">
      <BarChart data={data} accessibilityLayer>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="tier"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          fontSize={11}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(v) => `$${v}`}
          fontSize={11}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value, name) =>
                name === 'unitPrice'
                  ? `$${Number(value).toFixed(2)}/unit`
                  : `$${Number(value).toFixed(2)} flat`
              }
            />
          }
        />
        <Bar dataKey="unitPrice" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => (
            <Cell
              key={`cell-${i}`}
              fill={TIER_COLORS[i % TIER_COLORS.length]}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}

function VolumeChart({ tiers }: { tiers: TierData[] }) {
  const data = tiers.map((t) => ({
    tier: t.label,
    unitPrice: t.unitPrice,
  }))

  return (
    <ChartContainer config={chartConfig} className="h-[180px] w-full">
      <BarChart data={data} accessibilityLayer>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="tier"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          fontSize={11}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(v) => `$${v}`}
          fontSize={11}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value) => `$${Number(value).toFixed(2)}/unit`}
            />
          }
        />
        <Bar dataKey="unitPrice" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => (
            <Cell
              key={`cell-${i}`}
              fill={TIER_COLORS[i % TIER_COLORS.length]}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}

function GraduatedPercentageChart({
  tiers,
}: {
  tiers: { label: string; rate: number; flatAmount: number }[]
}) {
  const data = tiers.map((t) => ({
    tier: t.label,
    rate: t.rate,
  }))

  return (
    <ChartContainer config={chartConfig} className="h-[180px] w-full">
      <BarChart data={data} accessibilityLayer>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="tier"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          fontSize={11}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(v) => `${v}%`}
          fontSize={11}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value) => `${Number(value).toFixed(2)}%`}
            />
          }
        />
        <Bar dataKey="rate" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => (
            <Cell
              key={`cell-${i}`}
              fill={TIER_COLORS[i % TIER_COLORS.length]}
            />
          ))}
        </Bar>
      </BarChart>
    </ChartContainer>
  )
}

function StandardSummary({ properties }: { properties: Record<string, unknown> }) {
  const amount = Number(properties.amount ?? properties.unit_price ?? 0)
  return (
    <div className="text-sm text-muted-foreground text-center py-6">
      <span className="text-2xl font-semibold text-foreground">
        ${amount.toFixed(2)}
      </span>
      <span className="ml-1">per unit</span>
    </div>
  )
}

function PackageSummary({ properties }: { properties: Record<string, unknown> }) {
  const amount = Number(properties.amount ?? properties.unit_price ?? 0)
  const packageSize = Number(properties.package_size ?? 1)
  const freeUnits = Number(properties.free_units ?? 0)
  return (
    <div className="text-sm text-muted-foreground text-center py-6 space-y-1">
      <div>
        <span className="text-2xl font-semibold text-foreground">
          ${amount.toFixed(2)}
        </span>
        <span className="ml-1">per {packageSize} units</span>
      </div>
      {freeUnits > 0 && (
        <div className="text-xs">
          First {freeUnits} units free
        </div>
      )}
    </div>
  )
}

function PercentageSummary({ properties }: { properties: Record<string, unknown> }) {
  const rate = Number(properties.rate ?? properties.percentage ?? 0)
  const fixedAmount = Number(properties.fixed_amount ?? 0)
  const freeEvents = Number(properties.free_units_per_events ?? 0)
  const minAmount = properties.per_transaction_min_amount != null
    ? Number(properties.per_transaction_min_amount)
    : null
  const maxAmount = properties.per_transaction_max_amount != null
    ? Number(properties.per_transaction_max_amount)
    : null

  return (
    <div className="text-sm text-muted-foreground text-center py-6 space-y-1">
      <div>
        <span className="text-2xl font-semibold text-foreground">
          {rate}%
        </span>
        <span className="ml-1">of transaction amount</span>
      </div>
      {fixedAmount > 0 && (
        <div className="text-xs">+ ${fixedAmount.toFixed(2)} per event</div>
      )}
      {freeEvents > 0 && (
        <div className="text-xs">First {freeEvents} events free</div>
      )}
      {(minAmount != null || maxAmount != null) && (
        <div className="text-xs">
          {minAmount != null && `Min: $${minAmount.toFixed(2)}`}
          {minAmount != null && maxAmount != null && ' · '}
          {maxAmount != null && `Max: $${maxAmount.toFixed(2)}`}
        </div>
      )}
    </div>
  )
}

export function ChargeModelVisualizer({ charge }: { charge: Charge }) {
  const props = (charge.properties ?? {}) as Record<string, unknown>
  const model = charge.charge_model

  let content: React.ReactNode = null
  let title = 'Pricing'

  if (model === 'graduated') {
    const tiers = extractGraduatedTiers(props)
    if (tiers.length > 0) {
      title = 'Graduated Pricing Tiers'
      content = <GraduatedChart tiers={tiers} />
    }
  } else if (model === 'volume') {
    const tiers = extractVolumeTiers(props)
    if (tiers.length > 0) {
      title = 'Volume Pricing Tiers'
      content = <VolumeChart tiers={tiers} />
    }
  } else if (model === 'graduated_percentage') {
    const tiers = extractGraduatedPercentageTiers(props)
    if (tiers.length > 0) {
      title = 'Graduated Percentage Tiers'
      content = <GraduatedPercentageChart tiers={tiers} />
    }
  } else if (model === 'standard') {
    title = 'Standard Pricing'
    content = <StandardSummary properties={props} />
  } else if (model === 'package') {
    title = 'Package Pricing'
    content = <PackageSummary properties={props} />
  } else if (model === 'percentage') {
    title = 'Percentage Pricing'
    content = <PercentageSummary properties={props} />
  }

  if (!content) return null

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
