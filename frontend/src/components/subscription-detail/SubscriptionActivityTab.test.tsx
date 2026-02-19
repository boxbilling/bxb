import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@/test/test-utils'

import { SubscriptionActivityTab } from './SubscriptionActivityTab'

// Mock the AuditTrailTimeline since it has its own queries
vi.mock('@/components/AuditTrailTimeline', () => ({
  AuditTrailTimeline: ({
    resourceType,
    resourceId,
    limit,
    showViewAll,
  }: {
    resourceType: string
    resourceId: string
    limit: number
    showViewAll: boolean
  }) => (
    <div data-testid="audit-trail-timeline">
      <span data-testid="resource-type">{resourceType}</span>
      <span data-testid="resource-id">{resourceId}</span>
      <span data-testid="limit">{limit}</span>
      <span data-testid="show-view-all">{String(showViewAll)}</span>
    </div>
  ),
}))

describe('SubscriptionActivityTab', () => {
  it('renders Activity Log heading', () => {
    render(<SubscriptionActivityTab subscriptionId="sub-1" />)
    expect(screen.getByText('Activity Log')).toBeInTheDocument()
  })

  it('renders the AuditTrailTimeline component', () => {
    render(<SubscriptionActivityTab subscriptionId="sub-1" />)
    expect(screen.getByTestId('audit-trail-timeline')).toBeInTheDocument()
  })

  it('passes resourceType="subscription" to AuditTrailTimeline', () => {
    render(<SubscriptionActivityTab subscriptionId="sub-1" />)
    expect(screen.getByTestId('resource-type')).toHaveTextContent('subscription')
  })

  it('passes subscriptionId as resourceId to AuditTrailTimeline', () => {
    render(<SubscriptionActivityTab subscriptionId="sub-xyz-456" />)
    expect(screen.getByTestId('resource-id')).toHaveTextContent('sub-xyz-456')
  })

  it('passes limit=20 to AuditTrailTimeline', () => {
    render(<SubscriptionActivityTab subscriptionId="sub-1" />)
    expect(screen.getByTestId('limit')).toHaveTextContent('20')
  })

  it('passes showViewAll to AuditTrailTimeline', () => {
    render(<SubscriptionActivityTab subscriptionId="sub-1" />)
    expect(screen.getByTestId('show-view-all')).toHaveTextContent('true')
  })

  it('renders inside a Card', () => {
    const { container } = render(<SubscriptionActivityTab subscriptionId="sub-1" />)
    const card = container.querySelector('[data-slot="card"]') || container.firstElementChild
    expect(card).toBeInTheDocument()
  })
})
