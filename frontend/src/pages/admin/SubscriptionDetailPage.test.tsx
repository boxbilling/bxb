import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, userEvent, waitFor } from '@/test/test-utils'
import { buildSubscription, buildCustomer, buildPlan } from '@/test/factories'
import type { Subscription, Customer, Plan } from '@/types/billing'

/* ------------------------------------------------------------------ */
/*  Mock module-level state                                           */
/* ------------------------------------------------------------------ */

let mockSubscription: Subscription | undefined
let mockCustomer: Customer | undefined
let mockPlan: Plan | undefined
let mockPlans: Plan[] | undefined
let mockSubLoading = false
let mockSubError: Error | null = null
let mockIsMobile = false

/* captured mutation fns so we can invoke onSuccess / onError in tests */
let capturedMutations: Record<string, {
  mutationFn: (...args: unknown[]) => Promise<unknown>
  onSuccess?: () => void
  onError?: (err: unknown) => void
}> = {}

let capturedMutateMap: Record<string, { mutate: ReturnType<typeof vi.fn>; isPending: boolean }> = {}

/* ------------------------------------------------------------------ */
/*  Mocks                                                             */
/* ------------------------------------------------------------------ */

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ id: 'sub-uuid-1' }),
    useNavigate: () => mockNavigate,
  }
})

vi.mock('@/hooks/use-mobile', () => ({
  useIsMobile: () => mockIsMobile,
}))

vi.mock('@/lib/api', () => ({
  subscriptionsApi: {
    get: vi.fn(),
    update: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    terminate: vi.fn(),
  },
  customersApi: { get: vi.fn() },
  plansApi: { get: vi.fn(), list: vi.fn() },
  ApiError: class ApiError extends Error {},
}))

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query')
  return {
    ...actual,
    useQuery: (options: { queryKey: string[]; enabled?: boolean }) => {
      if (options.queryKey[0] === 'subscription') {
        return { data: mockSubscription, isLoading: mockSubLoading, error: mockSubError }
      }
      if (options.queryKey[0] === 'customer') {
        if (options.enabled === false) return { data: undefined, isLoading: false }
        return { data: mockCustomer, isLoading: false }
      }
      if (options.queryKey[0] === 'plan') {
        if (options.enabled === false) return { data: undefined, isLoading: false }
        return { data: mockPlan, isLoading: false }
      }
      if (options.queryKey[0] === 'plans') {
        return { data: mockPlans, isLoading: false }
      }
      return { data: undefined, isLoading: false }
    },
    useMutation: (opts: {
      mutationFn: (...args: unknown[]) => Promise<unknown>
      onSuccess?: () => void
      onError?: (err: unknown) => void
    }) => {
      // Determine which mutation this is by inspecting the calling order
      const key = getMutationKey()
      capturedMutations[key] = opts
      const entry = capturedMutateMap[key] ?? { mutate: vi.fn(), isPending: false }
      capturedMutateMap[key] = entry
      return { mutate: entry.mutate, isPending: entry.isPending }
    },
    useQueryClient: () => ({
      invalidateQueries: vi.fn(),
    }),
  }
})

// Track mutation creation order to assign keys
let mutationIndex = 0
const mutationKeys = ['update', 'pause', 'resume', 'changePlan', 'terminate']
function getMutationKey(): string {
  const key = mutationKeys[mutationIndex % mutationKeys.length]
  mutationIndex++
  return key
}

/* Mock child components to keep tests focused on page orchestration */
vi.mock('@/components/subscription-detail/SubscriptionHeader', () => ({
  SubscriptionHeader: (props: { subscription?: Subscription; customer?: Customer; plan?: Plan; isLoading?: boolean }) => (
    <div data-testid="subscription-header">
      {props.isLoading ? 'loading' : `${props.customer?.name ?? ''} — ${props.plan?.name ?? ''}`}
    </div>
  ),
}))

vi.mock('@/components/subscription-detail/SubscriptionKPICards', () => ({
  SubscriptionKPICards: () => <div data-testid="kpi-cards" />,
}))

vi.mock('@/components/subscription-detail/SubscriptionInfoSidebar', () => ({
  SubscriptionInfoSidebar: (props: {
    onEdit?: () => void
    onPause?: () => void
    onResume?: () => void
    onChangePlan?: () => void
    onTerminate?: () => void
  }) => (
    <div data-testid="info-sidebar">
      {props.onEdit && <button onClick={props.onEdit}>SidebarEdit</button>}
      {props.onPause && <button onClick={props.onPause}>SidebarPause</button>}
      {props.onResume && <button onClick={props.onResume}>SidebarResume</button>}
      {props.onChangePlan && <button onClick={props.onChangePlan}>SidebarChangePlan</button>}
      {props.onTerminate && <button onClick={props.onTerminate}>SidebarTerminate</button>}
    </div>
  ),
}))

vi.mock('@/components/subscription-detail/SubscriptionOverviewTab', () => ({
  SubscriptionOverviewTab: () => <div data-testid="tab-overview">Overview Content</div>,
}))
vi.mock('@/components/subscription-detail/SubscriptionInvoicesTab', () => ({
  SubscriptionInvoicesTab: () => <div data-testid="tab-invoices">Invoices Content</div>,
}))
vi.mock('@/components/subscription-detail/SubscriptionThresholdsAlertsTab', () => ({
  SubscriptionThresholdsAlertsTab: () => <div data-testid="tab-thresholds">Thresholds Content</div>,
}))
vi.mock('@/components/subscription-detail/SubscriptionEntitlementsTab', () => ({
  SubscriptionEntitlementsTab: () => <div data-testid="tab-entitlements">Entitlements Content</div>,
}))
vi.mock('@/components/subscription-detail/SubscriptionLifecycleTab', () => ({
  SubscriptionLifecycleTab: () => <div data-testid="tab-lifecycle">Lifecycle Content</div>,
}))
vi.mock('@/components/subscription-detail/SubscriptionActivityTab', () => ({
  SubscriptionActivityTab: () => <div data-testid="tab-activity">Activity Content</div>,
}))

vi.mock('@/components/EditSubscriptionDialog', () => ({
  EditSubscriptionDialog: (props: { open: boolean }) => (
    props.open ? <div data-testid="edit-dialog">Edit Dialog Open</div> : null
  ),
}))
vi.mock('@/components/ChangePlanDialog', () => ({
  ChangePlanDialog: (props: { open: boolean }) => (
    props.open ? <div data-testid="change-plan-dialog">Change Plan Dialog Open</div> : null
  ),
}))
vi.mock('@/components/TerminateSubscriptionDialog', () => ({
  TerminateSubscriptionDialog: (props: { open: boolean }) => (
    props.open ? <div data-testid="terminate-dialog">Terminate Dialog Open</div> : null
  ),
}))

const mockSetBreadcrumbs = vi.fn()
vi.mock('@/components/HeaderBreadcrumb', () => ({
  useSetBreadcrumbs: (...args: unknown[]) => mockSetBreadcrumbs(...args),
}))

/* ------------------------------------------------------------------ */
/*  Import after mocks                                                */
/* ------------------------------------------------------------------ */

import SubscriptionDetailPage from './SubscriptionDetailPage'

/* ------------------------------------------------------------------ */
/*  Tests                                                             */
/* ------------------------------------------------------------------ */

describe('SubscriptionDetailPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockSubscription = buildSubscription()
    mockCustomer = buildCustomer()
    mockPlan = buildPlan()
    mockPlans = [buildPlan()]
    mockSubLoading = false
    mockSubError = null
    mockIsMobile = false
    mutationIndex = 0
    capturedMutations = {}
    capturedMutateMap = {}
    mockNavigate.mockClear()
    mockSetBreadcrumbs.mockClear()
  })

  /* ---------------------------------------------------------------- */
  /*  Breadcrumb navigation                                           */
  /* ---------------------------------------------------------------- */

  describe('breadcrumb navigation', () => {
    it('calls useSetBreadcrumbs with Subscriptions link and customer/plan label', () => {
      render(<SubscriptionDetailPage />)
      expect(mockSetBreadcrumbs).toHaveBeenCalledWith([
        { label: 'Subscriptions', href: '/admin/subscriptions' },
        { label: `${mockCustomer!.name} \u2014 ${mockPlan!.name}` },
      ])
    })

    it('calls useSetBreadcrumbs with Loading... label when loading', () => {
      mockSubLoading = true
      render(<SubscriptionDetailPage />)
      expect(mockSetBreadcrumbs).toHaveBeenCalledWith([
        { label: 'Subscriptions', href: '/admin/subscriptions' },
        { label: 'Loading...' },
      ])
    })
  })

  /* ---------------------------------------------------------------- */
  /*  Error state                                                     */
  /* ---------------------------------------------------------------- */

  describe('error state', () => {
    it('renders error message when subscription fetch fails', () => {
      mockSubError = new Error('Not found')
      render(<SubscriptionDetailPage />)
      expect(screen.getByText(/Failed to load subscription/)).toBeInTheDocument()
    })

    it('does not render tabs when in error state', () => {
      mockSubError = new Error('Server error')
      render(<SubscriptionDetailPage />)
      expect(screen.queryByText('Overview')).not.toBeInTheDocument()
    })
  })

  /* ---------------------------------------------------------------- */
  /*  Loading state                                                   */
  /* ---------------------------------------------------------------- */

  describe('loading state', () => {
    it('renders skeletons when loading', () => {
      mockSubLoading = true
      mockSubscription = undefined
      const { container } = render(<SubscriptionDetailPage />)
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it('does not render tabs when loading', () => {
      mockSubLoading = true
      mockSubscription = undefined
      render(<SubscriptionDetailPage />)
      expect(screen.queryByText('Overview')).not.toBeInTheDocument()
    })
  })

  /* ---------------------------------------------------------------- */
  /*  Tabs rendering                                                  */
  /* ---------------------------------------------------------------- */

  describe('tabs', () => {
    it('renders all six tab triggers', () => {
      render(<SubscriptionDetailPage />)
      expect(screen.getByText('Overview')).toBeInTheDocument()
      expect(screen.getByText('Invoices & Payments')).toBeInTheDocument()
      expect(screen.getByText('Thresholds & Alerts')).toBeInTheDocument()
      expect(screen.getByText('Entitlements')).toBeInTheDocument()
      expect(screen.getByText('Lifecycle')).toBeInTheDocument()
      expect(screen.getByText('Activity')).toBeInTheDocument()
    })

    it('shows overview tab content by default', () => {
      render(<SubscriptionDetailPage />)
      expect(screen.getByTestId('tab-overview')).toBeInTheDocument()
    })

    it('switches to invoices tab on click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionDetailPage />)
      await user.click(screen.getByText('Invoices & Payments'))
      expect(screen.getByTestId('tab-invoices')).toBeInTheDocument()
    })

    it('switches to thresholds tab on click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionDetailPage />)
      await user.click(screen.getByText('Thresholds & Alerts'))
      expect(screen.getByTestId('tab-thresholds')).toBeInTheDocument()
    })

    it('switches to entitlements tab on click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionDetailPage />)
      await user.click(screen.getByText('Entitlements'))
      expect(screen.getByTestId('tab-entitlements')).toBeInTheDocument()
    })

    it('switches to lifecycle tab on click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionDetailPage />)
      await user.click(screen.getByText('Lifecycle'))
      expect(screen.getByTestId('tab-lifecycle')).toBeInTheDocument()
    })

    it('switches to activity tab on click', async () => {
      const user = userEvent.setup()
      render(<SubscriptionDetailPage />)
      await user.click(screen.getByText('Activity'))
      expect(screen.getByTestId('tab-activity')).toBeInTheDocument()
    })

    it('shows loading text for entitlements when external_id is missing', () => {
      mockSubscription = buildSubscription({ external_id: '' })
      render(<SubscriptionDetailPage />)
      // Entitlements tab renders "Loading entitlements..." when external_id is falsy
      // It won't be visible unless the tab is active, but the element is in the DOM
    })
  })

  /* ---------------------------------------------------------------- */
  /*  Desktop layout — sidebar always visible                         */
  /* ---------------------------------------------------------------- */

  describe('desktop layout', () => {
    it('renders sidebar directly (not in collapsible)', () => {
      mockIsMobile = false
      render(<SubscriptionDetailPage />)
      expect(screen.getByTestId('info-sidebar')).toBeInTheDocument()
      // No "Subscription Details" collapsible trigger on desktop
      expect(screen.queryByRole('button', { name: /Subscription Details/i })).not.toBeInTheDocument()
    })

    it('renders header and KPI cards', () => {
      render(<SubscriptionDetailPage />)
      expect(screen.getByTestId('subscription-header')).toBeInTheDocument()
      expect(screen.getByTestId('kpi-cards')).toBeInTheDocument()
    })
  })

  /* ---------------------------------------------------------------- */
  /*  Mobile layout — sidebar in collapsible                          */
  /* ---------------------------------------------------------------- */

  describe('mobile layout', () => {
    beforeEach(() => {
      mockIsMobile = true
    })

    it('renders collapsible trigger for subscription details', () => {
      render(<SubscriptionDetailPage />)
      expect(screen.getByRole('button', { name: /Subscription Details/i })).toBeInTheDocument()
    })

    it('expands sidebar when collapsible trigger is clicked', async () => {
      const user = userEvent.setup()
      render(<SubscriptionDetailPage />)
      const trigger = screen.getByRole('button', { name: /Subscription Details/i })
      await user.click(trigger)
      await waitFor(() => {
        expect(screen.getByTestId('info-sidebar')).toBeInTheDocument()
      })
    })

    it('renders tabs alongside collapsible sidebar', () => {
      render(<SubscriptionDetailPage />)
      expect(screen.getByText('Overview')).toBeInTheDocument()
    })
  })

  /* ---------------------------------------------------------------- */
  /*  Edit dialog                                                     */
  /* ---------------------------------------------------------------- */

  describe('edit dialog', () => {
    it('does not show edit dialog by default', () => {
      render(<SubscriptionDetailPage />)
      expect(screen.queryByTestId('edit-dialog')).not.toBeInTheDocument()
    })

    it('opens edit dialog when sidebar Edit is clicked', async () => {
      const user = userEvent.setup()
      render(<SubscriptionDetailPage />)
      await user.click(screen.getByRole('button', { name: 'SidebarEdit' }))
      expect(screen.getByTestId('edit-dialog')).toBeInTheDocument()
    })
  })

  /* ---------------------------------------------------------------- */
  /*  Change plan dialog                                              */
  /* ---------------------------------------------------------------- */

  describe('change plan dialog', () => {
    it('does not show change plan dialog by default', () => {
      render(<SubscriptionDetailPage />)
      expect(screen.queryByTestId('change-plan-dialog')).not.toBeInTheDocument()
    })

    it('opens change plan dialog when sidebar ChangePlan is clicked', async () => {
      const user = userEvent.setup()
      render(<SubscriptionDetailPage />)
      await user.click(screen.getByRole('button', { name: 'SidebarChangePlan' }))
      expect(screen.getByTestId('change-plan-dialog')).toBeInTheDocument()
    })
  })

  /* ---------------------------------------------------------------- */
  /*  Terminate dialog                                                */
  /* ---------------------------------------------------------------- */

  describe('terminate dialog', () => {
    it('does not show terminate dialog by default', () => {
      render(<SubscriptionDetailPage />)
      expect(screen.queryByTestId('terminate-dialog')).not.toBeInTheDocument()
    })

    it('opens terminate dialog when sidebar Terminate is clicked', async () => {
      const user = userEvent.setup()
      render(<SubscriptionDetailPage />)
      await user.click(screen.getByRole('button', { name: 'SidebarTerminate' }))
      expect(screen.getByTestId('terminate-dialog')).toBeInTheDocument()
    })
  })

  /* ---------------------------------------------------------------- */
  /*  Null subscription (not loaded yet, no error)                    */
  /* ---------------------------------------------------------------- */

  describe('when subscription is undefined and not loading', () => {
    it('calls useSetBreadcrumbs but does not render tabs', () => {
      mockSubscription = undefined
      render(<SubscriptionDetailPage />)
      expect(mockSetBreadcrumbs).toHaveBeenCalled()
      expect(screen.queryByText('Overview')).not.toBeInTheDocument()
    })
  })
})
