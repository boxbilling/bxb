import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@/test/test-utils'
import { SubscriptionHeader } from './SubscriptionHeader'
import { buildSubscription, buildCustomer, buildPlan } from '@/test/factories'

vi.mock('@/lib/api', () => ({
  plansApi: {
    get: vi.fn(),
  },
}))

// Track useQuery calls to return previous plan data when appropriate
const mockPreviousPlan = buildPlan({ id: 'prev-plan-1', name: 'Basic Monthly' })

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query')
  return {
    ...actual,
    useQuery: (options: { queryKey: string[]; enabled?: boolean }) => {
      if (options.queryKey[0] === 'plan' && options.enabled) {
        return { data: mockPreviousPlan, isLoading: false }
      }
      return { data: undefined, isLoading: false }
    },
  }
})

describe('SubscriptionHeader', () => {
  const defaultSubscription = buildSubscription()
  const defaultCustomer = buildCustomer()
  const defaultPlan = buildPlan()

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  describe('loading/skeleton state', () => {
    it('renders skeletons when isLoading is true', () => {
      const { container } = render(<SubscriptionHeader isLoading />)
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('renders skeletons when subscription is undefined', () => {
      const { container } = render(<SubscriptionHeader />)
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  describe('title rendering', () => {
    it('renders customer name and plan name', () => {
      render(
        <SubscriptionHeader
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText(/Acme Corp/)).toBeInTheDocument()
      expect(screen.getByText(/Pro Monthly/)).toBeInTheDocument()
    })

    it('shows "Loading..." when customer is undefined', () => {
      render(
        <SubscriptionHeader
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      // Both customer name and plan name fallback
      expect(screen.getByText(/Loading\.\.\./)).toBeInTheDocument()
    })

    it('shows "Loading..." when plan is undefined', () => {
      render(
        <SubscriptionHeader
          subscription={defaultSubscription}
          customer={defaultCustomer}
        />
      )
      expect(screen.getByText(/Loading\.\.\./)).toBeInTheDocument()
    })
  })

  describe('status badge', () => {
    it('renders active status badge', () => {
      render(
        <SubscriptionHeader
          subscription={buildSubscription({ status: 'active' })}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('active')).toBeInTheDocument()
    })

    it('renders pending status badge', () => {
      render(
        <SubscriptionHeader
          subscription={buildSubscription({ status: 'pending' })}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('pending')).toBeInTheDocument()
    })

    it('renders paused status badge', () => {
      render(
        <SubscriptionHeader
          subscription={buildSubscription({ status: 'paused' })}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('paused')).toBeInTheDocument()
    })

    it('renders canceled status badge', () => {
      render(
        <SubscriptionHeader
          subscription={buildSubscription({ status: 'canceled' })}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('canceled')).toBeInTheDocument()
    })

    it('renders terminated status badge', () => {
      render(
        <SubscriptionHeader
          subscription={buildSubscription({ status: 'terminated' })}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('terminated')).toBeInTheDocument()
    })
  })

  describe('external ID', () => {
    it('renders subscription external ID', () => {
      render(
        <SubscriptionHeader
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('sub_ext_001')).toBeInTheDocument()
    })

    it('renders a custom external ID', () => {
      const sub = buildSubscription({ external_id: 'custom_sub_789' })
      render(
        <SubscriptionHeader
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('custom_sub_789')).toBeInTheDocument()
    })
  })

  describe('downgrade indicator', () => {
    it('does not show downgrade badge when downgraded_at is null', () => {
      render(
        <SubscriptionHeader
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.queryByText(/Pending downgrade/)).not.toBeInTheDocument()
    })

    it('shows pending downgrade badge when downgraded_at is set', () => {
      const sub = buildSubscription({
        downgraded_at: '2024-03-01T00:00:00Z',
        previous_plan_id: 'prev-plan-1',
      })
      render(
        <SubscriptionHeader
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText(/Pending downgrade/)).toBeInTheDocument()
    })

    it('shows previous plan name in downgrade badge when available', () => {
      const sub = buildSubscription({
        downgraded_at: '2024-03-01T00:00:00Z',
        previous_plan_id: 'prev-plan-1',
      })
      render(
        <SubscriptionHeader
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText(/from Basic Monthly/)).toBeInTheDocument()
    })

    it('shows generic downgrade text when previous plan not loaded', () => {
      const sub = buildSubscription({
        downgraded_at: '2024-03-01T00:00:00Z',
        previous_plan_id: null,
      })
      render(
        <SubscriptionHeader
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Pending downgrade')).toBeInTheDocument()
      expect(screen.queryByText(/from/)).not.toBeInTheDocument()
    })
  })
})
