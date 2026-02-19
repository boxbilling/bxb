import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@/test/test-utils'

import { SubscriptionEntitlementsTab } from './SubscriptionEntitlementsTab'

vi.mock('@/lib/api', () => ({
  subscriptionsApi: { getEntitlements: vi.fn() },
  featuresApi: { list: vi.fn() },
}))

interface Entitlement {
  id: string
  feature_id: string
  value: string
}

interface Feature {
  id: string
  name: string
  code: string
  feature_type: string
}

let mockEntitlements: Entitlement[] | undefined
let mockEntitlementsLoading: boolean
let mockFeatures: Feature[] | undefined

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual('@tanstack/react-query')
  return {
    ...actual,
    useQuery: (options: { queryKey: string[]; enabled?: boolean }) => {
      if (options.queryKey[0] === 'subscription-entitlements') {
        return { data: mockEntitlements, isLoading: mockEntitlementsLoading }
      }
      if (options.queryKey[0] === 'features') {
        if (options.enabled === false) return { data: undefined, isLoading: false }
        return { data: mockFeatures, isLoading: false }
      }
      return { data: undefined, isLoading: false }
    },
  }
})

describe('SubscriptionEntitlementsTab', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockEntitlements = [
      { id: 'ent-1', feature_id: 'feat-1', value: 'true' },
      { id: 'ent-2', feature_id: 'feat-2', value: '100' },
      { id: 'ent-3', feature_id: 'feat-3', value: 'premium' },
    ]
    mockEntitlementsLoading = false
    mockFeatures = [
      { id: 'feat-1', name: 'SSO', code: 'sso', feature_type: 'boolean' },
      { id: 'feat-2', name: 'API Rate Limit', code: 'api_rate_limit', feature_type: 'quantity' },
      { id: 'feat-3', name: 'Support Tier', code: 'support_tier', feature_type: 'string' },
    ]
  })

  describe('loading state', () => {
    it('renders skeletons when entitlements are loading', () => {
      mockEntitlementsLoading = true
      const { container } = render(
        <SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />
      )
      const skeletons = container.querySelectorAll('[class*="animate-pulse"], [data-slot="skeleton"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  describe('empty state', () => {
    it('renders empty message when no entitlements', () => {
      mockEntitlements = []
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('No features configured for this plan.')).toBeInTheDocument()
    })

    it('renders empty message when entitlements undefined', () => {
      mockEntitlements = undefined
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('No features configured for this plan.')).toBeInTheDocument()
    })
  })

  describe('entitlements table', () => {
    it('renders Entitlements heading', () => {
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('Entitlements')).toBeInTheDocument()
    })

    it('renders Manage Features link', () => {
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      const link = screen.getByRole('link', { name: /Manage Features/ })
      expect(link).toHaveAttribute('href', '/admin/features')
    })

    it('renders feature names', () => {
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('SSO')).toBeInTheDocument()
      expect(screen.getByText('API Rate Limit')).toBeInTheDocument()
      expect(screen.getByText('Support Tier')).toBeInTheDocument()
    })

    it('renders feature codes', () => {
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('sso')).toBeInTheDocument()
      expect(screen.getByText('api_rate_limit')).toBeInTheDocument()
      expect(screen.getByText('support_tier')).toBeInTheDocument()
    })

    it('renders feature type badges', () => {
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('boolean')).toBeInTheDocument()
      expect(screen.getByText('quantity')).toBeInTheDocument()
      expect(screen.getByText('string')).toBeInTheDocument()
    })

    it('renders "Enabled" for boolean feature with value true', () => {
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('Enabled')).toBeInTheDocument()
    })

    it('renders "Disabled" for boolean feature with value false', () => {
      mockEntitlements = [
        { id: 'ent-1', feature_id: 'feat-1', value: 'false' },
      ]
      mockFeatures = [
        { id: 'feat-1', name: 'SSO', code: 'sso', feature_type: 'boolean' },
      ]
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('Disabled')).toBeInTheDocument()
    })

    it('renders raw value for non-boolean features', () => {
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('100')).toBeInTheDocument()
      expect(screen.getByText('premium')).toBeInTheDocument()
    })

    it('renders "Unknown" for feature not found in map', () => {
      mockEntitlements = [
        { id: 'ent-4', feature_id: 'unknown-feat', value: 'some_value' },
      ]
      mockFeatures = []
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('Unknown')).toBeInTheDocument()
    })

    it('renders feature_id as code when feature not found', () => {
      mockEntitlements = [
        { id: 'ent-4', feature_id: 'unknown-feat', value: 'some_value' },
      ]
      mockFeatures = []
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('unknown-feat')).toBeInTheDocument()
    })

    it('renders dash for feature type when feature not found', () => {
      mockEntitlements = [
        { id: 'ent-4', feature_id: 'unknown-feat', value: 'some_value' },
      ]
      mockFeatures = []
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('\u2014')).toBeInTheDocument()
    })

    it('renders table headers', () => {
      render(<SubscriptionEntitlementsTab subscriptionExternalId="sub-ext-1" />)
      expect(screen.getByText('Feature')).toBeInTheDocument()
      expect(screen.getByText('Code')).toBeInTheDocument()
      expect(screen.getByText('Type')).toBeInTheDocument()
      expect(screen.getByText('Value')).toBeInTheDocument()
    })
  })
})
