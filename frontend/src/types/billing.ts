// Billing domain types for bxb
// Re-export generated schema types for convenience
import type { components } from '@/lib/schema'

// --- Customers ---
export type Customer = components['schemas']['CustomerResponse']
export type CustomerCreate = components['schemas']['CustomerCreate']
export type CustomerUpdate = components['schemas']['CustomerUpdate']

// --- Billable Metrics ---
export type BillableMetric = components['schemas']['BillableMetricResponse']
export type BillableMetricCreate = components['schemas']['BillableMetricCreate']
export type BillableMetricUpdate = components['schemas']['BillableMetricUpdate']
export type AggregationType = components['schemas']['AggregationType']
export type BillableMetricFilter = components['schemas']['BillableMetricFilterResponse']
export type BillableMetricFilterCreate = components['schemas']['BillableMetricFilterCreate']

// --- Plans ---
export type Plan = components['schemas']['PlanResponse']
export type PlanCreate = components['schemas']['PlanCreate']
export type PlanUpdate = components['schemas']['PlanUpdate']
export type PlanInterval = components['schemas']['PlanInterval']

// --- Charges ---
export type Charge = components['schemas']['ChargeOutput']
export type ChargeInput = components['schemas']['ChargeInput']
export type ChargeModel = components['schemas']['ChargeModel']
export type ChargeFilterInput = components['schemas']['ChargeFilterInput']

// --- Subscriptions ---
export type Subscription = components['schemas']['SubscriptionResponse']
export type SubscriptionCreate = components['schemas']['SubscriptionCreate']
export type SubscriptionUpdate = components['schemas']['SubscriptionUpdate']
export type SubscriptionStatus = components['schemas']['SubscriptionStatus']
export type BillingTime = components['schemas']['BillingTime']
export type TerminationAction = components['schemas']['TerminationAction']

// --- Invoices ---
export type Invoice = components['schemas']['InvoiceResponse']
export type InvoiceUpdate = components['schemas']['InvoiceUpdate']
export type InvoiceStatus = components['schemas']['InvoiceStatus']

// --- Fees ---
export type Fee = components['schemas']['FeeResponse']
export type FeeUpdate = components['schemas']['FeeUpdate']
export type FeeType = components['schemas']['FeeType']
export type FeePaymentStatus = components['schemas']['FeePaymentStatus']

// --- Payments ---
export type Payment = components['schemas']['PaymentResponse']
export type PaymentStatus = components['schemas']['PaymentStatus']
export type PaymentProvider = components['schemas']['PaymentProvider']
export type CheckoutSessionCreate = components['schemas']['CheckoutSessionCreate']
export type CheckoutSessionResponse = components['schemas']['CheckoutSessionResponse']

// --- Wallets ---
export type Wallet = components['schemas']['WalletResponse']
export type WalletCreate = components['schemas']['WalletCreate']
export type WalletUpdate = components['schemas']['WalletUpdate']
export type WalletTopUp = components['schemas']['WalletTopUp']
export type WalletStatus = components['schemas']['WalletStatus']
export type WalletTransaction = components['schemas']['WalletTransactionResponse']

// --- Coupons ---
export type Coupon = components['schemas']['CouponResponse']
export type CouponCreate = components['schemas']['CouponCreate']
export type CouponUpdate = components['schemas']['CouponUpdate']
export type CouponType = components['schemas']['CouponType']
export type CouponFrequency = components['schemas']['CouponFrequency']
export type CouponStatus = components['schemas']['CouponStatus']
export type ApplyCouponRequest = components['schemas']['ApplyCouponRequest']
export type AppliedCoupon = components['schemas']['AppliedCouponResponse']

// --- Add-ons ---
export type AddOn = components['schemas']['AddOnResponse']
export type AddOnCreate = components['schemas']['AddOnCreate']
export type AddOnUpdate = components['schemas']['AddOnUpdate']
export type ApplyAddOnRequest = components['schemas']['ApplyAddOnRequest']
export type AppliedAddOn = components['schemas']['AppliedAddOnResponse']

// --- Credit Notes ---
export type CreditNote = components['schemas']['CreditNoteResponse']
export type CreditNoteCreate = components['schemas']['CreditNoteCreate']
export type CreditNoteUpdate = components['schemas']['CreditNoteUpdate']
export type CreditNoteItemCreate = components['schemas']['CreditNoteItemCreate']
export type CreditNoteStatus = components['schemas']['CreditNoteStatus']
export type CreditNoteType = components['schemas']['CreditNoteType']
export type CreditNoteReason = components['schemas']['CreditNoteReason']

// --- Taxes ---
export type Tax = components['schemas']['TaxResponse']
export type TaxCreate = components['schemas']['TaxCreate']
export type TaxUpdate = components['schemas']['TaxUpdate']
export type ApplyTaxRequest = components['schemas']['ApplyTaxRequest']
export type AppliedTax = components['schemas']['AppliedTaxResponse']

// --- Webhooks ---
export type WebhookEndpoint = components['schemas']['WebhookEndpointResponse']
export type WebhookEndpointCreate = components['schemas']['WebhookEndpointCreate']
export type WebhookEndpointUpdate = components['schemas']['WebhookEndpointUpdate']
export type Webhook = components['schemas']['WebhookResponse']

// --- Organizations ---
export type Organization = components['schemas']['OrganizationResponse']
export type OrganizationCreate = components['schemas']['OrganizationCreate']
export type OrganizationUpdate = components['schemas']['OrganizationUpdate']
export type ApiKeyCreate = components['schemas']['ApiKeyCreate']
export type ApiKeyCreateResponse = components['schemas']['ApiKeyCreateResponse']
export type ApiKey = components['schemas']['ApiKeyListResponse']

// --- Dunning Campaigns ---
export type DunningCampaign = components['schemas']['DunningCampaignResponse']
export type DunningCampaignCreate = components['schemas']['DunningCampaignCreate']
export type DunningCampaignUpdate = components['schemas']['DunningCampaignUpdate']
export type DunningCampaignThreshold = components['schemas']['DunningCampaignThresholdResponse']
export type DunningCampaignThresholdCreate = components['schemas']['DunningCampaignThresholdCreate']

// --- Commitments ---
export type Commitment = components['schemas']['CommitmentResponse']
export type CommitmentCreateAPI = components['schemas']['CommitmentCreateAPI']
export type CommitmentUpdate = components['schemas']['CommitmentUpdate']

// --- Usage Thresholds ---
export type UsageThreshold = components['schemas']['UsageThresholdResponse']
export type UsageThresholdCreateAPI = components['schemas']['UsageThresholdCreateAPI']
export type CurrentUsage = components['schemas']['app__schemas__usage_threshold__CurrentUsageResponse']

// --- Customer Usage ---
export type BillableMetricUsage = components['schemas']['BillableMetricUsage']
export type ChargeUsage = components['schemas']['ChargeUsage']
export type CustomerCurrentUsageResponse = components['schemas']['app__schemas__usage__CurrentUsageResponse']

// --- Integrations ---
export type Integration = components['schemas']['IntegrationResponse']
export type IntegrationCreate = components['schemas']['IntegrationCreate']
export type IntegrationUpdate = components['schemas']['IntegrationUpdate']

// --- Data Exports ---
export type DataExport = components['schemas']['DataExportResponse']
export type DataExportCreate = components['schemas']['DataExportCreate']
export type ExportType = components['schemas']['ExportType']

// --- Events ---
export type Event = components['schemas']['EventResponse']
export type EventCreate = components['schemas']['EventCreate']
export type EventBatchCreate = components['schemas']['EventBatchCreate']
export type EventBatchResponse = components['schemas']['EventBatchResponse']

// --- Payment Methods ---
export type PaymentMethod = components['schemas']['PaymentMethodResponse']
export type PaymentMethodCreate = components['schemas']['PaymentMethodCreate']
export type SetupSessionCreate = components['schemas']['SetupSessionCreate']
export type SetupSessionResponse = components['schemas']['SetupSessionResponse']

// --- Audit Logs ---
export type AuditLog = components['schemas']['AuditLogResponse']

// --- Billing Entities ---
export type BillingEntity = components['schemas']['BillingEntityResponse']
export type BillingEntityCreate = components['schemas']['BillingEntityCreate']
export type BillingEntityUpdate = components['schemas']['BillingEntityUpdate']

// --- Payment Requests ---
export type PaymentRequest = components['schemas']['PaymentRequestResponse']
export type PaymentRequestCreate = components['schemas']['PaymentRequestCreate']

// --- Invoice Preview ---
export type FeePreview = components['schemas']['FeePreview']
export type InvoicePreviewResponse = components['schemas']['InvoicePreviewResponse']
export type InvoicePreviewRequest = components['schemas']['InvoicePreviewRequest']

// --- Fee Estimation ---
export type EstimateFeesRequest = components['schemas']['EstimateFeesRequest']
export type EstimateFeesResponse = components['schemas']['EstimateFeesResponse']

// --- Dashboard types ---
export interface DashboardStats {
  total_customers: number
  active_subscriptions: number
  monthly_recurring_revenue: number
  total_invoiced: number
  total_wallet_credits: number
  currency: string
}

export interface RecentActivity {
  id: string
  type: 'customer_created' | 'subscription_created' | 'invoice_finalized' | 'payment_received'
  description: string
  timestamp: string
}

export interface RevenueDataPoint {
  month: string
  revenue: number
}

export interface RevenueMetrics {
  mrr: number
  total_revenue_this_month: number
  outstanding_invoices: number
  overdue_amount: number
  currency: string
  monthly_trend: RevenueDataPoint[]
}

export interface CustomerMetrics {
  total: number
  new_this_month: number
  churned_this_month: number
}

export interface SubscriptionPlanBreakdown {
  plan_name: string
  count: number
}

export interface SubscriptionMetrics {
  active: number
  new_this_month: number
  canceled_this_month: number
  by_plan: SubscriptionPlanBreakdown[]
}

export interface UsageMetricVolume {
  metric_name: string
  metric_code: string
  event_count: number
}

export interface UsageMetrics {
  top_metrics: UsageMetricVolume[]
}
