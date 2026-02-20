import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, userEvent, waitFor } from '@/test/test-utils'

import { ChangePlanDialog } from './ChangePlanDialog'
import { buildSubscription, buildPlan } from '@/test/factories'
import type { ChangePlanPreviewResponse } from '@/types/billing'

const mockChangePlanPreview = vi.fn()

vi.mock('@/lib/api', () => ({
  subscriptionsApi: {
    changePlanPreview: (...args: unknown[]) => mockChangePlanPreview(...args),
  },
}))

describe('ChangePlanDialog', () => {
  const currentPlan = buildPlan({
    id: 'plan-current',
    name: 'Starter Monthly',
    code: 'starter_monthly',
    amount_cents: 4900,
    currency: 'usd',
    interval: 'monthly',
  })

  const upgradePlan = buildPlan({
    id: 'plan-upgrade',
    name: 'Pro Monthly',
    code: 'pro_monthly',
    amount_cents: 9900,
    currency: 'usd',
    interval: 'monthly',
  })

  const downgradePlan = buildPlan({
    id: 'plan-downgrade',
    name: 'Free',
    code: 'free',
    amount_cents: 0,
    currency: 'usd',
    interval: 'monthly',
  })

  const samePricePlan = buildPlan({
    id: 'plan-same',
    name: 'Starter Annual',
    code: 'starter_annual',
    amount_cents: 4900,
    currency: 'usd',
    interval: 'monthly',
  })

  const subscription = buildSubscription({
    id: 'sub-1',
    plan_id: 'plan-current',
    status: 'active',
  })

  const plans = [currentPlan, upgradePlan, downgradePlan, samePricePlan]

  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    subscription,
    plans,
    onSubmit: vi.fn(),
    isLoading: false,
  }

  const previewResponse: ChangePlanPreviewResponse = {
    current_plan: {
      id: 'plan-current',
      name: 'Starter Monthly',
      code: 'starter_monthly',
      amount_cents: 4900,
      currency: 'usd',
      interval: 'monthly',
    },
    new_plan: {
      id: 'plan-upgrade',
      name: 'Pro Monthly',
      code: 'pro_monthly',
      amount_cents: 9900,
      currency: 'usd',
      interval: 'monthly',
    },
    effective_date: '2024-02-01T00:00:00Z',
    proration: {
      days_remaining: 15,
      total_days: 30,
      current_plan_credit_cents: 2450,
      new_plan_charge_cents: 4950,
      net_amount_cents: 2500,
    },
  }

  beforeEach(() => {
    vi.restoreAllMocks()
    mockChangePlanPreview.mockResolvedValue(previewResponse)
  })

  // Helper to get the dialog title heading
  function getDialogTitle() {
    return screen.getByRole('heading', { name: 'Change Plan' })
  }

  // Helper to get the submit button (not the heading)
  function getSubmitButton() {
    return screen.getByRole('button', { name: /^Change Plan$|^Changing\.\.\.$/ })
  }

  describe('rendering', () => {
    it('renders dialog title and description', () => {
      render(<ChangePlanDialog {...defaultProps} />)
      expect(getDialogTitle()).toBeInTheDocument()
      expect(screen.getByText(/Upgrade or downgrade/)).toBeInTheDocument()
    })

    it('renders plan selection label', () => {
      render(<ChangePlanDialog {...defaultProps} />)
      expect(screen.getByText('New Plan *')).toBeInTheDocument()
    })

    it('renders effective date section', () => {
      render(<ChangePlanDialog {...defaultProps} />)
      expect(screen.getByText('Effective Date')).toBeInTheDocument()
      expect(screen.getByText('Immediately (now)')).toBeInTheDocument()
    })

    it('renders cancel and submit buttons', () => {
      render(<ChangePlanDialog {...defaultProps} />)
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
      expect(getSubmitButton()).toBeInTheDocument()
    })

    it('returns null when subscription is null', () => {
      const { container } = render(
        <ChangePlanDialog {...defaultProps} subscription={null} />
      )
      expect(container.querySelector('[role="dialog"]')).not.toBeInTheDocument()
    })
  })

  describe('plan selection', () => {
    it('filters out the current plan from options', async () => {
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      // Current plan (Starter Monthly) should NOT appear in options
      const options = screen.getAllByRole('option')
      const optionTexts = options.map(o => o.textContent)
      expect(optionTexts.some(t => t?.includes('Starter Monthly'))).toBe(false)
      // Other plans should appear
      expect(optionTexts.some(t => t?.includes('Pro Monthly'))).toBe(true)
      expect(optionTexts.some(t => t?.includes('Free'))).toBe(true)
    })

    it('fetches proration preview when a plan is selected', async () => {
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Pro Monthly/ }))
      await waitFor(() => {
        expect(mockChangePlanPreview).toHaveBeenCalledWith('sub-1', {
          new_plan_id: 'plan-upgrade',
          effective_date: null,
        })
      })
    })

    it('shows price comparison after selecting a plan', async () => {
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Pro Monthly/ }))
      await waitFor(() => {
        expect(screen.getByText('Price Comparison')).toBeInTheDocument()
      })
      expect(screen.getByText('Current')).toBeInTheDocument()
      expect(screen.getByText('New')).toBeInTheDocument()
    })

    it('shows upgrade indicator when new plan is more expensive', async () => {
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Pro Monthly/ }))
      await waitFor(() => {
        expect(screen.getByText(/Upgrade:/)).toBeInTheDocument()
      })
    })

    it('shows downgrade indicator when new plan is cheaper', async () => {
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Free/ }))
      await waitFor(() => {
        expect(screen.getByText(/Downgrade/)).toBeInTheDocument()
      })
    })

    it('shows same price indicator when plans cost the same', async () => {
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Starter Annual/ }))
      await waitFor(() => {
        expect(screen.getByText('Same base price')).toBeInTheDocument()
      })
    })
  })

  describe('proration preview', () => {
    it('shows proration preview after plan selection', async () => {
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Pro Monthly/ }))
      await waitFor(() => {
        expect(screen.getByText('Proration Preview')).toBeInTheDocument()
      })
      expect(screen.getByText('Days remaining in period')).toBeInTheDocument()
      expect(screen.getByText('15 / 30')).toBeInTheDocument()
      expect(screen.getByText('Credit for current plan')).toBeInTheDocument()
      expect(screen.getByText('Charge for new plan')).toBeInTheDocument()
      expect(screen.getByText('Net adjustment')).toBeInTheDocument()
    })

    it('does not show proration preview before selecting a plan', () => {
      render(<ChangePlanDialog {...defaultProps} />)
      expect(screen.queryByText('Proration Preview')).not.toBeInTheDocument()
    })

    it('handles preview API errors gracefully', async () => {
      mockChangePlanPreview.mockRejectedValue(new Error('API error'))
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Pro Monthly/ }))
      // Should not crash - preview just won't show
      await waitFor(() => {
        expect(screen.queryByText('Proration Preview')).not.toBeInTheDocument()
      })
    })
  })

  describe('effective date picker', () => {
    it('opens calendar when date button is clicked', async () => {
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      await user.click(screen.getByText('Immediately (now)'))
      // Calendar should be visible
      expect(screen.getByRole('grid')).toBeInTheDocument()
    })

    it('shows helper text about leaving date empty', () => {
      render(<ChangePlanDialog {...defaultProps} />)
      expect(screen.getByText(/Leave empty to apply the change immediately/)).toBeInTheDocument()
    })

    it('refetches preview when date is changed with plan already selected', async () => {
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      // Select a plan first
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Pro Monthly/ }))
      await waitFor(() => {
        expect(mockChangePlanPreview).toHaveBeenCalled()
      })
      const callCountAfterPlanSelect = mockChangePlanPreview.mock.calls.length
      // Open date picker and select a date
      // The "Immediately (now)" text should now not appear because the
      // combobox selected value replaces it in the trigger
      const dateButton = screen.getByRole('button', { name: /Immediately|now/ })
      await user.click(dateButton)
      // Click a non-disabled day in the calendar
      const dayButtons = screen.getAllByRole('gridcell').filter(
        (cell) => {
          const btn = cell.querySelector('button')
          return btn && !btn.hasAttribute('disabled')
        }
      )
      if (dayButtons.length > 0) {
        const btn = dayButtons[dayButtons.length - 1].querySelector('button')
        if (btn) {
          await user.click(btn)
          await waitFor(() => {
            expect(mockChangePlanPreview.mock.calls.length).toBeGreaterThan(callCountAfterPlanSelect)
          })
        }
      }
    })
  })

  describe('submit', () => {
    it('submit button is disabled when no plan is selected', () => {
      render(<ChangePlanDialog {...defaultProps} />)
      expect(getSubmitButton()).toBeDisabled()
    })

    it('submit button is enabled after selecting a plan', async () => {
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Pro Monthly/ }))
      await waitFor(() => {
        expect(getSubmitButton()).toBeEnabled()
      })
    })

    it('calls onSubmit with subscription ID and selected plan ID', async () => {
      const onSubmit = vi.fn()
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} onSubmit={onSubmit} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Pro Monthly/ }))
      await waitFor(() => {
        expect(getSubmitButton()).toBeEnabled()
      })
      await user.click(getSubmitButton())
      expect(onSubmit).toHaveBeenCalledWith('sub-1', 'plan-upgrade', undefined)
    })

    it('shows loading text when isLoading is true', () => {
      render(<ChangePlanDialog {...defaultProps} isLoading={true} />)
      expect(screen.getByRole('button', { name: 'Changing...' })).toBeInTheDocument()
    })

    it('submit button is disabled when isLoading is true', () => {
      render(<ChangePlanDialog {...defaultProps} isLoading={true} />)
      expect(screen.getByRole('button', { name: 'Changing...' })).toBeDisabled()
    })
  })

  describe('dialog open/close', () => {
    it('calls onOpenChange when cancel is clicked', async () => {
      const onOpenChange = vi.fn()
      const user = userEvent.setup()
      render(<ChangePlanDialog {...defaultProps} onOpenChange={onOpenChange} />)
      await user.click(screen.getByRole('button', { name: 'Cancel' }))
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })

    it('resets state when dialog is closed', async () => {
      const onOpenChange = vi.fn()
      const user = userEvent.setup()
      const { rerender } = render(
        <ChangePlanDialog {...defaultProps} onOpenChange={onOpenChange} />
      )
      // Select a plan
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: /Pro Monthly/ }))
      await waitFor(() => {
        expect(screen.getByText('Price Comparison')).toBeInTheDocument()
      })
      // Close dialog via cancel
      await user.click(screen.getByRole('button', { name: 'Cancel' }))
      // Reopen
      rerender(<ChangePlanDialog {...defaultProps} open={true} onOpenChange={onOpenChange} />)
      // The plan selection should be reset (submit disabled)
      expect(getSubmitButton()).toBeDisabled()
    })

    it('does not render dialog content when open is false', () => {
      render(<ChangePlanDialog {...defaultProps} open={false} />)
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })
})
