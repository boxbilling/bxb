import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, userEvent } from '@/test/test-utils'

import { TerminateSubscriptionDialog } from './TerminateSubscriptionDialog'
import { buildSubscription } from '@/test/factories'

describe('TerminateSubscriptionDialog', () => {
  const subscription = buildSubscription({
    id: 'sub-1',
    external_id: 'sub_ext_001',
    status: 'active',
  })

  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    subscription,
    onTerminate: vi.fn(),
    isLoading: false,
  }

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  describe('rendering', () => {
    it('renders dialog title', () => {
      render(<TerminateSubscriptionDialog {...defaultProps} />)
      expect(screen.getByText('Terminate Subscription')).toBeInTheDocument()
    })

    it('renders dialog description', () => {
      render(<TerminateSubscriptionDialog {...defaultProps} />)
      expect(screen.getByText(/permanently terminate the subscription/)).toBeInTheDocument()
    })

    it('renders financial action label', () => {
      render(<TerminateSubscriptionDialog {...defaultProps} />)
      expect(screen.getByText('Financial Action')).toBeInTheDocument()
    })

    it('renders cancel and terminate buttons', () => {
      render(<TerminateSubscriptionDialog {...defaultProps} />)
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Terminate' })).toBeInTheDocument()
    })

    it('returns null when subscription is null', () => {
      const { container } = render(
        <TerminateSubscriptionDialog {...defaultProps} subscription={null} />
      )
      expect(container.querySelector('[role="alertdialog"]')).not.toBeInTheDocument()
    })

    it('does not render content when open is false', () => {
      render(<TerminateSubscriptionDialog {...defaultProps} open={false} />)
      expect(screen.queryByText('Terminate Subscription')).not.toBeInTheDocument()
    })
  })

  describe('financial action selection', () => {
    it('defaults to generate_invoice', () => {
      render(<TerminateSubscriptionDialog {...defaultProps} />)
      expect(screen.getByText('Generate final invoice')).toBeInTheDocument()
    })

    it('shows all three financial action options', async () => {
      const user = userEvent.setup()
      render(<TerminateSubscriptionDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      expect(screen.getByRole('option', { name: 'Generate final invoice' })).toBeInTheDocument()
      expect(screen.getByRole('option', { name: 'Generate credit note (refund)' })).toBeInTheDocument()
      expect(screen.getByRole('option', { name: 'Skip (no financial action)' })).toBeInTheDocument()
    })

    it('allows selecting credit note option', async () => {
      const user = userEvent.setup()
      render(<TerminateSubscriptionDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: 'Generate credit note (refund)' }))
      expect(screen.getByText('Generate credit note (refund)')).toBeInTheDocument()
    })

    it('allows selecting skip option', async () => {
      const user = userEvent.setup()
      render(<TerminateSubscriptionDialog {...defaultProps} />)
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: 'Skip (no financial action)' }))
      expect(screen.getByText('Skip (no financial action)')).toBeInTheDocument()
    })
  })

  describe('submit', () => {
    it('calls onTerminate with subscription ID and default action', async () => {
      const onTerminate = vi.fn()
      const user = userEvent.setup()
      render(
        <TerminateSubscriptionDialog {...defaultProps} onTerminate={onTerminate} />
      )
      await user.click(screen.getByRole('button', { name: 'Terminate' }))
      expect(onTerminate).toHaveBeenCalledWith('sub-1', 'generate_invoice')
    })

    it('calls onTerminate with selected credit note action', async () => {
      const onTerminate = vi.fn()
      const user = userEvent.setup()
      render(
        <TerminateSubscriptionDialog {...defaultProps} onTerminate={onTerminate} />
      )
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: 'Generate credit note (refund)' }))
      await user.click(screen.getByRole('button', { name: 'Terminate' }))
      expect(onTerminate).toHaveBeenCalledWith('sub-1', 'generate_credit_note')
    })

    it('calls onTerminate with skip action', async () => {
      const onTerminate = vi.fn()
      const user = userEvent.setup()
      render(
        <TerminateSubscriptionDialog {...defaultProps} onTerminate={onTerminate} />
      )
      await user.click(screen.getByRole('combobox'))
      await user.click(screen.getByRole('option', { name: 'Skip (no financial action)' }))
      await user.click(screen.getByRole('button', { name: 'Terminate' }))
      expect(onTerminate).toHaveBeenCalledWith('sub-1', 'skip')
    })
  })

  describe('loading state', () => {
    it('shows "Terminating..." text when isLoading is true', () => {
      render(<TerminateSubscriptionDialog {...defaultProps} isLoading={true} />)
      expect(screen.getByRole('button', { name: 'Terminating...' })).toBeInTheDocument()
    })

    it('shows "Terminate" text when isLoading is false', () => {
      render(<TerminateSubscriptionDialog {...defaultProps} isLoading={false} />)
      expect(screen.getByRole('button', { name: 'Terminate' })).toBeInTheDocument()
    })
  })

  describe('dialog open/close', () => {
    it('calls onOpenChange when cancel is clicked', async () => {
      const onOpenChange = vi.fn()
      const user = userEvent.setup()
      render(
        <TerminateSubscriptionDialog {...defaultProps} onOpenChange={onOpenChange} />
      )
      await user.click(screen.getByRole('button', { name: 'Cancel' }))
      expect(onOpenChange).toHaveBeenCalled()
    })
  })
})
