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
export type ChargeSimulationResult = components['schemas']['ChargeSimulationResult']
export type PlanSimulateResponse = components['schemas']['PlanSimulateResponse']

// --- Subscriptions ---
export type Subscription = components['schemas']['SubscriptionResponse']
export type SubscriptionCreate = components['schemas']['SubscriptionCreate']
export type SubscriptionUpdate = components['schemas']['SubscriptionUpdate']
export type SubscriptionStatus = components['schemas']['SubscriptionStatus']
export type BillingTime = components['schemas']['BillingTime']
export type TerminationAction = components['schemas']['TerminationAction']
export type ChangePlanPreviewRequest = components['schemas']['ChangePlanPreviewRequest']
export type ChangePlanPreviewResponse = components['schemas']['ChangePlanPreviewResponse']
export type PlanSummary = components['schemas']['PlanSummary']
export type ProrationDetail = components['schemas']['ProrationDetail']

// --- Invoices ---
export type Invoice = components['schemas']['InvoiceResponse']
export type InvoiceUpdate = components['schemas']['InvoiceUpdate']
export type InvoiceStatus = components['schemas']['InvoiceStatus']
export type OneOffInvoiceCreate = components['schemas']['OneOffInvoiceCreate']
export type BulkFinalizeResponse = components['schemas']['BulkFinalizeResponse']
export type SendReminderResponse = components['schemas']['SendReminderResponse']

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
export type BalanceTimelineResponse = components['schemas']['BalanceTimelineResponse']
export type BalanceTimelinePoint = components['schemas']['BalanceTimelinePoint']
export type DepletionForecastResponse = components['schemas']['DepletionForecastResponse']
export type WalletTransferRequest = components['schemas']['WalletTransferRequest']
export type WalletTransferResponse = components['schemas']['WalletTransferResponse']

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
export type AppliedAddOnDetail = components['schemas']['AppliedAddOnDetailResponse']
export type PortalAddOn = components['schemas']['PortalAddOnResponse']
export type PortalPurchasedAddOn = components['schemas']['PortalPurchasedAddOnResponse']
export type PortalPurchaseAddOnResult = components['schemas']['PortalPurchaseAddOnResponse']

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
export type TaxAppliedEntitiesResponse = components['schemas']['TaxAppliedEntitiesResponse']
export type TaxApplicationCountsResponse = components['schemas']['TaxApplicationCountsResponse']

// --- Webhooks ---
export type WebhookEndpoint = components['schemas']['WebhookEndpointResponse']
export type WebhookEndpointCreate = components['schemas']['WebhookEndpointCreate']
export type WebhookEndpointUpdate = components['schemas']['WebhookEndpointUpdate']
export type Webhook = components['schemas']['WebhookResponse']
export type WebhookDeliveryAttempt = components['schemas']['WebhookDeliveryAttemptResponse']
export type EndpointDeliveryStats = components['schemas']['EndpointDeliveryStats']

// --- Organizations ---
export type Organization = components['schemas']['OrganizationResponse']
export type OrganizationCreate = components['schemas']['OrganizationCreate']
export type OrganizationUpdate = components['schemas']['OrganizationUpdate']
export type PortalBranding = components['schemas']['PortalBrandingResponse']
export type ApiKeyCreate = components['schemas']['ApiKeyCreate']
export type ApiKeyCreateResponse = components['schemas']['ApiKeyCreateResponse']
export type ApiKey = components['schemas']['ApiKeyListResponse']

// --- Dunning Campaigns ---
export type DunningCampaign = components['schemas']['DunningCampaignResponse']
export type DunningCampaignCreate = components['schemas']['DunningCampaignCreate']
export type DunningCampaignUpdate = components['schemas']['DunningCampaignUpdate']
export type DunningCampaignThreshold = components['schemas']['DunningCampaignThresholdResponse']
export type DunningCampaignThresholdCreate = components['schemas']['DunningCampaignThresholdCreate']
export type DunningCampaignPerformanceStats = components['schemas']['DunningCampaignPerformanceStats']
export type ExecutionHistoryEntry = components['schemas']['ExecutionHistoryEntry']
export type ExecutionHistoryInvoice = components['schemas']['ExecutionHistoryInvoice']
export type CampaignTimelineEvent = components['schemas']['CampaignTimelineEvent']
export type CampaignTimelineResponse = components['schemas']['CampaignTimelineResponse']
export type CampaignPreviewResponse = components['schemas']['CampaignPreviewResponse']
export type CampaignPreviewInvoiceGroup = components['schemas']['CampaignPreviewInvoiceGroup']

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
export type { IntegrationCustomerResponse, IntegrationMappingResponse, IntegrationSyncHistoryResponse } from '@/lib/api'

// --- Data Exports ---
export type DataExport = components['schemas']['DataExportResponse']
export type DataExportCreate = components['schemas']['DataExportCreate']
export type ExportType = components['schemas']['ExportType']
export type DataExportEstimate = { export_type: string; record_count: number }

// --- Events ---
export type Event = components['schemas']['EventResponse']
export type EventCreate = components['schemas']['EventCreate']
export type EventBatchCreate = components['schemas']['EventBatchCreate']
export type EventBatchResponse = components['schemas']['EventBatchResponse']
export type EventVolumePoint = components['schemas']['EventVolumePoint']
export type EventVolumeResponse = components['schemas']['EventVolumeResponse']

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

// --- Features ---
export type Feature = components['schemas']['FeatureResponse']
export type FeatureCreate = components['schemas']['FeatureCreate']
export type FeatureUpdate = components['schemas']['FeatureUpdate']
export type FeatureType = components['schemas']['FeatureType']

// --- Entitlements ---
export type Entitlement = components['schemas']['EntitlementResponse']
export type EntitlementCreate = components['schemas']['EntitlementCreate']
export type EntitlementUpdate = components['schemas']['EntitlementUpdate']

// --- Usage Alerts ---
export type UsageAlert = components['schemas']['UsageAlertResponse']
export type UsageAlertCreate = components['schemas']['UsageAlertCreate']
export type UsageAlertUpdate = components['schemas']['UsageAlertUpdate']

export interface UsageAlertStatus {
  alert_id: string
  current_usage: string
  threshold_value: string
  usage_percentage: string
  billing_period_start: string
  billing_period_end: string
}

export interface UsageAlertTrigger {
  id: string
  usage_alert_id: string
  current_usage: string
  threshold_value: string
  metric_code: string
  triggered_at: string
}

// --- Subscription Lifecycle ---
export type LifecycleEvent = components['schemas']['LifecycleEvent']
export type SubscriptionLifecycleResponse = components['schemas']['SubscriptionLifecycleResponse']

// --- Payment Requests ---
export type PaymentRequest = components['schemas']['PaymentRequestResponse']
export type PaymentRequestCreate = components['schemas']['PaymentRequestCreate']
export type BatchPaymentRequestResponse = components['schemas']['BatchPaymentRequestResponse']
export type PaymentAttemptHistoryResponse = components['schemas']['PaymentAttemptHistoryResponse']
export type PaymentAttemptEntry = components['schemas']['PaymentAttemptEntry']

// --- Invoice Preview ---
export type FeePreview = components['schemas']['FeePreview']
export type InvoicePreviewResponse = components['schemas']['InvoicePreviewResponse']
export type InvoicePreviewRequest = components['schemas']['InvoicePreviewRequest']

// --- Fee Estimation ---
export type EstimateFeesRequest = components['schemas']['EstimateFeesRequest']
export type EstimateFeesResponse = components['schemas']['EstimateFeesResponse']

// --- Customer Health ---
export interface CustomerHealthResponse {
  status: 'good' | 'warning' | 'critical'
  total_invoices: number
  paid_invoices: number
  overdue_invoices: number
  total_payments: number
  failed_payments: number
  overdue_amount: number
}

// --- Dashboard types ---
export interface TrendIndicator {
  previous_value: number
  change_percent: number | null
}

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
  mrr_trend: TrendIndicator | null
}

export interface CustomerMetrics {
  total: number
  new_this_month: number
  churned_this_month: number
  new_trend: TrendIndicator | null
  churned_trend: TrendIndicator | null
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
  new_trend: TrendIndicator | null
  canceled_trend: TrendIndicator | null
}

export interface UsageMetricVolume {
  metric_name: string
  metric_code: string
  event_count: number
}

export interface UsageMetrics {
  top_metrics: UsageMetricVolume[]
}
