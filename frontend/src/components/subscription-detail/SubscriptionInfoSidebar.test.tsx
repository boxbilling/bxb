import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@/test/test-utils'
import { SubscriptionInfoSidebar } from './SubscriptionInfoSidebar'
import { buildSubscription, buildCustomer, buildPlan, buildBillingEntity } from '@/test/factories'

vi.mock('@/lib/api', () => ({
  billingEntitiesApi: {
    list: vi.fn(),
  },
}))

// Mock useQuery to return billing entities when enabled
const mockBillingEntity = buildBillingEntity({ id: 'be-uuid-1', code: 'acme_entity', name: 'Acme Billing Entity' })

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query')
  return {
    ...actual,
    useQuery: (options: { queryKey: string[]; enabled?: boolean }) => {
      if (options.queryKey[0] === 'billing-entities' && options.enabled) {
        return { data: [mockBillingEntity], isLoading: false }
      }
      return { data: undefined, isLoading: false }
    },
  }
})

describe('SubscriptionInfoSidebar', () => {
  const defaultSubscription = buildSubscription()
  const defaultCustomer = buildCustomer()
  const defaultPlan = buildPlan()

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  describe('loading/skeleton state', () => {
    it('renders skeletons when isLoading is true', () => {
      const { container } = render(<SubscriptionInfoSidebar isLoading />)
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('renders skeletons when subscription is undefined', () => {
      const { container } = render(<SubscriptionInfoSidebar />)
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  describe('external ID and status', () => {
    it('renders the subscription external ID', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('sub_ext_001')).toBeInTheDocument()
      expect(screen.getByText('External ID')).toBeInTheDocument()
    })

    it('renders the status badge', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('active')).toBeInTheDocument()
    })

    it('renders terminated status', () => {
      const terminated = buildSubscription({ status: 'terminated' })
      render(
        <SubscriptionInfoSidebar
          subscription={terminated}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('terminated')).toBeInTheDocument()
    })
  })

  describe('customer link', () => {
    it('renders customer name as link', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      const link = screen.getByRole('link', { name: /Acme Corp/i })
      expect(link).toHaveAttribute('href', '/admin/customers/cust-uuid-1')
    })

    it('renders customer email when present', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('billing@acme.com')).toBeInTheDocument()
    })

    it('does not render email when null', () => {
      const noEmail = buildCustomer({ email: null })
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={noEmail}
          plan={defaultPlan}
        />
      )
      expect(screen.queryByText('billing@acme.com')).not.toBeInTheDocument()
    })
  })

  describe('plan link', () => {
    it('renders plan name as link', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      const link = screen.getByRole('link', { name: /Pro Monthly/i })
      expect(link).toHaveAttribute('href', '/admin/plans/plan-uuid-1')
    })

    it('renders plan pricing', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      // $99.00 / monthly
      expect(screen.getByText(/\$99\.00/)).toBeInTheDocument()
      expect(screen.getByText(/monthly/)).toBeInTheDocument()
    })
  })

  describe('quick actions based on status', () => {
    it('shows Edit, Pause, Change Plan, Terminate for active subscription', () => {
      const active = buildSubscription({ status: 'active' })
      render(
        <SubscriptionInfoSidebar
          subscription={active}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Pause/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Change Plan/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Terminate/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Resume/i })).not.toBeInTheDocument()
    })

    it('shows Edit, Resume, Terminate for paused subscription', () => {
      const paused = buildSubscription({ status: 'paused' })
      render(
        <SubscriptionInfoSidebar
          subscription={paused}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Resume/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Terminate/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Pause$/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Change Plan/i })).not.toBeInTheDocument()
    })

    it('shows no action buttons for terminated subscription', () => {
      const terminated = buildSubscription({ status: 'terminated' })
      render(
        <SubscriptionInfoSidebar
          subscription={terminated}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.queryByRole('button', { name: /Edit/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Pause/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Resume/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Change Plan/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Terminate/i })).not.toBeInTheDocument()
    })

    it('shows Edit, Change Plan, Terminate for pending subscription', () => {
      const pending = buildSubscription({ status: 'pending' })
      render(
        <SubscriptionInfoSidebar
          subscription={pending}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByRole('button', { name: /Edit/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Change Plan/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Terminate/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Pause$/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Resume/i })).not.toBeInTheDocument()
    })

    it('does not show Change Plan when plan is not provided', () => {
      const active = buildSubscription({ status: 'active' })
      render(
        <SubscriptionInfoSidebar
          subscription={active}
          customer={defaultCustomer}
        />
      )
      expect(screen.queryByRole('button', { name: /Change Plan/i })).not.toBeInTheDocument()
    })

    it('calls onEdit when Edit is clicked', async () => {
      const onEdit = vi.fn()
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
          onEdit={onEdit}
        />
      )
      const { default: userEvent } = await import('@testing-library/user-event')
      await userEvent.click(screen.getByRole('button', { name: /Edit/i }))
      expect(onEdit).toHaveBeenCalledOnce()
    })

    it('calls onPause when Pause is clicked', async () => {
      const onPause = vi.fn()
      render(
        <SubscriptionInfoSidebar
          subscription={buildSubscription({ status: 'active' })}
          customer={defaultCustomer}
          plan={defaultPlan}
          onPause={onPause}
        />
      )
      const { default: userEvent } = await import('@testing-library/user-event')
      await userEvent.click(screen.getByRole('button', { name: /Pause/i }))
      expect(onPause).toHaveBeenCalledOnce()
    })

    it('calls onResume when Resume is clicked', async () => {
      const onResume = vi.fn()
      render(
        <SubscriptionInfoSidebar
          subscription={buildSubscription({ status: 'paused' })}
          customer={defaultCustomer}
          plan={defaultPlan}
          onResume={onResume}
        />
      )
      const { default: userEvent } = await import('@testing-library/user-event')
      await userEvent.click(screen.getByRole('button', { name: /Resume/i }))
      expect(onResume).toHaveBeenCalledOnce()
    })

    it('calls onChangePlan when Change Plan is clicked', async () => {
      const onChangePlan = vi.fn()
      render(
        <SubscriptionInfoSidebar
          subscription={buildSubscription({ status: 'active' })}
          customer={defaultCustomer}
          plan={defaultPlan}
          onChangePlan={onChangePlan}
        />
      )
      const { default: userEvent } = await import('@testing-library/user-event')
      await userEvent.click(screen.getByRole('button', { name: /Change Plan/i }))
      expect(onChangePlan).toHaveBeenCalledOnce()
    })

    it('calls onTerminate when Terminate is clicked', async () => {
      const onTerminate = vi.fn()
      render(
        <SubscriptionInfoSidebar
          subscription={buildSubscription({ status: 'active' })}
          customer={defaultCustomer}
          plan={defaultPlan}
          onTerminate={onTerminate}
        />
      )
      const { default: userEvent } = await import('@testing-library/user-event')
      await userEvent.click(screen.getByRole('button', { name: /Terminate/i }))
      expect(onTerminate).toHaveBeenCalledOnce()
    })

    it('shows loading text on Pause button when isPauseLoading', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={buildSubscription({ status: 'active' })}
          customer={defaultCustomer}
          plan={defaultPlan}
          isPauseLoading
        />
      )
      expect(screen.getByRole('button', { name: /Pausing\.\.\./i })).toBeDisabled()
    })

    it('shows loading text on Resume button when isResumeLoading', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={buildSubscription({ status: 'paused' })}
          customer={defaultCustomer}
          plan={defaultPlan}
          isResumeLoading
        />
      )
      expect(screen.getByRole('button', { name: /Resuming\.\.\./i })).toBeDisabled()
    })

    it('shows loading text on Terminate button when isTerminateLoading', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={buildSubscription({ status: 'active' })}
          customer={defaultCustomer}
          plan={defaultPlan}
          isTerminateLoading
        />
      )
      expect(screen.getByRole('button', { name: /Terminating\.\.\./i })).toBeDisabled()
    })
  })

  describe('billing configuration', () => {
    it('displays billing_time', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Billing Time')).toBeInTheDocument()
      expect(screen.getByText('calendar')).toBeInTheDocument()
    })

    it('displays pay_in_advance as Yes', () => {
      const sub = buildSubscription({ pay_in_advance: true })
      render(
        <SubscriptionInfoSidebar
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Yes')).toBeInTheDocument()
    })

    it('displays pay_in_advance as No', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('No')).toBeInTheDocument()
    })

    it('displays on_termination_action with underscores replaced', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('On Termination')).toBeInTheDocument()
      expect(screen.getByText('generate last invoice')).toBeInTheDocument()
    })
  })

  describe('trial info', () => {
    it('does not render trial section when trial_period_days is 0', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.queryByText('Trial Period')).not.toBeInTheDocument()
    })

    it('renders trial section when trial_period_days > 0', () => {
      const sub = buildSubscription({ trial_period_days: 14 })
      render(
        <SubscriptionInfoSidebar
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Trial Period')).toBeInTheDocument()
      expect(screen.getByText('14 days')).toBeInTheDocument()
    })

    it('renders trial ended date when present', () => {
      const sub = buildSubscription({
        trial_period_days: 14,
        trial_ended_at: '2024-02-01T10:00:00Z',
      })
      render(
        <SubscriptionInfoSidebar
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Trial Ended')).toBeInTheDocument()
      expect(screen.getByText(/Feb 1, 2024/)).toBeInTheDocument()
    })

    it('does not render trial ended when null', () => {
      const sub = buildSubscription({ trial_period_days: 14, trial_ended_at: null })
      render(
        <SubscriptionInfoSidebar
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Trial Period')).toBeInTheDocument()
      expect(screen.queryByText('Trial Ended')).not.toBeInTheDocument()
    })
  })

  describe('key dates', () => {
    it('renders started_at when present', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Started At')).toBeInTheDocument()
      expect(screen.getByText(/Jan 15, 2024/)).toBeInTheDocument()
    })

    it('renders dash when started_at is null', () => {
      const sub = buildSubscription({ started_at: null })
      render(
        <SubscriptionInfoSidebar
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Started At')).toBeInTheDocument()
      // em dash
      const startedRow = screen.getByText('Started At').closest('div')
      expect(startedRow).toHaveTextContent('—')
    })

    it('renders created_at', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Created')).toBeInTheDocument()
      expect(screen.getByText(/Jan 10, 2024/)).toBeInTheDocument()
    })

    it('renders paused_at conditionally', () => {
      const sub = buildSubscription({ paused_at: '2024-03-01T12:00:00Z' })
      render(
        <SubscriptionInfoSidebar
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Paused At')).toBeInTheDocument()
      expect(screen.getByText(/Mar 1, 2024/)).toBeInTheDocument()
    })

    it('does not render paused_at when null', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.queryByText('Paused At')).not.toBeInTheDocument()
    })

    it('renders resumed_at conditionally', () => {
      const sub = buildSubscription({ resumed_at: '2024-04-01T09:00:00Z' })
      render(
        <SubscriptionInfoSidebar
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Last Resumed')).toBeInTheDocument()
      expect(screen.getByText(/Apr 1, 2024/)).toBeInTheDocument()
    })

    it('renders canceled_at conditionally', () => {
      const sub = buildSubscription({ canceled_at: '2024-05-01T08:00:00Z' })
      render(
        <SubscriptionInfoSidebar
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Canceled At')).toBeInTheDocument()
      expect(screen.getByText(/May 1, 2024/)).toBeInTheDocument()
    })

    it('renders ending_at conditionally', () => {
      const sub = buildSubscription({ ending_at: '2024-06-01T00:00:00Z' })
      render(
        <SubscriptionInfoSidebar
          subscription={sub}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Ending At')).toBeInTheDocument()
      expect(screen.getByText(/Jun 1, 2024/)).toBeInTheDocument()
    })
  })

  describe('billing entity', () => {
    it('does not render billing entity section when billing_entity_id is null', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.queryByText('Billing Entity')).not.toBeInTheDocument()
    })

    it('renders billing entity link when customer has billing_entity_id', () => {
      const customerWithBE = buildCustomer({ billing_entity_id: 'be-uuid-1' })
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={customerWithBE}
          plan={defaultPlan}
        />
      )
      expect(screen.getByText('Billing Entity')).toBeInTheDocument()
      const link = screen.getByRole('link', { name: /Acme Billing Entity/i })
      expect(link).toHaveAttribute('href', '/admin/billing-entities/acme_entity')
    })
  })

  describe('related links', () => {
    it('renders invoices link for this subscription', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      const link = screen.getByRole('link', { name: /Invoices for this subscription/i })
      expect(link).toHaveAttribute('href', '/admin/invoices?subscription_id=sub-uuid-1')
    })

    it('renders customer other subscriptions link when customer exists', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      const link = screen.getByRole('link', { name: /other subscriptions/i })
      expect(link).toHaveAttribute('href', '/admin/subscriptions?customer_id=cust-uuid-1')
    })

    it('renders events link when customer exists', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      const link = screen.getByRole('link', { name: /Events from this customer/i })
      expect(link).toHaveAttribute('href', '/admin/events?customer_id=cust_ext_001')
    })

    it('does not render customer-specific related links when customer is undefined', () => {
      render(
        <SubscriptionInfoSidebar
          subscription={defaultSubscription}
          plan={defaultPlan}
        />
      )
      expect(screen.queryByRole('link', { name: /other subscriptions/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('link', { name: /Events from this customer/i })).not.toBeInTheDocument()
      // Invoice link is always shown
      expect(screen.getByRole('link', { name: /Invoices for this subscription/i })).toBeInTheDocument()
    })
  })

  describe('canceled subscription', () => {
    it('shows no action buttons for canceled status', () => {
      const canceled = buildSubscription({ status: 'canceled' })
      render(
        <SubscriptionInfoSidebar
          subscription={canceled}
          customer={defaultCustomer}
          plan={defaultPlan}
        />
      )
      expect(screen.queryByRole('button', { name: /Edit/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Pause/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Resume/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Change Plan/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Terminate/i })).not.toBeInTheDocument()
    })
  })
})
