import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/test-utils'

import OnboardingPage from './OnboardingPage'

const mockGetCurrent = vi.fn()
const mockListBillingEntities = vi.fn()
const mockListPlans = vi.fn()

vi.mock('@/lib/api', () => ({
  organizationsApi: {
    getCurrent: (...args: unknown[]) => mockGetCurrent(...args),
  },
  billingEntitiesApi: {
    list: (...args: unknown[]) => mockListBillingEntities(...args),
  },
  plansApi: {
    list: (...args: unknown[]) => mockListPlans(...args),
  },
}))

const completeOrg = {
  id: 'org-1',
  name: 'Acme Corp',
  default_currency: 'USD',
  timezone: 'UTC',
  logo_url: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const incompleteOrg = {
  id: 'org-2',
  name: '',
  default_currency: null,
  timezone: null,
  logo_url: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const billingEntity = {
  id: 'be-1',
  code: 'default',
  name: 'Default Entity',
  currency: 'USD',
  timezone: 'UTC',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

const plan = {
  id: 'plan-1',
  code: 'pro',
  name: 'Pro Plan',
  interval: 'monthly',
  amount_cents: 9900,
  currency: 'USD',
  charges: [],
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

describe('OnboardingPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  describe('loading state', () => {
    it('renders loading skeletons while data is fetching', () => {
      mockGetCurrent.mockReturnValue(new Promise(() => {}))
      mockListBillingEntities.mockReturnValue(new Promise(() => {}))
      mockListPlans.mockReturnValue(new Promise(() => {}))

      render(<OnboardingPage />)

      // Should not show the page header yet; skeletons should be visible
      expect(screen.queryByText('Get Started')).not.toBeInTheDocument()
    })
  })

  describe('all steps incomplete', () => {
    beforeEach(() => {
      mockGetCurrent.mockResolvedValue(incompleteOrg)
      mockListBillingEntities.mockResolvedValue([])
      mockListPlans.mockResolvedValue([])
    })

    it('renders the page header', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(screen.getByText('Get Started')).toBeInTheDocument()
      })
      expect(
        screen.getByText('Complete these steps to start billing your customers'),
      ).toBeInTheDocument()
    })

    it('shows 0 of 3 steps completed', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(screen.getByText('0 of 3 steps completed')).toBeInTheDocument()
      })
      expect(screen.getByText('0%')).toBeInTheDocument()
    })

    it('shows the incomplete message', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(
          screen.getByText(
            'Complete the remaining steps to start billing your customers.',
          ),
        ).toBeInTheDocument()
      })
    })

    it('renders all three onboarding steps', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(screen.getByText('Organization Details')).toBeInTheDocument()
      })
      expect(screen.getByText('Create a Billing Entity')).toBeInTheDocument()
      expect(screen.getByText('Create a Plan')).toBeInTheDocument()
    })

    it('shows Pending badges for all steps', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(screen.getAllByText('Pending')).toHaveLength(3)
      })
    })

    it('shows action buttons for incomplete steps', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(
          screen.getByRole('link', { name: /Configure organization/ }),
        ).toBeInTheDocument()
      })
      expect(
        screen.getByRole('link', { name: /Create billing entity/ }),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('link', { name: /Create a plan/ }),
      ).toBeInTheDocument()
    })

    it('links to correct pages', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(
          screen.getByRole('link', { name: /Configure organization/ }),
        ).toHaveAttribute('href', '/admin/settings')
      })
      expect(
        screen.getByRole('link', { name: /Create billing entity/ }),
      ).toHaveAttribute('href', '/admin/billing-entities/new')
      expect(
        screen.getByRole('link', { name: /Create a plan/ }),
      ).toHaveAttribute('href', '/admin/plans')
    })
  })

  describe('all steps complete', () => {
    beforeEach(() => {
      mockGetCurrent.mockResolvedValue(completeOrg)
      mockListBillingEntities.mockResolvedValue([billingEntity])
      mockListPlans.mockResolvedValue([plan])
    })

    it('shows 3 of 3 steps completed', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(screen.getByText('3 of 3 steps completed')).toBeInTheDocument()
      })
      expect(screen.getByText('100%')).toBeInTheDocument()
    })

    it('shows the all-complete message', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(
          screen.getByText(
            'All set! Your organization is ready to start billing.',
          ),
        ).toBeInTheDocument()
      })
    })

    it('shows Complete badges for all steps', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(screen.getAllByText('Complete')).toHaveLength(3)
      })
    })

    it('shows review/view action labels when steps are complete', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(
          screen.getByRole('link', { name: /Review settings/ }),
        ).toBeInTheDocument()
      })
      expect(
        screen.getByRole('link', { name: /View billing entities/ }),
      ).toBeInTheDocument()
      expect(
        screen.getByRole('link', { name: /View plans/ }),
      ).toBeInTheDocument()
    })
  })

  describe('partial completion', () => {
    it('shows correct count when only org is complete', async () => {
      mockGetCurrent.mockResolvedValue(completeOrg)
      mockListBillingEntities.mockResolvedValue([])
      mockListPlans.mockResolvedValue([])

      render(<OnboardingPage />)
      await waitFor(() => {
        expect(screen.getByText('1 of 3 steps completed')).toBeInTheDocument()
      })
      expect(screen.getByText('33%')).toBeInTheDocument()
    })

    it('shows correct count when org and billing entity are complete', async () => {
      mockGetCurrent.mockResolvedValue(completeOrg)
      mockListBillingEntities.mockResolvedValue([billingEntity])
      mockListPlans.mockResolvedValue([])

      render(<OnboardingPage />)
      await waitFor(() => {
        expect(screen.getByText('2 of 3 steps completed')).toBeInTheDocument()
      })
      expect(screen.getByText('67%')).toBeInTheDocument()
    })

    it('shows a mix of Complete and Pending badges', async () => {
      mockGetCurrent.mockResolvedValue(completeOrg)
      mockListBillingEntities.mockResolvedValue([billingEntity])
      mockListPlans.mockResolvedValue([])

      render(<OnboardingPage />)
      await waitFor(() => {
        expect(screen.getAllByText('Complete')).toHaveLength(2)
      })
      expect(screen.getAllByText('Pending')).toHaveLength(1)
    })
  })

  describe('step descriptions', () => {
    beforeEach(() => {
      mockGetCurrent.mockResolvedValue(incompleteOrg)
      mockListBillingEntities.mockResolvedValue([])
      mockListPlans.mockResolvedValue([])
    })

    it('shows organization step description', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(
          screen.getByText(
            'Set up your organization name, default currency, and timezone.',
          ),
        ).toBeInTheDocument()
      })
    })

    it('shows billing entity step description', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(
          screen.getByText(
            'Add at least one billing entity with legal name and address for invoicing.',
          ),
        ).toBeInTheDocument()
      })
    })

    it('shows plan step description', async () => {
      render(<OnboardingPage />)
      await waitFor(() => {
        expect(
          screen.getByText(
            'Define a pricing plan with charges that you can assign to customers.',
          ),
        ).toBeInTheDocument()
      })
    })
  })
})
