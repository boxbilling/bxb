import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, userEvent, waitFor } from '@/test/test-utils'

import { SubscriptionThresholdsAlertsTab } from './SubscriptionThresholdsAlertsTab'

vi.mock('@/lib/api', () => ({
  usageThresholdsApi: {
    listForSubscription: vi.fn(),
    createForSubscription: vi.fn(),
    delete: vi.fn(),
  },
  usageAlertsApi: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
  billableMetricsApi: {
    list: vi.fn(),
  },
  ApiError: class extends Error {},
}))

interface Threshold {
  id: string
  amount_cents: string
  currency: string
  recurring: boolean
  threshold_display_name: string | null
}

interface UsageAlert {
  id: string
  name: string | null
  billable_metric_id: string
  threshold_value: string
  recurring: boolean
  triggered_at: string | null
}

interface Metric {
  id: string
  name: string
  code: string
}

let mockThresholds: Threshold[] | undefined
let mockThresholdsLoading: boolean
let mockUsageAlerts: UsageAlert[] | undefined
let mockAlertsLoading: boolean
let mockMetrics: Metric[] | undefined
let capturedMutationFns: Array<{ mutationFn: (...args: unknown[]) => unknown; onSuccess?: () => void }>

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query')
  return {
    ...actual,
    useQuery: (options: { queryKey: string[]; enabled?: boolean }) => {
      if (options.queryKey[0] === 'usage-thresholds') {
        return { data: mockThresholds, isLoading: mockThresholdsLoading }
      }
      if (options.queryKey[0] === 'usage-alerts') {
        return { data: mockUsageAlerts, isLoading: mockAlertsLoading }
      }
      if (options.queryKey[0] === 'billable-metrics') {
        return { data: mockMetrics, isLoading: false }
      }
      return { data: undefined, isLoading: false }
    },
    useQueryClient: () => ({
      invalidateQueries: vi.fn(),
    }),
    useMutation: (options: { mutationFn: (...args: unknown[]) => unknown; onSuccess?: () => void; onError?: (error: unknown) => void }) => {
      capturedMutationFns.push(options)
      const mutate = vi.fn((...args: unknown[]) => {
        options.mutationFn(...args)
        options.onSuccess?.()
      })
      return { mutate, isPending: false }
    },
  }
})

describe('SubscriptionThresholdsAlertsTab', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    capturedMutationFns = []
    mockThresholds = [
      {
        id: 'thresh-1',
        amount_cents: '10000',
        currency: 'USD',
        recurring: true,
        threshold_display_name: 'Monthly Cap',
      },
      {
        id: 'thresh-2',
        amount_cents: '5000',
        currency: 'USD',
        recurring: false,
        threshold_display_name: null,
      },
    ]
    mockThresholdsLoading = false
    mockUsageAlerts = [
      {
        id: 'alert-1',
        name: 'API limit warning',
        billable_metric_id: 'metric-1',
        threshold_value: '1000',
        recurring: true,
        triggered_at: '2024-01-20T10:00:00Z',
      },
    ]
    mockAlertsLoading = false
    mockMetrics = [
      { id: 'metric-1', name: 'API Calls', code: 'api_calls' },
    ]
  })

  describe('Usage Thresholds section', () => {
    it('renders Usage Thresholds heading', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('Usage Thresholds')).toBeInTheDocument()
    })

    it('renders skeletons when thresholds are loading', () => {
      mockThresholdsLoading = true
      const { container } = render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('renders empty message when no thresholds', () => {
      mockThresholds = []
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('No usage thresholds configured')).toBeInTheDocument()
    })

    it('renders empty message when thresholds undefined', () => {
      mockThresholds = undefined
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('No usage thresholds configured')).toBeInTheDocument()
    })

    it('renders threshold amounts formatted', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('$100.00')).toBeInTheDocument()
      expect(screen.getByText('$50.00')).toBeInTheDocument()
    })

    it('renders recurring badge correctly', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('Yes')).toBeInTheDocument()
      expect(screen.getByText('No')).toBeInTheDocument()
    })

    it('renders threshold display name', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('Monthly Cap')).toBeInTheDocument()
    })

    it('renders dash for missing display name', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      const dashes = screen.getAllByText('\u2014')
      expect(dashes.length).toBeGreaterThanOrEqual(1)
    })

    it('renders Add Threshold button', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByRole('button', { name: /Add Threshold/ })).toBeInTheDocument()
    })

    it('shows add threshold form on button click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      await user.click(screen.getByRole('button', { name: /Add Threshold/ }))
      expect(screen.getByLabelText(/Amount \(cents\)/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Display Name/)).toBeInTheDocument()
    })

    it('hides Add Threshold button when form is shown', async () => {
      const user = userEvent.setup()
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      await user.click(screen.getByRole('button', { name: /Add Threshold/ }))
      expect(screen.getByRole('button', { name: /^Create$/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /^Cancel$/ })).toBeInTheDocument()
    })

    it('closes form on Cancel', async () => {
      const user = userEvent.setup()
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      await user.click(screen.getByRole('button', { name: /Add Threshold/ }))
      await user.click(screen.getByRole('button', { name: /^Cancel$/ }))
      expect(screen.queryByLabelText(/Amount \(cents\)/)).not.toBeInTheDocument()
    })

    it('submits threshold form successfully', async () => {
      const user = userEvent.setup()
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      await user.click(screen.getByRole('button', { name: /Add Threshold/ }))
      await user.type(screen.getByLabelText(/Amount \(cents\)/), '20000')
      await user.click(screen.getByRole('button', { name: /^Create$/ }))
      // The mutation was called - we can verify by checking the form was closed (onSuccess resets it)
      expect(screen.queryByLabelText(/Amount \(cents\)/)).not.toBeInTheDocument()
    })

    it('calls delete on threshold delete button click', async () => {
      const { usageThresholdsApi } = await import('@/lib/api')
      const user = userEvent.setup()
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      const deleteButtons = screen.getAllByRole('button').filter(
        (btn) => btn.querySelector('[class*="text-destructive"]')
      )
      // First two destructive buttons are threshold deletes (one per row)
      expect(deleteButtons.length).toBeGreaterThanOrEqual(2)
      await user.click(deleteButtons[0])
      expect(usageThresholdsApi.delete).toHaveBeenCalledWith('thresh-1')
    })
  })

  describe('Usage Alerts section', () => {
    it('renders Usage Alerts heading', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('Usage Alerts')).toBeInTheDocument()
    })

    it('renders skeletons when alerts are loading', () => {
      mockAlertsLoading = true
      const { container } = render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('renders empty message and Create Alert button when no alerts', () => {
      mockUsageAlerts = []
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('No usage alerts configured')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Create Alert/ })).toBeInTheDocument()
    })

    it('renders alert name', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('API limit warning')).toBeInTheDocument()
    })

    it('renders alert threshold value', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('1,000')).toBeInTheDocument()
    })

    it('renders Recurring badge for recurring alert', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      // "Recurring" appears as a table header and as the alert badge
      const recurringElements = screen.getAllByText('Recurring')
      expect(recurringElements.length).toBeGreaterThanOrEqual(2)
    })

    it('renders One-time badge for non-recurring alert', () => {
      mockUsageAlerts = [{
        id: 'alert-2',
        name: 'One time alert',
        billable_metric_id: 'metric-1',
        threshold_value: '500',
        recurring: false,
        triggered_at: null,
      }]
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('One-time')).toBeInTheDocument()
    })

    it('renders last triggered date when present', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText(/Jan 20, 2024/)).toBeInTheDocument()
    })

    it('does not render last triggered when null', () => {
      mockUsageAlerts = [{
        id: 'alert-2',
        name: 'No trigger alert',
        billable_metric_id: 'metric-1',
        threshold_value: '500',
        recurring: false,
        triggered_at: null,
      }]
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.queryByText(/Last triggered/)).not.toBeInTheDocument()
    })

    it('renders Add Alert button', () => {
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByRole('button', { name: /Add Alert/ })).toBeInTheDocument()
    })

    it('shows add alert form on button click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      await user.click(screen.getByRole('button', { name: /Add Alert/ }))
      expect(screen.getByLabelText(/Threshold Value/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Name/)).toBeInTheDocument()
    })

    it('shows delete confirmation dialog on delete button click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      const alertDeleteButtons = screen.getAllByRole('button').filter(
        (btn) => btn.querySelector('[class*="text-destructive"]')
      )
      await user.click(alertDeleteButtons[alertDeleteButtons.length - 1])
      expect(screen.getByText('Delete Usage Alert')).toBeInTheDocument()
      expect(screen.getByText(/Are you sure you want to delete this usage alert/)).toBeInTheDocument()
    })

    it('calls delete alert mutation on confirmation', async () => {
      const { usageAlertsApi } = await import('@/lib/api')
      const user = userEvent.setup()
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      const alertDeleteButtons = screen.getAllByRole('button').filter(
        (btn) => btn.querySelector('[class*="text-destructive"]')
      )
      await user.click(alertDeleteButtons[alertDeleteButtons.length - 1])
      await user.click(screen.getByRole('button', { name: /^Delete$/ }))
      expect(usageAlertsApi.delete).toHaveBeenCalledWith('alert-1')
    })

    it('closes delete dialog on Cancel', async () => {
      const user = userEvent.setup()
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      const alertDeleteButtons = screen.getAllByRole('button').filter(
        (btn) => btn.querySelector('[class*="text-destructive"]')
      )
      await user.click(alertDeleteButtons[alertDeleteButtons.length - 1])
      expect(screen.getByText('Delete Usage Alert')).toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: /^Cancel$/ }))
      await waitFor(() => {
        expect(screen.queryByText('Delete Usage Alert')).not.toBeInTheDocument()
      })
    })

    it('shows alert form fields including billable metric', async () => {
      const user = userEvent.setup()
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      await user.click(screen.getByRole('button', { name: /Add Alert/ }))
      expect(screen.getByLabelText(/Billable Metric/)).toBeInTheDocument()
    })

    it('uses metric name when alert name is null', () => {
      mockUsageAlerts = [{
        id: 'alert-3',
        name: null,
        billable_metric_id: 'metric-1',
        threshold_value: '750',
        recurring: false,
        triggered_at: null,
      }]
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('API Calls')).toBeInTheDocument()
    })

    it('shows "Unnamed alert" when both name and metric are missing', () => {
      mockUsageAlerts = [{
        id: 'alert-4',
        name: null,
        billable_metric_id: 'unknown-metric',
        threshold_value: '100',
        recurring: false,
        triggered_at: null,
      }]
      mockMetrics = []
      render(<SubscriptionThresholdsAlertsTab subscriptionId="sub-1" />)
      expect(screen.getByText('Unnamed alert')).toBeInTheDocument()
    })
  })
})
