import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@/test/test-utils'
import { SubscriptionKPICards } from './SubscriptionKPICards'
import { buildSubscription, buildPlan } from '@/test/factories'

vi.mock('@/lib/api', () => ({
  subscriptionsApi: {
    getNextBillingDate: vi.fn(),
  },
  usageThresholdsApi: {
    getCurrentUsage: vi.fn(),
  },
  invoicesApi: {
    list: vi.fn(),
  },
}))

// Default mock data for useQuery results
let mockNextBillingDate: { next_billing_date: string; days_until_next_billing: number } | undefined
let mockNextBillingLoading = false
let mockUsage: { current_usage_amount_cents: string; billing_period_start: string; billing_period_end: string } | undefined
let mockUsageLoading = false
let mockInvoices: { id: string }[] | undefined
let mockInvoicesLoading = false

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query')
  return {
    ...actual,
    useQuery: (options: { queryKey: string[]; enabled?: boolean }) => {
      if (options.queryKey[0] === 'next-billing-date') {
        if (options.enabled === false) {
          return { data: undefined, isLoading: false }
        }
        return { data: mockNextBillingDate, isLoading: mockNextBillingLoading }
      }
      if (options.queryKey[0] === 'current-usage') {
        return { data: mockUsage, isLoading: mockUsageLoading }
      }
      if (options.queryKey[0] === 'subscription-invoices') {
        return { data: mockInvoices, isLoading: mockInvoicesLoading }
      }
      return { data: undefined, isLoading: false }
    },
  }
})

describe('SubscriptionKPICards', () => {
  const defaultSubscription = buildSubscription()
  const defaultPlan = buildPlan()

  beforeEach(() => {
    vi.restoreAllMocks()
    mockNextBillingDate = {
      next_billing_date: '2024-02-15T00:00:00Z',
      days_until_next_billing: 12,
    }
    mockNextBillingLoading = false
    mockUsage = {
      current_usage_amount_cents: '4500',
      billing_period_start: '2024-01-15T00:00:00Z',
      billing_period_end: '2024-02-15T00:00:00Z',
    }
    mockUsageLoading = false
    mockInvoices = [{ id: 'inv-1' }, { id: 'inv-2' }, { id: 'inv-3' }]
    mockInvoicesLoading = false
  })

  describe('loading/skeleton state', () => {
    it('renders 4 skeleton cards when isLoading is true', () => {
      const { container } = render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          isLoading
        />
      )
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  describe('Next Billing card', () => {
    it('renders days until next billing and date', () => {
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Next Billing')).toBeInTheDocument()
      expect(screen.getByText('12')).toBeInTheDocument()
      expect(screen.getByText('days')).toBeInTheDocument()
      expect(screen.getByText('Feb 15, 2024')).toBeInTheDocument()
    })

    it('renders loading skeletons when next billing is loading', () => {
      mockNextBillingLoading = true
      const { container } = render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Next Billing')).toBeInTheDocument()
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('shows dash for terminated subscription', () => {
      const terminated = buildSubscription({ status: 'terminated' })
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={terminated}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Subscription terminated')).toBeInTheDocument()
    })

    it('shows dash for canceled subscription', () => {
      const canceled = buildSubscription({ status: 'canceled' })
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={canceled}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Subscription canceled')).toBeInTheDocument()
    })

    it('shows "Not available" when nextBillingDate is undefined for active subscription', () => {
      mockNextBillingDate = undefined
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Not available')).toBeInTheDocument()
    })
  })

  describe('Current Usage card', () => {
    it('renders current usage amount and billing period', () => {
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Current Usage')).toBeInTheDocument()
      // formatCents(4500) => $45.00
      expect(screen.getByText('$45.00')).toBeInTheDocument()
    })

    it('renders loading skeletons when usage is loading', () => {
      mockUsageLoading = true
      const { container } = render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Current Usage')).toBeInTheDocument()
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('shows dash and "No usage data" when usage is undefined', () => {
      mockUsage = undefined
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('No usage data')).toBeInTheDocument()
    })
  })

  describe('Invoices card', () => {
    it('renders invoice count', () => {
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Invoices')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
      expect(screen.getByText('Total invoices')).toBeInTheDocument()
    })

    it('renders loading skeletons when invoices are loading', () => {
      mockInvoicesLoading = true
      const { container } = render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Invoices')).toBeInTheDocument()
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('renders 0 when invoices is undefined', () => {
      mockInvoices = undefined
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('0')).toBeInTheDocument()
    })
  })

  describe('Plan Price card', () => {
    it('renders plan amount and interval', () => {
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Plan Price')).toBeInTheDocument()
      // formatCents(9900, 'usd') => $99.00
      expect(screen.getByText('$99.00')).toBeInTheDocument()
      expect(screen.getByText('monthly')).toBeInTheDocument()
    })

    it('renders skeleton when plan is undefined', () => {
      const { container } = render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
        />
      )
      expect(screen.getByText('Plan Price')).toBeInTheDocument()
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('renders annual interval for annual plan', () => {
      const annualPlan = buildPlan({ interval: 'annual', amount_cents: 99000 })
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={annualPlan}
        />
      )
      expect(screen.getByText('annual')).toBeInTheDocument()
      expect(screen.getByText('$990.00')).toBeInTheDocument()
    })
  })

  describe('all 4 cards rendered', () => {
    it('renders all card titles', () => {
      render(
        <SubscriptionKPICards
          subscriptionId="sub-uuid-1"
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Next Billing')).toBeInTheDocument()
      expect(screen.getByText('Current Usage')).toBeInTheDocument()
      expect(screen.getByText('Invoices')).toBeInTheDocument()
      expect(screen.getByText('Plan Price')).toBeInTheDocument()
    })
  })
})
