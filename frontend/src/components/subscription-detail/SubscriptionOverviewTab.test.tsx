import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@/test/test-utils'
import { SubscriptionOverviewTab } from './SubscriptionOverviewTab'
import { buildPlan } from '@/test/factories'

vi.mock('@/lib/api', () => ({
  plansApi: { get: vi.fn() },
  billableMetricsApi: { list: vi.fn() },
  usageThresholdsApi: { getCurrentUsage: vi.fn() },
  customersApi: { getCurrentUsage: vi.fn() },
  subscriptionsApi: { getUsageTrend: vi.fn() },
}))

// Mock recharts to avoid rendering issues in tests
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="responsive-container">{children}</div>,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div data-testid="area-chart">{children}</div>,
  Area: () => <div data-testid="area" />,
  CartesianGrid: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
}))

let mockPlan: ReturnType<typeof buildPlan> | undefined
let mockPlanLoading = false
let mockUsage: { current_usage_amount_cents: string; billing_period_start: string; billing_period_end: string } | undefined
let mockUsageLoading = false
let mockUsageError = false
let mockCustomerUsage: { charges: Array<{ billable_metric: { name: string; code: string }; units: string; amount_cents: string; charge_model: string }>; currency: string } | undefined
let mockCustomerUsageLoading = false
let mockUsageTrend: { data_points: Array<{ date: string; value: number; events_count: number }> } | undefined
let mockUsageTrendLoading = false
let mockMetrics: Array<{ id: string; name: string; code: string }> | undefined

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query')
  return {
    ...actual,
    useQuery: (options: { queryKey: string[]; enabled?: boolean }) => {
      if (options.queryKey[0] === 'plan') {
        if (options.enabled === false) return { data: undefined, isLoading: false }
        return { data: mockPlan, isLoading: mockPlanLoading }
      }
      if (options.queryKey[0] === 'billable-metrics') {
        if (options.enabled === false) return { data: undefined, isLoading: false }
        return { data: mockMetrics, isLoading: false }
      }
      if (options.queryKey[0] === 'current-usage') {
        return { data: mockUsage, isLoading: mockUsageLoading, isError: mockUsageError }
      }
      if (options.queryKey[0] === 'customer-usage') {
        if (options.enabled === false) return { data: undefined, isLoading: false }
        return { data: mockCustomerUsage, isLoading: mockCustomerUsageLoading }
      }
      if (options.queryKey[0] === 'usage-trend') {
        return { data: mockUsageTrend, isLoading: mockUsageTrendLoading }
      }
      return { data: undefined, isLoading: false }
    },
  }
})

describe('SubscriptionOverviewTab', () => {
  beforeEach(() => {
    mockPlan = buildPlan()
    mockPlanLoading = false
    mockUsage = {
      current_usage_amount_cents: '15000',
      billing_period_start: '2024-01-15T00:00:00Z',
      billing_period_end: '2024-02-15T00:00:00Z',
    }
    mockUsageLoading = false
    mockUsageError = false
    mockCustomerUsage = {
      charges: [
        {
          billable_metric: { name: 'API Calls', code: 'api_calls' },
          units: '1,250',
          amount_cents: '5000',
          charge_model: 'standard',
        },
      ],
      currency: 'usd',
    }
    mockCustomerUsageLoading = false
    mockUsageTrend = {
      data_points: [
        { date: '2024-01-01', value: 100, events_count: 50 },
        { date: '2024-01-02', value: 200, events_count: 80 },
      ],
    }
    mockUsageTrendLoading = false
    mockMetrics = [
      { id: 'metric-1', name: 'API Calls', code: 'api_calls' },
    ]
  })

  describe('Plan Details card', () => {
    it('renders plan name and code', () => {
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      expect(screen.getByText('Plan Details')).toBeInTheDocument()
      expect(screen.getByText('Pro Monthly')).toBeInTheDocument()
      expect(screen.getByText('pro_monthly')).toBeInTheDocument()
    })

    it('renders plan pricing with interval', () => {
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      expect(screen.getByText(/\$99\.00/)).toBeInTheDocument()
      expect(screen.getByText('/month')).toBeInTheDocument()
    })

    it('renders View Plan link', () => {
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      const link = screen.getByRole('link', { name: /View Plan/ })
      expect(link).toHaveAttribute('href', '/admin/plans/plan-uuid-1')
    })

    it('renders skeletons when plan is loading', () => {
      mockPlanLoading = true
      const { container } = render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('renders "No plan data available" when plan is undefined', () => {
      mockPlan = undefined
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      expect(screen.getByText('No plan data available')).toBeInTheDocument()
    })

    it('renders plan description when present', () => {
      mockPlan = buildPlan({ description: 'A great plan for professionals' })
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      expect(screen.getByText('A great plan for professionals')).toBeInTheDocument()
    })

    it('does not render description when empty', () => {
      mockPlan = buildPlan({ description: '' })
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      expect(screen.queryByText('A great plan for professionals')).not.toBeInTheDocument()
    })

    it('renders charges table when charges exist', () => {
      mockPlan = buildPlan({
        charges: [
          { id: 'charge-1', billable_metric_id: 'metric-1', charge_model: 'standard' },
        ] as never,
      })
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      expect(screen.getByText('Charges (1)')).toBeInTheDocument()
      expect(screen.getByText('Metric')).toBeInTheDocument()
      expect(screen.getByText('Charge Model')).toBeInTheDocument()
      expect(screen.getByText('API Calls')).toBeInTheDocument()
      expect(screen.getByText('standard')).toBeInTheDocument()
    })

    it('shows "Unknown metric" when metric not found in map', () => {
      mockPlan = buildPlan({
        charges: [
          { id: 'charge-1', billable_metric_id: 'unknown-id', charge_model: 'graduated' },
        ] as never,
      })
      mockMetrics = []
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      expect(screen.getByText('Unknown metric')).toBeInTheDocument()
    })

    it('renders pending downgrade alert', () => {
      const prevPlan = buildPlan({ id: 'prev-plan', name: 'Enterprise Monthly' })
      mockPlan = buildPlan()
      // Override the mock for previousPlan query
      const originalMock = vi.mocked(vi.fn())
      // The downgrade is shown when previousPlanId + downgradedAt + previousPlan are all present.
      // The second useQuery call (for previousPlan) needs to also return data.
      // We'll check for the props: previousPlanId and downgradedAt are passed, and plan mock returns data.
      // Since our useQuery mock returns `mockPlan` for all 'plan' queries, both plan and previousPlan get the same data.
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
          previousPlanId="prev-plan"
          downgradedAt="2024-03-01T00:00:00Z"
        />
      )
      expect(screen.getByText('Pending Downgrade')).toBeInTheDocument()
      expect(screen.getByText(/Scheduled for/)).toBeInTheDocument()
    })

    it('does not render charges section when no charges', () => {
      mockPlan = buildPlan({ charges: [] })
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      expect(screen.queryByText(/Charges/)).not.toBeInTheDocument()
    })

    it('renders yearly interval correctly', () => {
      mockPlan = buildPlan({ interval: 'yearly', amount_cents: 99000 })
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          planId="plan-uuid-1"
        />
      )
      expect(screen.getByText('/year')).toBeInTheDocument()
    })
  })

  describe('Current Usage card', () => {
    it('renders current usage amount and billing period', () => {
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
        />
      )
      expect(screen.getByText('Current Usage')).toBeInTheDocument()
      expect(screen.getByText('$150.00')).toBeInTheDocument()
      expect(screen.getByText(/Jan 15, 2024/)).toBeInTheDocument()
      expect(screen.getByText(/Feb 15, 2024/)).toBeInTheDocument()
    })

    it('renders skeletons when usage is loading', () => {
      mockUsageLoading = true
      const { container } = render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
        />
      )
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('renders "No usage data available" when usage is undefined', () => {
      mockUsage = undefined
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
        />
      )
      expect(screen.getByText('No usage data available')).toBeInTheDocument()
    })

    it('renders "No usage data available" on usage error', () => {
      mockUsageError = true
      mockUsage = undefined
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
        />
      )
      expect(screen.getByText('No usage data available')).toBeInTheDocument()
    })
  })

  describe('Usage Trend card', () => {
    it('renders chart when trend data exists', () => {
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
        />
      )
      expect(screen.getByText('Usage Trend')).toBeInTheDocument()
      expect(screen.getByTestId('area-chart')).toBeInTheDocument()
    })

    it('renders skeletons when trend is loading', () => {
      mockUsageTrendLoading = true
      const { container } = render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
        />
      )
      expect(screen.getByText('Usage Trend')).toBeInTheDocument()
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('renders empty message when no trend data', () => {
      mockUsageTrend = { data_points: [] }
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
        />
      )
      expect(screen.getByText('No usage trend data available')).toBeInTheDocument()
    })

    it('renders empty message when trend is undefined', () => {
      mockUsageTrend = undefined
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
        />
      )
      expect(screen.getByText('No usage trend data available')).toBeInTheDocument()
    })
  })

  describe('Usage Breakdown card', () => {
    it('renders per-metric usage table', () => {
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          customerExternalId="cust-ext-1"
          subscriptionExternalId="sub-ext-1"
          customerId="cust-1"
        />
      )
      expect(screen.getByText('Usage Breakdown')).toBeInTheDocument()
      expect(screen.getByText('API Calls')).toBeInTheDocument()
      expect(screen.getByText('api_calls')).toBeInTheDocument()
      expect(screen.getByText('1,250')).toBeInTheDocument()
      expect(screen.getByText('$50.00')).toBeInTheDocument()
      expect(screen.getByText('standard')).toBeInTheDocument()
    })

    it('renders View Full Usage link when customerId exists', () => {
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          customerExternalId="cust-ext-1"
          subscriptionExternalId="sub-ext-1"
          customerId="cust-1"
        />
      )
      const link = screen.getByRole('link', { name: /View Full Usage/ })
      expect(link).toHaveAttribute('href', '/admin/customers/cust-1?tab=usage')
    })

    it('does not render View Full Usage link when customerId is undefined', () => {
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
        />
      )
      expect(screen.queryByRole('link', { name: /View Full Usage/ })).not.toBeInTheDocument()
    })

    it('renders skeletons when customer usage is loading', () => {
      mockCustomerUsageLoading = true
      const { container } = render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          customerExternalId="cust-ext-1"
          subscriptionExternalId="sub-ext-1"
        />
      )
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('renders empty message when no charges', () => {
      mockCustomerUsage = { charges: [], currency: 'usd' }
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          customerExternalId="cust-ext-1"
          subscriptionExternalId="sub-ext-1"
        />
      )
      expect(screen.getByText('No per-metric usage data available')).toBeInTheDocument()
    })

    it('renders empty message when customer usage is undefined', () => {
      mockCustomerUsage = undefined
      render(
        <SubscriptionOverviewTab
          subscriptionId="sub-1"
          customerExternalId="cust-ext-1"
          subscriptionExternalId="sub-ext-1"
        />
      )
      expect(screen.getByText('No per-metric usage data available')).toBeInTheDocument()
    })
  })
})
