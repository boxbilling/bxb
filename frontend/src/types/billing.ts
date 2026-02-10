// Billing domain types for bxb
// Re-export generated schema types for convenience
import type { components } from '@/lib/schema'

// Type aliases for easier usage
export type Customer = components['schemas']['CustomerResponse']
export type CustomerCreate = components['schemas']['CustomerCreate']
export type CustomerUpdate = components['schemas']['CustomerUpdate']

export type BillableMetric = components['schemas']['BillableMetricResponse']
export type BillableMetricCreate = components['schemas']['BillableMetricCreate']
export type BillableMetricUpdate = components['schemas']['BillableMetricUpdate']
export type AggregationType = components['schemas']['AggregationType']

export type Plan = components['schemas']['PlanResponse']
export type PlanCreate = components['schemas']['PlanCreate']
export type PlanUpdate = components['schemas']['PlanUpdate']
export type PlanInterval = components['schemas']['PlanInterval']

export type Charge = components['schemas']['ChargeOutput']
export type ChargeInput = components['schemas']['ChargeInput']
export type ChargeModel = components['schemas']['ChargeModel']

export type Subscription = components['schemas']['SubscriptionResponse']
export type SubscriptionCreate = components['schemas']['SubscriptionCreate']
export type SubscriptionUpdate = components['schemas']['SubscriptionUpdate']
export type SubscriptionStatus = components['schemas']['SubscriptionStatus']

// Dashboard types (not in backend yet, keep for UI)
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

// Invoice types (not in backend yet, keep for UI)
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
