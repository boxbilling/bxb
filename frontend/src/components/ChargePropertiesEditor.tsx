import { useState, useMemo, useCallback } from 'react'
import { Trash2, Plus, ChevronDown, ChevronUp } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible'
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
          min={0}
          value={(props.amount as number) ?? ''}
          onChange={(e) => emit({ ...props, amount: e.target.value === '' ? '' : Number(e.target.value) }, onChange)}
          placeholder="0.00"
        />
        <p className="text-xs text-muted-foreground">Price charged per single unit of usage</p>
      </div>
    </div>
  )
}

function PackageFields({ props, onChange }: { props: Record<string, unknown>; onChange: (json: string) => void }) {
  const fields = [
    { key: 'amount', label: 'Amount per package', step: 0.01, hint: 'Price charged per package of units' },
    { key: 'package_size', label: 'Package size (units)', step: 1, hint: 'Number of units in each package' },
    { key: 'free_units', label: 'Free units', step: 1, hint: 'Units included at no charge before billing starts' },
  ]
  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.key} className="space-y-2">
          <Label>{f.label}</Label>
          <Input
            type="number"
            step={f.step}
            min={0}
            value={(props[f.key] as number) ?? ''}
            onChange={(e) => emit({ ...props, [f.key]: e.target.value === '' ? '' : Number(e.target.value) }, onChange)}
            placeholder="0"
          />
          <p className="text-xs text-muted-foreground">{f.hint}</p>
        </div>
      ))}
    </div>
  )
}

function PercentageFields({ props, onChange }: { props: Record<string, unknown>; onChange: (json: string) => void }) {
  const fields = [
    { key: 'rate', label: 'Rate %', step: 0.01, hint: 'Percentage of transaction amount to charge (0-100)' },
    { key: 'fixed_amount', label: 'Fixed amount per event', step: 0.01, hint: 'Additional fixed amount charged per event' },
    { key: 'free_units_per_events', label: 'Free events', step: 1, hint: 'Number of events before charges begin' },
    { key: 'per_transaction_min_amount', label: 'Min amount per transaction', step: 0.01, hint: 'Minimum charge per transaction (leave empty for none)' },
    { key: 'per_transaction_max_amount', label: 'Max amount per transaction', step: 0.01, hint: 'Maximum charge per transaction (leave empty for none)' },
  ]
  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.key} className="space-y-2">
          <Label>{f.label}</Label>
          <Input
            type="number"
            step={f.step}
            min={0}
            value={(props[f.key] as number) ?? ''}
            onChange={(e) => emit({ ...props, [f.key]: e.target.value === '' ? '' : Number(e.target.value) }, onChange)}
            placeholder="0"
          />
          <p className="text-xs text-muted-foreground">{f.hint}</p>
        </div>
      ))}
    </div>
  )
}

function DynamicFields({ props, onChange }: { props: Record<string, unknown>; onChange: (json: string) => void }) {
  const fields = [
    { key: 'price_field', label: 'Price field name', hint: 'Name of the event property containing the price' },
    { key: 'quantity_field', label: 'Quantity field name', hint: 'Name of the event property containing the quantity' },
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
          <p className="text-xs text-muted-foreground">{f.hint}</p>
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
            min={0}
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

function TierBuilder({ props, onChange, chargeModel }: { props: Record<string, unknown>; onChange: (json: string) => void; chargeModel: 'graduated' | 'volume' }) {
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

  const description = chargeModel === 'graduated'
    ? "Define pricing tiers \u2014 each tier's rate applies only to units within that range"
    : "Define volume tiers \u2014 the tier matching total usage applies its rate to ALL units"

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">{description}</p>
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
              min={0}
              value={tier.unit_price}
              onChange={(e) => updateTier(index, 'unit_price', Number(e.target.value))}
            />
            <Input
              key={`flat_amount_${index}`}
              type="number"
              step={0.01}
              min={0}
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
      <p className="text-xs text-muted-foreground">Define percentage tiers &mdash; each tier&apos;s rate applies to the transaction amount within that range</p>
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
              min={0}
              value={range.rate}
              onChange={(e) => updateRange(index, 'rate', Number(e.target.value))}
            />
            <Input
              key={`flat_${index}`}
              type="number"
              step={0.01}
              min={0}
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

// --- Advanced JSON Toggle ---

function AdvancedJsonToggle({ value, onChange }: { value: string; onChange: (json: string) => void }) {
  const [open, setOpen] = useState(false)
  const [localJson, setLocalJson] = useState(value)
  const [jsonError, setJsonError] = useState(false)

  // Sync from structured form → JSON textarea when value changes externally
  const formattedValue = useMemo(() => {
    try {
      return JSON.stringify(JSON.parse(value), null, 2)
    } catch {
      return value
    }
  }, [value])

  // Update local JSON when the structured form changes (and textarea isn't focused with errors)
  if (!jsonError && localJson !== formattedValue) {
    setLocalJson(formattedValue)
  }

  const handleJsonChange = (text: string) => {
    setLocalJson(text)
    try {
      JSON.parse(text)
      setJsonError(false)
    } catch {
      setJsonError(true)
    }
  }

  const handleJsonBlur = () => {
    if (jsonError) return
    try {
      const parsed = JSON.parse(localJson)
      onChange(JSON.stringify(parsed, null, 2))
    } catch {
      // shouldn't happen since we checked above
    }
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <Button type="button" variant="ghost" size="sm" className="gap-1 text-xs">
          Advanced JSON
          {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-2 space-y-1">
          <Textarea
            className={`font-mono text-sm ${jsonError ? 'border-red-500' : ''}`}
            rows={4}
            value={localJson}
            onChange={(e) => handleJsonChange(e.target.value)}
            onBlur={handleJsonBlur}
          />
          {jsonError && (
            <p className="text-xs text-red-500">Invalid JSON</p>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

// --- Main Component ---

export function ChargePropertiesEditor({ chargeModel, value, onChange }: ChargePropertiesEditorProps) {
  const props = useMemo(() => parseProps(value), [value])

  let fields: React.ReactNode = null
  switch (chargeModel) {
    case 'standard':
      fields = <StandardFields props={props} onChange={onChange} />
      break
    case 'package':
      fields = <PackageFields props={props} onChange={onChange} />
      break
    case 'percentage':
      fields = <PercentageFields props={props} onChange={onChange} />
      break
    case 'dynamic':
      fields = <DynamicFields props={props} onChange={onChange} />
      break
    case 'custom':
      fields = <CustomFields props={props} onChange={onChange} />
      break
    case 'graduated':
    case 'volume':
      fields = <TierBuilder props={props} onChange={onChange} chargeModel={chargeModel} />
      break
    case 'graduated_percentage':
      fields = <GraduatedPercentageTierBuilder props={props} onChange={onChange} />
      break
    default:
      return null
  }

  return (
    <div className="space-y-3">
      {fields}
      <AdvancedJsonToggle value={value} onChange={onChange} />
    </div>
  )
}
