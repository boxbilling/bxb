import { describe, test, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from './test/test-utils'

// Ensure localStorage is available in jsdom
beforeAll(() => {
  if (typeof globalThis.localStorage === 'undefined' || typeof globalThis.localStorage.getItem !== 'function') {
    const store: Record<string, string> = {}
    globalThis.localStorage = {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, value: string) => { store[key] = value },
      removeItem: (key: string) => { delete store[key] },
      clear: () => { Object.keys(store).forEach(k => delete store[k]) },
      get length() { return Object.keys(store).length },
      key: (i: number) => Object.keys(store)[i] ?? null,
    }
  }
})

// Mock the API module so components don't make real HTTP calls
vi.mock('@/lib/api', () => ({
  organizationsApi: {
    getCurrent: vi.fn().mockResolvedValue({
      id: 'org-1',
      name: 'Test Org',
      default_currency: 'usd',
      timezone: 'UTC',
    }),
  },
  billingEntitiesApi: {
    list: vi.fn().mockResolvedValue([]),
  },
  plansApi: {
    list: vi.fn().mockResolvedValue([]),
  },
  searchApi: {
    search: vi.fn().mockResolvedValue([]),
  },
  notificationsApi: {
    getUnreadCount: vi.fn().mockResolvedValue({ count: 0 }),
    list: vi.fn().mockResolvedValue([]),
  },
  dashboardApi: {
    getStats: vi.fn().mockResolvedValue({}),
    getRevenueMetrics: vi.fn().mockResolvedValue({}),
    getCustomerMetrics: vi.fn().mockResolvedValue({}),
    getSubscriptionMetrics: vi.fn().mockResolvedValue({}),
    getUsageMetrics: vi.fn().mockResolvedValue({}),
    getRecentActivity: vi.fn().mockResolvedValue([]),
  },
  getActiveOrganizationId: vi.fn().mockReturnValue('org-1'),
  setActiveOrganizationId: vi.fn(),
}))

describe('Smoke tests', () => {
  test('app renders without crashing', async () => {
    const { default: App } = await import('./App')
    // App uses lazy-loaded routes + Suspense; rendering it should not throw
    const { container } = render(<App />)
    expect(container).toBeTruthy()
  })

  test('onboarding page renders', async () => {
    const { default: OnboardingPage } = await import(
      './pages/admin/OnboardingPage'
    )
    render(<OnboardingPage />)

    await waitFor(() => {
      expect(screen.getByText('Get Started')).toBeInTheDocument()
    })

    expect(screen.getByText(/Organization Details/)).toBeInTheDocument()
    expect(screen.getByText(/Create a Billing Entity/)).toBeInTheDocument()
    expect(screen.getByText(/Create a Plan/)).toBeInTheDocument()
  })
})
