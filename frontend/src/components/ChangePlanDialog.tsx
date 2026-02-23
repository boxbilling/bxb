import { useState } from 'react'
import { format } from 'date-fns'
import { CalendarIcon, ArrowRight, TrendingUp, TrendingDown, Minus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { subscriptionsApi } from '@/lib/api'
import type { Subscription, Plan, ChangePlanPreviewResponse } from '@/lib/api'
import { formatCents } from '@/lib/utils'

interface ChangePlanDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscription: Subscription | null
  plans: Plan[]
  onSubmit: (subscriptionId: string, newPlanId: string, effectiveDate?: string) => void
  isLoading: boolean
}

export function ChangePlanDialog({
  open,
  onOpenChange,
  subscription,
  plans,
  onSubmit,
  isLoading,
}: ChangePlanDialogProps) {
  const [selectedPlanId, setSelectedPlanId] = useState('')
  const [effectiveDate, setEffectiveDate] = useState<Date | undefined>(undefined)
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [preview, setPreview] = useState<ChangePlanPreviewResponse | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const currentPlan = subscription ? plans.find(p => p.id === subscription.plan_id) : null
  const newPlan = selectedPlanId ? plans.find(p => p.id === selectedPlanId) : null

  // Fetch preview when plan is selected
  const fetchPreview = async (planId: string, date?: Date) => {
    if (!subscription) return
    setPreviewLoading(true)
    try {
      const result = await subscriptionsApi.changePlanPreview(subscription.id, {
        new_plan_id: planId,
        effective_date: date?.toISOString() ?? null,
      })
      setPreview(result)
    } catch {
      setPreview(null)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handlePlanChange = (planId: string) => {
    setSelectedPlanId(planId)
    if (planId) fetchPreview(planId, effectiveDate)
    else setPreview(null)
  }

  const handleDateChange = (date: Date | undefined) => {
    setEffectiveDate(date)
    setCalendarOpen(false)
    if (selectedPlanId) fetchPreview(selectedPlanId, date)
  }

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      setSelectedPlanId('')
      setEffectiveDate(undefined)
      setPreview(null)
    }
    onOpenChange(isOpen)
  }

  if (!subscription) return null

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Change Plan</DialogTitle>
          <DialogDescription>
            Upgrade or downgrade the subscription to a different plan
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          {/* Plan Selection */}
          <div className="space-y-2">
            <Label>New Plan *</Label>
            <Select value={selectedPlanId} onValueChange={handlePlanChange}>
              <SelectTrigger>
                <SelectValue placeholder="Select a new plan" />
              </SelectTrigger>
              <SelectContent>
                {plans
                  .filter(p => p.id !== subscription.plan_id)
                  .map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} — {formatCents(p.amount_cents, p.currency)}/{p.interval}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          {/* Effective Date Picker */}
          <div className="space-y-2">
            <Label>Effective Date</Label>
            <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-full justify-start text-left font-normal">
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {effectiveDate ? format(effectiveDate, 'MMM d, yyyy') : 'Immediately (now)'}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={effectiveDate}
                  onSelect={handleDateChange}
                  disabled={(date) => date < new Date(new Date().setHours(0, 0, 0, 0))}
                />
                {effectiveDate && (
                  <div className="border-t p-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="w-full"
                      onClick={() => handleDateChange(undefined)}
                    >
                      Clear (use now)
                    </Button>
                  </div>
                )}
              </PopoverContent>
            </Popover>
            <p className="text-xs text-muted-foreground">
              Leave empty to apply the change immediately
            </p>
          </div>

          {/* Price Comparison */}
          {selectedPlanId && currentPlan && newPlan && (
            <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
              <p className="text-sm font-medium">Price Comparison</p>
              <div className="flex items-center gap-3">
                <div className="flex-1 rounded-md border bg-background p-3 text-center">
                  <p className="text-xs text-muted-foreground mb-1">Current</p>
                  <p className="font-semibold">{currentPlan.name}</p>
                  <p className="text-lg font-mono">
                    {formatCents(currentPlan.amount_cents, currentPlan.currency)}
                  </p>
                  <p className="text-xs text-muted-foreground">/{currentPlan.interval}</p>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                <div className="flex-1 rounded-md border bg-background p-3 text-center">
                  <p className="text-xs text-muted-foreground mb-1">New</p>
                  <p className="font-semibold">{newPlan.name}</p>
                  <p className="text-lg font-mono">
                    {formatCents(newPlan.amount_cents, newPlan.currency)}
                  </p>
                  <p className="text-xs text-muted-foreground">/{newPlan.interval}</p>
                </div>
              </div>
              {/* Price difference indicator */}
              {(() => {
                const diff = newPlan.amount_cents - currentPlan.amount_cents
                if (diff === 0) return (
                  <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <Minus className="h-3.5 w-3.5" />
                    Same base price
                  </div>
                )
                return (
                  <div className={`flex items-center gap-1.5 text-sm ${diff > 0 ? 'text-orange-600' : 'text-green-600'}`}>
                    {diff > 0 ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
                    {diff > 0 ? 'Upgrade' : 'Downgrade'}: {diff > 0 ? '+' : ''}{formatCents(diff, newPlan.currency)}/{newPlan.interval}
                  </div>
                )
              })()}
            </div>
          )}

          {/* Proration Preview */}
          {previewLoading && (
            <div className="rounded-lg border p-4">
              <div className="space-y-2 animate-pulse">
                <div className="h-4 w-32 bg-muted rounded" />
                <div className="h-3 w-full bg-muted rounded" />
                <div className="h-3 w-3/4 bg-muted rounded" />
              </div>
            </div>
          )}
          {preview && !previewLoading && (
            <div className="rounded-lg border p-4 space-y-2">
              <p className="text-sm font-medium">Proration Preview</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <span className="text-muted-foreground">Days remaining in period</span>
                <span className="text-right font-mono">
                  {preview.proration.days_remaining} / {preview.proration.total_days}
                </span>
                <span className="text-muted-foreground">Credit for current plan</span>
                <span className="text-right font-mono text-green-600">
                  -{formatCents(preview.proration.current_plan_credit_cents, preview.current_plan.currency)}
                </span>
                <span className="text-muted-foreground">Charge for new plan</span>
                <span className="text-right font-mono">
                  +{formatCents(preview.proration.new_plan_charge_cents, preview.new_plan.currency)}
                </span>
              </div>
              <div className="border-t pt-2 mt-2 flex justify-between text-sm font-medium">
                <span>Net adjustment</span>
                <span className={`font-mono ${preview.proration.net_amount_cents > 0 ? 'text-orange-600' : preview.proration.net_amount_cents < 0 ? 'text-green-600' : ''}`}>
                  {preview.proration.net_amount_cents >= 0 ? '+' : ''}{formatCents(preview.proration.net_amount_cents, preview.current_plan.currency)}
                </span>
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>Cancel</Button>
          <Button
            disabled={!selectedPlanId || isLoading}
            onClick={() => onSubmit(subscription.id, selectedPlanId, effectiveDate?.toISOString())}
          >
            {isLoading ? 'Changing...' : 'Change Plan'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
