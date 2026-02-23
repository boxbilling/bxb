import type { Subscription, Customer, Plan, BillingEntity } from '@/lib/api'

export function buildSubscription(overrides: Partial<Subscription> = {}): Subscription {
  return {
    id: 'sub-uuid-1',
    external_id: 'sub_ext_001',
    customer_id: 'cust-uuid-1',
    plan_id: 'plan-uuid-1',
    status: 'active',
    billing_time: 'calendar',
    trial_period_days: 0,
    trial_ended_at: null,
    subscription_at: null,
    pay_in_advance: false,
    previous_plan_id: null,
    downgraded_at: null,
    on_termination_action: 'generate_last_invoice',
    started_at: '2024-01-15T10:00:00Z',
    ending_at: null,
    canceled_at: null,
    paused_at: null,
    resumed_at: null,
    created_at: '2024-01-10T08:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
    ...overrides,
  }
}

export function buildCustomer(overrides: Partial<Customer> = {}): Customer {
  return {
    id: 'cust-uuid-1',
    external_id: 'cust_ext_001',
    name: 'Acme Corp',
    email: 'billing@acme.com',
    currency: 'usd',
    timezone: 'UTC',
    billing_metadata: {},
    invoice_grace_period: 0,
    net_payment_term: 30,
    billing_entity_id: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}

export function buildPlan(overrides: Partial<Plan> = {}): Plan {
  return {
    id: 'plan-uuid-1',
    code: 'pro_monthly',
    name: 'Pro Monthly',
    description: 'Professional monthly plan',
    interval: 'monthly',
    amount_cents: 9900,
    currency: 'usd',
    trial_period_days: 0,
    charges: [],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}

export function buildBillingEntity(overrides: Partial<BillingEntity> = {}): BillingEntity {
  return {
    id: 'be-uuid-1',
    code: 'be_default',
    name: 'Default Entity',
    legal_name: null,
    address_line1: null,
    address_line2: null,
    city: null,
    state: null,
    country: null,
    zip_code: null,
    tax_id: null,
    email: null,
    currency: 'usd',
    timezone: 'UTC',
    document_locale: 'en',
    invoice_prefix: null,
    next_invoice_number: 1,
    invoice_grace_period: 0,
    net_payment_term: 30,
    invoice_footer: null,
    is_default: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}
