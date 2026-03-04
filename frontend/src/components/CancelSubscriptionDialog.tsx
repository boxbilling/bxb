import { useState } from 'react'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import type { Subscription, TerminationAction } from '@/lib/api'

interface CancelSubscriptionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscription: Subscription | null
  onCancel: (id: string, action: TerminationAction) => void
  isLoading: boolean
}

export function CancelSubscriptionDialog({
  open,
  onOpenChange,
  subscription,
  onCancel,
  isLoading,
}: CancelSubscriptionDialogProps) {
  const [action, setAction] = useState<TerminationAction>('generate_invoice')

  if (!subscription) return null

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Cancel Subscription</AlertDialogTitle>
          <AlertDialogDescription>
            This will cancel the subscription. Choose what should happen with the remaining billing period.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="py-4 space-y-3">
          <Label>Financial Action</Label>
          <Select value={action} onValueChange={(v: TerminationAction) => setAction(v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="generate_invoice">Generate final invoice</SelectItem>
              <SelectItem value="generate_credit_note">Generate credit note (refund)</SelectItem>
              <SelectItem value="skip">Skip (no financial action)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>Go Back</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => onCancel(subscription.id, action)}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isLoading ? 'Canceling...' : 'Cancel Subscription'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
