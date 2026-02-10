// Billing domain types for bxb

export interface Customer {
  id: string
  external_id: string
  name: string
  email: string | null
  phone: string | null
  address_line1: string | null
  address_line2: string | null
  city: string | null
  state: string | null
  postal_code: string | null
  country: string | null
  currency: string
  timezone: string
  metadata: Record<string, string>
  created_at: string
  updated_at: string
}

export interface CustomerCreate {
  external_id: string
  name: string
  email?: string | null
  phone?: string | null
  address_line1?: string | null
  address_line2?: string | null
  city?: string | null
  state?: string | null
  postal_code?: string | null
  country?: string | null
  currency?: string
  timezone?: string
  metadata?: Record<string, string>
}

export interface CustomerUpdate {
  name?: string
  email?: string | null
  phone?: string | null
  address_line1?: string | null
  address_line2?: string | null
  city?: string | null
  state?: string | null
  postal_code?: string | null
  country?: string | null
  currency?: string
  timezone?: string
  metadata?: Record<string, string>
}

export type AggregationType = 'count' | 'sum' | 'max' | 'unique_count' | 'latest'

export interface BillableMetric {
  id: string
  code: string
  name: string
  description: string | null
  aggregation_type: AggregationType
  field_name: string | null
  recurring: boolean
  created_at: string
  updated_at: string
}

export interface BillableMetricCreate {
  code: string
  name: string
  description?: string | null
  aggregation_type: AggregationType
  field_name?: string | null
  recurring?: boolean
}

export interface BillableMetricUpdate {
  name?: string
  description?: string | null
  aggregation_type?: AggregationType
  field_name?: string | null
  recurring?: boolean
}

export type ChargeModel = 'standard' | 'graduated' | 'volume' | 'package' | 'percentage'

export interface GraduatedTier {
  from_value: number
  to_value: number | null
  per_unit_amount: string
  flat_amount: string
}

export interface Charge {
  id: string
  billable_metric_id: string
  billable_metric?: BillableMetric
  charge_model: ChargeModel
  amount: string | null
  properties: {
    graduated_tiers?: GraduatedTier[]
    volume_ranges?: GraduatedTier[]
    package_size?: number
    free_units?: number
    rate?: string
    fixed_amount?: string
  }
  min_amount_cents: number | null
  created_at: string
  updated_at: string
}

export interface ChargeCreate {
  billable_metric_id: string
  charge_model: ChargeModel
  amount?: string | null
  properties?: Charge['properties']
  min_amount_cents?: number | null
}

export type PlanInterval = 'weekly' | 'monthly' | 'quarterly' | 'yearly'

export interface Plan {
  id: string
  code: string
  name: string
  description: string | null
  amount_cents: number
  amount_currency: string
  interval: PlanInterval
  pay_in_advance: boolean
  trial_period_days: number | null
  charges: Charge[]
  active_subscriptions_count: number
  created_at: string
  updated_at: string
}

export interface PlanCreate {
  code: string
  name: string
  description?: string | null
  amount_cents: number
  amount_currency?: string
  interval: PlanInterval
  pay_in_advance?: boolean
  trial_period_days?: number | null
  charges?: ChargeCreate[]
}

export interface PlanUpdate {
  name?: string
  description?: string | null
  amount_cents?: number
  amount_currency?: string
  pay_in_advance?: boolean
  trial_period_days?: number | null
}

export type SubscriptionStatus = 'pending' | 'active' | 'canceled' | 'terminated'

export interface Subscription {
  id: string
  external_id: string
  customer_id: string
  customer?: Customer
  plan_id: string
  plan?: Plan
  status: SubscriptionStatus
  billing_time: 'calendar' | 'anniversary'
  started_at: string
  ending_at: string | null
  canceled_at: string | null
  terminated_at: string | null
  created_at: string
  updated_at: string
}

export interface SubscriptionCreate {
  external_id: string
  customer_id: string
  plan_id: string
  billing_time?: 'calendar' | 'anniversary'
  started_at?: string
}

export type InvoiceStatus = 'draft' | 'finalized' | 'paid' | 'voided'

export interface InvoiceLineItem {
  id: string
  description: string
  amount_cents: number
  quantity: number
  unit_amount_cents: number
}

export interface Invoice {
  id: string
  number: string
  customer_id: string
  customer?: Customer
  subscription_id: string | null
  subscription?: Subscription
  status: InvoiceStatus
  issuing_date: string
  payment_due_date: string
  amount_cents: number
  amount_currency: string
  taxes_amount_cents: number
  total_amount_cents: number
  line_items: InvoiceLineItem[]
  created_at: string
  updated_at: string
}

export interface DashboardStats {
  total_customers: number
  active_subscriptions: number
  monthly_recurring_revenue: number
  total_invoiced: number
  currency: string
}

export interface RecentActivity {
  id: string
  type: 'customer_created' | 'subscription_created' | 'invoice_finalized' | 'payment_received'
  description: string
  timestamp: string
}

export interface PaginatedResponse<T> {
  data: T[]
  meta: {
    total: number
    page: number
    per_page: number
    total_pages: number
  }
}
