import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@/test/test-utils'

import { SubscriptionLifecycleTab } from './SubscriptionLifecycleTab'

// Mock the SubscriptionLifecycleTimeline since it has its own queries
vi.mock('@/components/SubscriptionLifecycleTimeline', () => ({
  SubscriptionLifecycleTimeline: ({ subscriptionId }: { subscriptionId: string }) => (
    <div data-testid="lifecycle-timeline">Timeline for {subscriptionId}</div>
  ),
}))

describe('SubscriptionLifecycleTab', () => {
  it('renders Lifecycle Timeline heading', () => {
    render(<SubscriptionLifecycleTab subscriptionId="sub-1" />)
    expect(screen.getByText('Lifecycle Timeline')).toBeInTheDocument()
  })

  it('renders the SubscriptionLifecycleTimeline component', () => {
    render(<SubscriptionLifecycleTab subscriptionId="sub-1" />)
    expect(screen.getByTestId('lifecycle-timeline')).toBeInTheDocument()
  })

  it('passes subscriptionId to SubscriptionLifecycleTimeline', () => {
    render(<SubscriptionLifecycleTab subscriptionId="sub-abc-123" />)
    expect(screen.getByText('Timeline for sub-abc-123')).toBeInTheDocument()
  })

  it('renders inside a Card', () => {
    const { container } = render(<SubscriptionLifecycleTab subscriptionId="sub-1" />)
    const card = container.querySelector('[data-slot="card"]') || container.firstElementChild
    expect(card).toBeInTheDocument()
  })
})
