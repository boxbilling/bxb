import { useMemo, useCallback } from 'react'
import { Trash2, Plus } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import type { ChargeModel } from '@/lib/api'

interface ChargePropertiesEditorProps {
  chargeModel: ChargeModel
  value: string
  onChange: (json: string) => void
}

function parseProps(value: string): Record<string, unknown> {
  try {
    return JSON.parse(value)
  } catch {
    return {}
  }
}

function emit(obj: Record<string, unknown>, onChange: (json: string) => void) {
  onChange(JSON.stringify(obj, null, 2))
}

// --- Sub-editors ---

function StandardFields({ props, onChange }: { props: Record<string, unknown>; onChange: (json: string) => void }) {
  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Label>Amount per unit</Label>
        <Input
          type="number"
          step={0.01}
          value={(props.amount as number) ?? ''}
          onChange={(e) => emit({ ...props, amount: e.target.value === '' ? '' : Number(e.target.value) }, onChange)}
          placeholder="0.00"
        />
      </div>
    </div>
  )
}

function PackageFields({ props, onChange }: { props: Record<string, unknown>; onChange: (json: string) => void }) {
  const fields = [
    { key: 'amount', label: 'Amount per package' },
    { key: 'package_size', label: 'Package size (units)' },
    { key: 'free_units', label: 'Free units' },
  ]
  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.key} className="space-y-2">
          <Label>{f.label}</Label>
          <Input
            type="number"
            step={0.01}
            value={(props[f.key] as number) ?? ''}
            onChange={(e) => emit({ ...props, [f.key]: e.target.value === '' ? '' : Number(e.target.value) }, onChange)}
            placeholder="0"
          />
        </div>
      ))}
    </div>
  )
}

function PercentageFields({ props, onChange }: { props: Record<string, unknown>; onChange: (json: string) => void }) {
  const fields = [
    { key: 'rate', label: 'Rate %', step: 0.01 },
    { key: 'fixed_amount', label: 'Fixed amount per event', step: 0.01 },
    { key: 'free_units_per_events', label: 'Free events', step: 1 },
    { key: 'per_transaction_min_amount', label: 'Min amount per transaction', step: 0.01 },
    { key: 'per_transaction_max_amount', label: 'Max amount per transaction', step: 0.01 },
  ]
  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.key} className="space-y-2">
          <Label>{f.label}</Label>
          <Input
            type="number"
            step={f.step}
            value={(props[f.key] as number) ?? ''}
            onChange={(e) => emit({ ...props, [f.key]: e.target.value === '' ? '' : Number(e.target.value) }, onChange)}
            placeholder="0"
          />
        </div>
      ))}
    </div>
  )
}

function DynamicFields({ props, onChange }: { props: Record<string, unknown>; onChange: (json: string) => void }) {
  const fields = [
    { key: 'price_field', label: 'Price field name' },
    { key: 'quantity_field', label: 'Quantity field name' },
  ]
  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.key} className="space-y-2">
          <Label>{f.label}</Label>
          <Input
            type="text"
            value={(props[f.key] as string) ?? ''}
            onChange={(e) => emit({ ...props, [f.key]: e.target.value }, onChange)}
          />
        </div>
      ))}
    </div>
  )
}

function CustomFields({ props, onChange }: { props: Record<string, unknown>; onChange: (json: string) => void }) {
  const fields = [
    { key: 'custom_amount', label: 'Custom amount' },
    { key: 'unit_price', label: 'Unit price' },
  ]
  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.key} className="space-y-2">
          <Label>{f.label}</Label>
          <Input
            type="number"
            step={0.01}
            value={(props[f.key] as number) ?? ''}
            onChange={(e) => emit({ ...props, [f.key]: e.target.value === '' ? '' : Number(e.target.value) }, onChange)}
            placeholder="0"
          />
        </div>
      ))}
    </div>
  )
}

// --- Tier Builders ---

interface Tier {
  up_to: number | null
  unit_price: number
  flat_amount: number
}

function TierBuilder({ props, onChange }: { props: Record<string, unknown>; onChange: (json: string) => void }) {
  const tiers: Tier[] = useMemo(() => {
    const raw = props.tiers
    if (Array.isArray(raw) && raw.length > 0) return raw as Tier[]
    return [{ up_to: null, unit_price: 0, flat_amount: 0 }]
  }, [props.tiers])

  const emitTiers = useCallback(
    (newTiers: Tier[]) => emit({ tiers: newTiers }, onChange),
    [onChange],
  )

  const updateTier = (index: number, field: keyof Tier, value: number | null) => {
    const newTiers = tiers.map((t, i) => (i === index ? { ...t, [field]: value } : t))
    emitTiers(newTiers)
  }

  const addTier = () => {
    const newTiers = [...tiers]
    const lastIdx = newTiers.length - 1
    const prevUpTo = lastIdx > 0 ? (newTiers[lastIdx - 1].up_to ?? 0) : 0
    // Give the current last tier a numeric up_to
    newTiers[lastIdx] = { ...newTiers[lastIdx], up_to: prevUpTo + 100 }
    // Add new open-ended tier
    newTiers.push({ up_to: null, unit_price: 0, flat_amount: 0 })
    emitTiers(newTiers)
  }

  const removeTier = (index: number) => {
    if (tiers.length <= 1) return
    const newTiers = tiers.filter((_, i) => i !== index)
    // Ensure last tier is open-ended
    newTiers[newTiers.length - 1] = { ...newTiers[newTiers.length - 1], up_to: null }
    emitTiers(newTiers)
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 items-center">
        <Label className="text-xs text-muted-foreground">Up to (units)</Label>
        <Label className="text-xs text-muted-foreground">Unit price</Label>
        <Label className="text-xs text-muted-foreground">Flat amount</Label>
        <div className="w-7" />
        {tiers.map((tier, index) => (
          <>
            <Input
              key={`up_to_${index}`}
              type="text"
              value={tier.up_to === null ? '∞' : tier.up_to}
              disabled={tier.up_to === null}
              onChange={(e) => {
                const v = e.target.value === '' ? 0 : Number(e.target.value)
                updateTier(index, 'up_to', isNaN(v) ? 0 : v)
              }}
            />
            <Input
              key={`unit_price_${index}`}
              type="number"
              step={0.01}
              value={tier.unit_price}
              onChange={(e) => updateTier(index, 'unit_price', Number(e.target.value))}
            />
            <Input
              key={`flat_amount_${index}`}
              type="number"
              step={0.01}
              value={tier.flat_amount}
              onChange={(e) => updateTier(index, 'flat_amount', Number(e.target.value))}
            />
            <Button
              key={`remove_${index}`}
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-destructive"
              disabled={tiers.length <= 1}
              onClick={() => removeTier(index)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </>
        ))}
      </div>
      <Button type="button" variant="outline" size="sm" onClick={addTier}>
        <Plus className="mr-2 h-4 w-4" />
        Add tier
      </Button>
    </div>
  )
}

interface GradPercentRange {
  from_value: number
  to_value: number | null
  rate: number
  flat_amount: number
}

function GraduatedPercentageTierBuilder({ props, onChange }: { props: Record<string, unknown>; onChange: (json: string) => void }) {
  const ranges: GradPercentRange[] = useMemo(() => {
    const raw = props.graduated_percentage_ranges
    if (Array.isArray(raw) && raw.length > 0) return raw as GradPercentRange[]
    return [{ from_value: 0, to_value: null, rate: 0, flat_amount: 0 }]
  }, [props.graduated_percentage_ranges])

  const emitRanges = useCallback(
    (newRanges: GradPercentRange[]) => emit({ graduated_percentage_ranges: newRanges }, onChange),
    [onChange],
  )

  const updateRange = (index: number, field: keyof GradPercentRange, value: number | null) => {
    const newRanges = ranges.map((r, i) => {
      if (i !== index) return r
      const updated = { ...r, [field]: value }
      return updated
    })
    // Auto-fill from_value for subsequent ranges
    for (let i = 1; i < newRanges.length; i++) {
      const prevTo = newRanges[i - 1].to_value
      newRanges[i] = { ...newRanges[i], from_value: prevTo ?? 0 }
    }
    emitRanges(newRanges)
  }

  const addRange = () => {
    const newRanges = [...ranges]
    const lastIdx = newRanges.length - 1
    const prevTo = lastIdx > 0 ? (newRanges[lastIdx - 1].to_value ?? 0) : 0
    const currentTo = prevTo + 1000
    newRanges[lastIdx] = { ...newRanges[lastIdx], to_value: currentTo }
    newRanges.push({ from_value: currentTo, to_value: null, rate: 0, flat_amount: 0 })
    emitRanges(newRanges)
  }

  const removeRange = (index: number) => {
    if (ranges.length <= 1) return
    const newRanges = ranges.filter((_, i) => i !== index)
    newRanges[newRanges.length - 1] = { ...newRanges[newRanges.length - 1], to_value: null }
    // Re-fill from_values
    for (let i = 1; i < newRanges.length; i++) {
      const prevTo = newRanges[i - 1].to_value
      newRanges[i] = { ...newRanges[i], from_value: prevTo ?? 0 }
    }
    emitRanges(newRanges)
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-[1fr_1fr_1fr_1fr_auto] gap-2 items-center">
        <Label className="text-xs text-muted-foreground">From value</Label>
        <Label className="text-xs text-muted-foreground">To value</Label>
        <Label className="text-xs text-muted-foreground">Rate (%)</Label>
        <Label className="text-xs text-muted-foreground">Flat amount</Label>
        <div className="w-7" />
        {ranges.map((range, index) => (
          <>
            <Input
              key={`from_${index}`}
              type="number"
              value={range.from_value}
              disabled
            />
            <Input
              key={`to_${index}`}
              type="text"
              value={range.to_value === null ? '∞' : range.to_value}
              disabled={range.to_value === null}
              onChange={(e) => {
                const v = e.target.value === '' ? 0 : Number(e.target.value)
                updateRange(index, 'to_value', isNaN(v) ? 0 : v)
              }}
            />
            <Input
              key={`rate_${index}`}
              type="number"
              step={0.01}
              value={range.rate}
              onChange={(e) => updateRange(index, 'rate', Number(e.target.value))}
            />
            <Input
              key={`flat_${index}`}
              type="number"
              step={0.01}
              value={range.flat_amount}
              onChange={(e) => updateRange(index, 'flat_amount', Number(e.target.value))}
            />
            <Button
              key={`remove_${index}`}
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-destructive"
              disabled={ranges.length <= 1}
              onClick={() => removeRange(index)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </>
        ))}
      </div>
      <Button type="button" variant="outline" size="sm" onClick={addRange}>
        <Plus className="mr-2 h-4 w-4" />
        Add tier
      </Button>
    </div>
  )
}

// --- Main Component ---

export function ChargePropertiesEditor({ chargeModel, value, onChange }: ChargePropertiesEditorProps) {
  const props = useMemo(() => parseProps(value), [value])

  switch (chargeModel) {
    case 'standard':
      return <StandardFields props={props} onChange={onChange} />
    case 'package':
      return <PackageFields props={props} onChange={onChange} />
    case 'percentage':
      return <PercentageFields props={props} onChange={onChange} />
    case 'dynamic':
      return <DynamicFields props={props} onChange={onChange} />
    case 'custom':
      return <CustomFields props={props} onChange={onChange} />
    case 'graduated':
    case 'volume':
      return <TierBuilder props={props} onChange={onChange} />
    case 'graduated_percentage':
      return <GraduatedPercentageTierBuilder props={props} onChange={onChange} />
    default:
      return null
  }
}
