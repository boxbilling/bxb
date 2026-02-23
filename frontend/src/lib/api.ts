// API client for bxb billing platform
// This file is the single source of truth for all API types.
import type { components } from '@/lib/schema'

// --- Customers ---
export type Customer = components['schemas']['CustomerResponse']
export type CustomerCreate = components['schemas']['CustomerCreate']
export type CustomerUpdate = components['schemas']['CustomerUpdate']
export type CustomerIntegrationMappingResponse = components['schemas']['CustomerIntegrationMappingResponse']

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
export type PlanSimulateRequest = components['schemas']['PlanSimulateRequest']
export type PlanSimulateResponse = components['schemas']['PlanSimulateResponse']

// --- Charges ---
export type Charge = components['schemas']['ChargeOutput']
export type ChargeInput = components['schemas']['ChargeInput']
export type ChargeModel = components['schemas']['ChargeModel']
export type ChargeFilterInput = components['schemas']['ChargeFilterInput']
export type ChargeSimulationResult = components['schemas']['ChargeSimulationResult']

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
export type BulkSubscriptionRequest = components['schemas']['BulkSubscriptionRequest']
export type BulkTerminateRequest = components['schemas']['BulkTerminateRequest']
export type BulkSubscriptionResponse = components['schemas']['BulkSubscriptionResponse']
export type LifecycleEvent = components['schemas']['LifecycleEvent']
export type SubscriptionLifecycleResponse = components['schemas']['SubscriptionLifecycleResponse']
export type NextBillingDateResponse = components['schemas']['NextBillingDateResponse']
export type UsageTrendResponse = components['schemas']['UsageTrendResponse']

// --- Invoices ---
export type Invoice = components['schemas']['InvoiceResponse']
export type InvoiceUpdate = components['schemas']['InvoiceUpdate']
export type InvoiceStatus = components['schemas']['InvoiceStatus']
export type OneOffInvoiceCreate = components['schemas']['OneOffInvoiceCreate']
export type BulkFinalizeRequest = components['schemas']['BulkFinalizeRequest']
export type BulkFinalizeResponse = components['schemas']['BulkFinalizeResponse']
export type BulkVoidRequest = components['schemas']['BulkVoidRequest']
export type BulkVoidResponse = components['schemas']['BulkVoidResponse']
export type SendReminderResponse = components['schemas']['SendReminderResponse']
export type FeePreview = components['schemas']['FeePreview']
export type InvoicePreviewResponse = components['schemas']['InvoicePreviewResponse']
export type InvoicePreviewRequest = components['schemas']['InvoicePreviewRequest']

// --- Fees ---
export type Fee = components['schemas']['FeeResponse']
export type FeeUpdate = components['schemas']['FeeUpdate']
export type FeeType = components['schemas']['FeeType']
export type FeePaymentStatus = components['schemas']['FeePaymentStatus']
export type EstimateFeesRequest = components['schemas']['EstimateFeesRequest']
export type EstimateFeesResponse = components['schemas']['EstimateFeesResponse']

// --- Payments ---
export type Payment = components['schemas']['PaymentResponse']
export type PaymentStatus = components['schemas']['PaymentStatus']
export type PaymentProvider = components['schemas']['PaymentProvider']
export type CheckoutSessionCreate = components['schemas']['CheckoutSessionCreate']
export type CheckoutSessionResponse = components['schemas']['CheckoutSessionResponse']
export type ManualPaymentCreate = components['schemas']['ManualPaymentCreate']

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
export type PortalAppliedCoupon = components['schemas']['PortalAppliedCouponResponse']

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
export type IntegrationCustomerResponse = {
  id: string
  integration_id: string
  customer_id: string
  external_customer_id: string
  settings: Record<string, unknown> | null
  created_at: string
  updated_at: string
}
export type IntegrationMappingResponse = {
  id: string
  integration_id: string
  mappable_type: string
  mappable_id: string
  external_id: string
  external_data: Record<string, unknown> | null
  last_synced_at: string | null
  created_at: string
  updated_at: string
}
export type IntegrationSyncHistoryResponse = {
  id: string
  integration_id: string
  resource_type: string
  resource_id: string | null
  external_id: string | null
  action: string
  status: string
  error_message: string | null
  details: Record<string, unknown> | null
  started_at: string
  completed_at: string | null
  created_at: string
}

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
export type EventReprocessResponse = components['schemas']['EventReprocessResponse']

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

// --- Payment Requests ---
export type PaymentRequest = components['schemas']['PaymentRequestResponse']
export type PaymentRequestCreate = components['schemas']['PaymentRequestCreate']
export type BatchPaymentRequestResponse = components['schemas']['BatchPaymentRequestResponse']
export type PaymentAttemptHistoryResponse = components['schemas']['PaymentAttemptHistoryResponse']
export type PaymentAttemptEntry = components['schemas']['PaymentAttemptEntry']

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
  type: 'customer_created' | 'subscription_created' | 'invoice_finalized' | 'payment_received' | 'subscription_canceled' | 'payment_failed' | 'credit_note_created' | 'wallet_topped_up'
  description: string
  timestamp: string
  resource_type?: string | null
  resource_id?: string | null
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

// --- Portal types ---
export type PortalTopUpResponse = components['schemas']['PortalTopUpResponse']
export type PortalUsageTrendResponse = components['schemas']['PortalUsageTrendResponse']
export type PortalUsageLimitsResponse = components['schemas']['PortalUsageLimitsResponse']
export type PortalProjectedUsageResponse = components['schemas']['PortalProjectedUsageResponse']
export type PortalPayNowResponse = components['schemas']['PortalPayNowResponse']

export type PortalPlanSummary = {
  id: string
  name: string
  code: string
  interval: string
  amount_cents: number
  currency: string
}

export type PortalSubscriptionResponse = {
  id: string
  external_id: string
  status: string
  started_at: string | null
  canceled_at: string | null
  paused_at: string | null
  downgraded_at: string | null
  created_at: string
  plan: PortalPlanSummary
  pending_downgrade_plan: PortalPlanSummary | null
}

export type PortalPlanResponse = {
  id: string
  name: string
  code: string
  description: string | null
  interval: string
  amount_cents: number
  currency: string
}

export type PortalNextBillingInfo = {
  subscription_id: string
  subscription_external_id: string
  plan_name: string
  plan_interval: string
  next_billing_date: string
  days_until_next_billing: number
  amount_cents: number
  currency: string
}

export type PortalUpcomingCharge = {
  subscription_id: string
  subscription_external_id: string
  plan_name: string
  base_amount_cents: number
  usage_amount_cents: number
  total_estimated_cents: number
  currency: string
}

export type PortalUsageProgress = {
  feature_name: string
  feature_code: string
  feature_type: string
  entitlement_value: string
  current_usage: number | null
  usage_percentage: number | null
}

export type PortalQuickActions = {
  outstanding_invoice_count: number
  outstanding_amount_cents: number
  has_wallet: boolean
  wallet_balance_cents: number
  has_active_subscription: boolean
  currency: string
}

export type PortalDashboardSummaryResponse = {
  next_billing: PortalNextBillingInfo[]
  upcoming_charges: PortalUpcomingCharge[]
  usage_progress: PortalUsageProgress[]
  quick_actions: PortalQuickActions
}

// --- Notification types ---
export type NotificationResponse = components['schemas']['NotificationResponse']
export type NotificationCountResponse = components['schemas']['NotificationCountResponse']

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const ORG_STORAGE_KEY = 'bxb_organization_id'

export function getActiveOrganizationId(): string | null {
  return localStorage.getItem(ORG_STORAGE_KEY)
}

export function setActiveOrganizationId(id: string | null) {
  if (id) {
    localStorage.setItem(ORG_STORAGE_KEY, id)
  } else {
    localStorage.removeItem(ORG_STORAGE_KEY)
  }
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  const orgId = getActiveOrganizationId()
  if (orgId) {
    headers['X-Organization-Id'] = orgId
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(response.status, error.message || error.detail || 'Request failed', error)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

export interface PaginatedResponse<T> {
  data: T[]
  totalCount: number
}

async function requestWithCount<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<PaginatedResponse<T>> {
  const url = `${API_BASE_URL}${endpoint}`

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  const orgId = getActiveOrganizationId()
  if (orgId) {
    headers['X-Organization-Id'] = orgId
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(response.status, error.message || error.detail || 'Request failed', error)
  }

  const totalCount = parseInt(response.headers.get('X-Total-Count') || '0', 10)
  const data = await response.json()
  return { data, totalCount }
}

async function requestBlob(
  endpoint: string,
  options: RequestInit = {}
): Promise<Blob> {
  const url = `${API_BASE_URL}${endpoint}`

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  const orgId = getActiveOrganizationId()
  if (orgId) {
    headers['X-Organization-Id'] = orgId
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(response.status, error.message || error.detail || 'Request failed', error)
  }

  return response.blob()
}

function buildQuery(params?: Record<string, string | number | undefined>): string {
  if (!params) return ''
  const searchParams = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) searchParams.set(key, String(value))
  }
  const query = searchParams.toString()
  return query ? `?${query}` : ''
}

// Portal request helper — uses token query param instead of org ID header
async function portalRequest<T>(
  endpoint: string,
  token: string,
  options: RequestInit = {}
): Promise<T> {
  const separator = endpoint.includes('?') ? '&' : '?'
  const url = `${API_BASE_URL}${endpoint}${separator}token=${encodeURIComponent(token)}`

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(response.status, error.message || error.detail || 'Request failed', error)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

async function portalRequestBlob(
  endpoint: string,
  token: string,
  options: RequestInit = {}
): Promise<Blob> {
  const separator = endpoint.includes('?') ? '&' : '?'
  const url = `${API_BASE_URL}${endpoint}${separator}token=${encodeURIComponent(token)}`

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(response.status, error.message || error.detail || 'Request failed', error)
  }

  return response.blob()
}

// Portal API — customer-facing, authenticated via JWT token
export const portalApi = {
  getDashboardSummary: (token: string) =>
    portalRequest<PortalDashboardSummaryResponse>('/portal/dashboard_summary', token),
  getCustomer: (token: string) =>
    portalRequest<Customer>('/portal/customer', token),
  getBranding: (token: string) =>
    portalRequest<PortalBranding>('/portal/branding', token),
  listInvoices: (token: string) =>
    portalRequest<Invoice[]>('/portal/invoices', token),
  getInvoice: (token: string, id: string) =>
    portalRequest<Invoice>(`/portal/invoices/${id}`, token),
  downloadInvoicePdf: (token: string, id: string) =>
    portalRequestBlob(`/portal/invoices/${id}/download_pdf`, token),
  previewInvoicePdf: (token: string, id: string) =>
    portalRequestBlob(`/portal/invoices/${id}/pdf_preview`, token),
  payInvoice: (token: string, id: string, successUrl: string, cancelUrl: string) =>
    portalRequest<PortalPayNowResponse>(`/portal/invoices/${id}/pay`, token, {
      method: 'POST',
      body: JSON.stringify({ success_url: successUrl, cancel_url: cancelUrl }),
    }),
  getInvoicePayments: (token: string, id: string) =>
    portalRequest<Payment[]>(`/portal/invoices/${id}/payments`, token),
  getCurrentUsage: (token: string, subscriptionId: string) =>
    portalRequest<CustomerCurrentUsageResponse>(`/portal/current_usage?subscription_id=${subscriptionId}`, token),
  getUsageTrend: (token: string, subscriptionId: string, startDate?: string, endDate?: string) => {
    const params = new URLSearchParams({ subscription_id: subscriptionId })
    if (startDate) params.set('start_date', startDate)
    if (endDate) params.set('end_date', endDate)
    return portalRequest<PortalUsageTrendResponse>(`/portal/usage/trend?${params}`, token)
  },
  getUsageLimits: (token: string, subscriptionId: string) =>
    portalRequest<PortalUsageLimitsResponse>(`/portal/usage/limits?subscription_id=${subscriptionId}`, token),
  getProjectedUsage: (token: string, subscriptionId: string) =>
    portalRequest<PortalProjectedUsageResponse>(`/portal/usage/projected?subscription_id=${subscriptionId}`, token),
  listPayments: (token: string) =>
    portalRequest<Payment[]>('/portal/payments', token),
  getWallet: (token: string) =>
    portalRequest<Wallet>('/portal/wallet', token),
  getWallets: (token: string) =>
    portalRequest<Wallet[]>('/portal/wallet', token),
  getWalletTransactions: (token: string, walletId: string) =>
    portalRequest<WalletTransaction[]>(`/portal/wallet/${walletId}/transactions`, token),
  getWalletBalanceTimeline: (token: string, walletId: string) =>
    portalRequest<BalanceTimelineResponse>(`/portal/wallet/${walletId}/balance_timeline`, token),
  topUpWallet: (token: string, walletId: string, credits: number) =>
    portalRequest<PortalTopUpResponse>(`/portal/wallet/${walletId}/top_up`, token, {
      method: 'POST',
      body: JSON.stringify({ credits }),
    }),
  updateProfile: (token: string, data: { name?: string; email?: string | null; timezone?: string }) =>
    portalRequest<Customer>('/portal/profile', token, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  listPaymentMethods: (token: string) =>
    portalRequest<PaymentMethod[]>('/portal/payment_methods', token),
  addPaymentMethod: (token: string, data: PaymentMethodCreate) =>
    portalRequest<PaymentMethod>('/portal/payment_methods', token, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deletePaymentMethod: (token: string, id: string) =>
    portalRequest<void>(`/portal/payment_methods/${id}`, token, {
      method: 'DELETE',
    }),
  setDefaultPaymentMethod: (token: string, id: string) =>
    portalRequest<PaymentMethod>(`/portal/payment_methods/${id}/set_default`, token, {
      method: 'POST',
    }),
  listSubscriptions: (token: string) =>
    portalRequest<PortalSubscriptionResponse[]>('/portal/subscriptions', token),
  getSubscription: (token: string, id: string) =>
    portalRequest<PortalSubscriptionResponse>(`/portal/subscriptions/${id}`, token),
  listPlans: (token: string) =>
    portalRequest<PortalPlanResponse[]>('/portal/plans', token),
  changePlanPreview: (token: string, subscriptionId: string, newPlanId: string) =>
    portalRequest<ChangePlanPreviewResponse>(`/portal/subscriptions/${subscriptionId}/change_plan_preview`, token, {
      method: 'POST',
      body: JSON.stringify({ new_plan_id: newPlanId }),
    }),
  changePlan: (token: string, subscriptionId: string, newPlanId: string) =>
    portalRequest<Subscription>(`/portal/subscriptions/${subscriptionId}/change_plan`, token, {
      method: 'POST',
      body: JSON.stringify({ new_plan_id: newPlanId }),
    }),
  listAddOns: (token: string) =>
    portalRequest<PortalAddOn[]>('/portal/add_ons', token),
  listPurchasedAddOns: (token: string) =>
    portalRequest<PortalPurchasedAddOn[]>('/portal/add_ons/purchased', token),
  purchaseAddOn: (token: string, addOnId: string) =>
    portalRequest<PortalPurchaseAddOnResult>(`/portal/add_ons/${addOnId}/purchase`, token, {
      method: 'POST',
    }),
  listCoupons: (token: string) =>
    portalRequest<PortalAppliedCoupon[]>('/portal/coupons', token),
  redeemCoupon: (token: string, couponCode: string) =>
    portalRequest<PortalAppliedCoupon>('/portal/coupons/redeem', token, {
      method: 'POST',
      body: JSON.stringify({ coupon_code: couponCode }),
    }),
}

// Customers API
export const customersApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<Customer[]>(`/v1/customers/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<Customer>(`/v1/customers/${buildQuery(params)}`),
  get: (id: string) => request<Customer>(`/v1/customers/${id}`),
  create: (data: CustomerCreate) =>
    request<Customer>('/v1/customers/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: CustomerUpdate) =>
    request<Customer>(`/v1/customers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/customers/${id}`, { method: 'DELETE' }),
  getAppliedCoupons: (customerId: string) =>
    request<AppliedCoupon[]>(`/v1/customers/${customerId}/applied_coupons`),
  getCurrentUsage: (externalId: string, subscriptionId: string) =>
    request<CustomerCurrentUsageResponse>(`/v1/customers/${externalId}/current_usage${buildQuery({ subscription_id: subscriptionId })}`),
  getProjectedUsage: (externalId: string, subscriptionId: string) =>
    request<CustomerCurrentUsageResponse>(`/v1/customers/${externalId}/projected_usage${buildQuery({ subscription_id: subscriptionId })}`),
  getPastUsage: (externalId: string, externalSubscriptionId: string, periodsCount?: number) =>
    request<CustomerCurrentUsageResponse[]>(`/v1/customers/${externalId}/past_usage${buildQuery({ external_subscription_id: externalSubscriptionId, periods_count: periodsCount })}`),
  getPortalUrl: (externalId: string) =>
    request<{ portal_url: string }>(`/v1/customers/${externalId}/portal_url`),
  getHealth: (customerId: string) =>
    request<{ status: string; total_invoices: number; paid_invoices: number; overdue_invoices: number; total_payments: number; failed_payments: number; overdue_amount: number }>(`/v1/customers/${customerId}/health`),
  getAppliedAddOns: (customerId: string) =>
    request<AppliedAddOnDetail[]>(`/v1/customers/${customerId}/applied_add_ons`),
  getIntegrationMappings: (customerId: string) =>
    request<CustomerIntegrationMappingResponse[]>(`/v1/customers/${customerId}/integration_mappings`),
}

// Billable Metrics API
export const billableMetricsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<BillableMetric[]>(`/v1/billable_metrics/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<BillableMetric>(`/v1/billable_metrics/${buildQuery(params)}`),
  get: (id: string) => request<BillableMetric>(`/v1/billable_metrics/${id}`),
  create: (data: BillableMetricCreate) =>
    request<BillableMetric>('/v1/billable_metrics/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: BillableMetricUpdate) =>
    request<BillableMetric>(`/v1/billable_metrics/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/billable_metrics/${id}`, { method: 'DELETE' }),
  stats: () =>
    request<{ total: number; by_aggregation_type: Record<string, number> }>('/v1/billable_metrics/stats'),
  planCounts: () =>
    request<Record<string, number>>('/v1/billable_metrics/plan_counts'),
  createFilter: (code: string, data: BillableMetricFilterCreate) =>
    request<BillableMetricFilter>(`/v1/billable_metrics/${code}/filters`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listFilters: (code: string) =>
    request<BillableMetricFilter[]>(`/v1/billable_metrics/${code}/filters`),
  deleteFilter: (code: string, filterId: string) =>
    request<void>(`/v1/billable_metrics/${code}/filters/${filterId}`, { method: 'DELETE' }),
}

// Plans API
export const plansApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<Plan[]>(`/v1/plans/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<Plan>(`/v1/plans/${buildQuery(params)}`),
  get: (id: string) => request<Plan>(`/v1/plans/${id}`),
  create: (data: PlanCreate) =>
    request<Plan>('/v1/plans/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: PlanUpdate) =>
    request<Plan>(`/v1/plans/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/plans/${id}`, { method: 'DELETE' }),
  subscriptionCounts: () =>
    request<Record<string, number>>('/v1/plans/subscription_counts'),
  simulate: (id: string, data: PlanSimulateRequest) =>
    request<PlanSimulateResponse>(`/v1/plans/${id}/simulate`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Subscriptions API
export const subscriptionsApi = {
  list: (params?: { skip?: number; limit?: number; customer_id?: string }) =>
    request<Subscription[]>(`/v1/subscriptions/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; customer_id?: string; order_by?: string }) =>
    requestWithCount<Subscription>(`/v1/subscriptions/${buildQuery(params)}`),
  get: (id: string) => request<Subscription>(`/v1/subscriptions/${id}`),
  create: (data: SubscriptionCreate) =>
    request<Subscription>('/v1/subscriptions/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: SubscriptionUpdate) =>
    request<Subscription>(`/v1/subscriptions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  cancel: (id: string, onTerminationAction?: string) =>
    request<Subscription>(`/v1/subscriptions/${id}/cancel${buildQuery({ on_termination_action: onTerminationAction })}`, {
      method: 'POST',
    }),
  terminate: (id: string, onTerminationAction?: string) =>
    request<void>(`/v1/subscriptions/${id}${buildQuery({ on_termination_action: onTerminationAction })}`, { method: 'DELETE' }),
  pause: (id: string) =>
    request<Subscription>(`/v1/subscriptions/${id}/pause`, { method: 'POST' }),
  resume: (id: string) =>
    request<Subscription>(`/v1/subscriptions/${id}/resume`, { method: 'POST' }),
  getEntitlements: (externalId: string) =>
    request<Entitlement[]>(`/v1/subscriptions/${externalId}/entitlements`),
  getLifecycle: (id: string) =>
    request<SubscriptionLifecycleResponse>(`/v1/subscriptions/${id}/lifecycle`),
  changePlanPreview: (id: string, data: ChangePlanPreviewRequest) =>
    request<ChangePlanPreviewResponse>(`/v1/subscriptions/${id}/change_plan_preview`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getNextBillingDate: (id: string) =>
    request<NextBillingDateResponse>(`/v1/subscriptions/${id}/next_billing_date`),
  getUsageTrend: (id: string, params?: { start_date?: string; end_date?: string }) =>
    request<UsageTrendResponse>(`/v1/subscriptions/${id}/usage_trend${buildQuery(params)}`),
  bulkPause: (data: BulkSubscriptionRequest) =>
    request<BulkSubscriptionResponse>('/v1/subscriptions/bulk_pause', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  bulkResume: (data: BulkSubscriptionRequest) =>
    request<BulkSubscriptionResponse>('/v1/subscriptions/bulk_resume', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  bulkTerminate: (data: BulkTerminateRequest) =>
    request<BulkSubscriptionResponse>('/v1/subscriptions/bulk_terminate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Events API
export const eventsApi = {
  list: (params?: { skip?: number; limit?: number; external_customer_id?: string; code?: string; from_timestamp?: string; to_timestamp?: string }) =>
    request<Event[]>(`/v1/events/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; external_customer_id?: string; code?: string; from_timestamp?: string; to_timestamp?: string; order_by?: string }) =>
    requestWithCount<Event>(`/v1/events/${buildQuery(params)}`),
  get: (id: string) => request<Event>(`/v1/events/${id}`),
  create: (data: EventCreate) =>
    request<Event>('/v1/events/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  createBatch: (data: EventBatchCreate) =>
    request<EventBatchResponse>('/v1/events/batch', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  estimateFees: (data: EstimateFeesRequest) =>
    request<EstimateFeesResponse>('/v1/events/estimate_fees', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getVolume: (params?: { from_timestamp?: string; to_timestamp?: string }) =>
    request<EventVolumeResponse>(`/v1/events/volume${buildQuery(params)}`),
  reprocess: (id: string) =>
    request<EventReprocessResponse>(`/v1/events/${id}/reprocess`, { method: 'POST' }),
}

// Fees API
export const feesApi = {
  list: (params?: {
    skip?: number
    limit?: number
    invoice_id?: string
    customer_id?: string
    subscription_id?: string
    fee_type?: FeeType
    payment_status?: FeePaymentStatus
  }) => request<Fee[]>(`/v1/fees/${buildQuery(params)}`),
  listPaginated: (params?: {
    skip?: number
    limit?: number
    invoice_id?: string
    customer_id?: string
    subscription_id?: string
    fee_type?: FeeType
    payment_status?: FeePaymentStatus
    order_by?: string
  }) => requestWithCount<Fee>(`/v1/fees/${buildQuery(params)}`),
  get: (id: string) => request<Fee>(`/v1/fees/${id}`),
  update: (id: string, data: FeeUpdate) =>
    request<Fee>(`/v1/fees/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
}

// Invoices API
export const invoicesApi = {
  list: (params?: { skip?: number; limit?: number; customer_id?: string; status?: InvoiceStatus; subscription_id?: string }) =>
    request<Invoice[]>(`/v1/invoices/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; customer_id?: string; status?: InvoiceStatus; subscription_id?: string; order_by?: string }) =>
    requestWithCount<Invoice>(`/v1/invoices/${buildQuery(params)}`),
  get: (id: string) => request<Invoice>(`/v1/invoices/${id}`),
  update: (id: string, data: InvoiceUpdate) =>
    request<Invoice>(`/v1/invoices/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  finalize: (id: string) => request<Invoice>(`/v1/invoices/${id}/finalize`, { method: 'POST' }),
  pay: (id: string) => request<Invoice>(`/v1/invoices/${id}/pay`, { method: 'POST' }),
  void: (id: string) => request<Invoice>(`/v1/invoices/${id}/void`, { method: 'POST' }),
  delete: (id: string) => request<void>(`/v1/invoices/${id}`, { method: 'DELETE' }),
  listSettlements: (invoiceId: string) =>
    request<{ id: string; invoice_id: string; settlement_type: string; source_id: string; amount_cents: string; created_at: string }[]>(
      `/v1/invoices/${invoiceId}/settlements`
    ),
  downloadPdf: (id: string): Promise<Blob> =>
    requestBlob(`/v1/invoices/${id}/download_pdf`, { method: 'POST' }),
  sendEmail: (id: string) =>
    request<{ sent: boolean }>(`/v1/invoices/${id}/send_email`, { method: 'POST' }),
  preview: (data: InvoicePreviewRequest) =>
    request<InvoicePreviewResponse>('/v1/invoices/preview', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  createOneOff: (data: OneOffInvoiceCreate) =>
    request<Invoice>('/v1/invoices/one_off', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  bulkFinalize: (data: BulkFinalizeRequest) =>
    request<BulkFinalizeResponse>('/v1/invoices/bulk_finalize', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  bulkVoid: (data: BulkVoidRequest) =>
    request<BulkVoidResponse>('/v1/invoices/bulk_void', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  sendReminder: (id: string) =>
    request<SendReminderResponse>(`/v1/invoices/${id}/send_reminder`, { method: 'POST' }),
  previewPdf: (id: string): Promise<Blob> =>
    requestBlob(`/v1/invoices/${id}/pdf_preview`),
}

// Payments API
export const paymentsApi = {
  list: (params?: {
    skip?: number
    limit?: number
    invoice_id?: string
    customer_id?: string
    status?: PaymentStatus
    provider?: PaymentProvider
  }) => request<Payment[]>(`/v1/payments/${buildQuery(params)}`),
  listPaginated: (params?: {
    skip?: number
    limit?: number
    invoice_id?: string
    customer_id?: string
    status?: PaymentStatus
    provider?: PaymentProvider
    order_by?: string
  }) => requestWithCount<Payment>(`/v1/payments/${buildQuery(params)}`),
  get: (id: string) => request<Payment>(`/v1/payments/${id}`),
  createCheckout: (data: CheckoutSessionCreate) =>
    request<CheckoutSessionResponse>('/v1/payments/checkout', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  markPaid: (id: string) =>
    request<Payment>(`/v1/payments/${id}/mark-paid`, { method: 'POST' }),
  refund: (id: string, amount?: number) =>
    request<Payment>(`/v1/payments/${id}/refund`, {
      method: 'POST',
      body: amount !== undefined ? JSON.stringify({ amount }) : undefined,
    }),
  retry: (id: string) =>
    request<Payment>(`/v1/payments/${id}/retry`, { method: 'POST' }),
  delete: (id: string) => request<void>(`/v1/payments/${id}`, { method: 'DELETE' }),
  recordManual: (data: ManualPaymentCreate) =>
    request<Payment>('/v1/payments/record', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Payment Methods API
export const paymentMethodsApi = {
  list: (params?: { customer_id?: string; skip?: number; limit?: number }) =>
    request<PaymentMethod[]>(`/v1/payment_methods/${buildQuery(params)}`),
  listPaginated: (params?: { customer_id?: string; skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<PaymentMethod>(`/v1/payment_methods/${buildQuery(params)}`),
  get: (id: string) => request<PaymentMethod>(`/v1/payment_methods/${id}`),
  create: (data: PaymentMethodCreate) =>
    request<PaymentMethod>('/v1/payment_methods/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/payment_methods/${id}`, { method: 'DELETE' }),
  setDefault: (id: string) =>
    request<PaymentMethod>(`/v1/payment_methods/${id}/set_default`, {
      method: 'POST',
    }),
  createSetupSession: (data: SetupSessionCreate) =>
    request<SetupSessionResponse>('/v1/payment_methods/setup', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Wallets API
export const walletsApi = {
  list: (params?: { skip?: number; limit?: number; customer_id?: string }) =>
    request<Wallet[]>(`/v1/wallets/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; customer_id?: string; order_by?: string }) =>
    requestWithCount<Wallet>(`/v1/wallets/${buildQuery(params)}`),
  get: (id: string) => request<Wallet>(`/v1/wallets/${id}`),
  create: (data: WalletCreate) =>
    request<Wallet>('/v1/wallets/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: WalletUpdate) =>
    request<Wallet>(`/v1/wallets/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  terminate: (id: string) =>
    request<void>(`/v1/wallets/${id}`, { method: 'DELETE' }),
  topUp: (id: string, data: WalletTopUp) =>
    request<WalletTransaction>(`/v1/wallets/${id}/top_up`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listTransactions: (walletId: string, params?: { skip?: number; limit?: number }) =>
    request<WalletTransaction[]>(`/v1/wallets/${walletId}/transactions${buildQuery(params)}`),
  getBalanceTimeline: (walletId: string, params?: { start_date?: string; end_date?: string }) =>
    request<BalanceTimelineResponse>(`/v1/wallets/${walletId}/balance_timeline${buildQuery(params)}`),
  getDepletionForecast: (walletId: string, params?: { days?: number }) =>
    request<DepletionForecastResponse>(`/v1/wallets/${walletId}/depletion_forecast${buildQuery(params)}`),
  transfer: (data: WalletTransferRequest) =>
    request<WalletTransferResponse>('/v1/wallets/transfer', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Coupons API
export const couponsApi = {
  list: (params?: { skip?: number; limit?: number; status?: CouponStatus }) =>
    request<Coupon[]>(`/v1/coupons/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; status?: CouponStatus; order_by?: string }) =>
    requestWithCount<Coupon>(`/v1/coupons/${buildQuery(params)}`),
  get: (code: string) => request<Coupon>(`/v1/coupons/${code}`),
  create: (data: CouponCreate) =>
    request<Coupon>('/v1/coupons/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: CouponUpdate) =>
    request<Coupon>(`/v1/coupons/${code}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  terminate: (code: string) =>
    request<void>(`/v1/coupons/${code}`, { method: 'DELETE' }),
  apply: (data: ApplyCouponRequest) =>
    request<AppliedCoupon>('/v1/coupons/apply', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  removeApplied: (appliedCouponId: string) =>
    request<void>(`/v1/coupons/applied/${appliedCouponId}`, {
      method: 'DELETE',
    }),
  analytics: (code: string) =>
    request<{
      times_applied: number
      active_applications: number
      terminated_applications: number
      total_discount_cents: string
      remaining_uses: number | null
    }>(`/v1/coupons/${code}/analytics`),
  duplicate: (code: string) =>
    request<Coupon>(`/v1/coupons/${code}/duplicate`, {
      method: 'POST',
    }),
}

// Add-ons API
export const addOnsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<AddOn[]>(`/v1/add_ons/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<AddOn>(`/v1/add_ons/${buildQuery(params)}`),
  get: (code: string) => request<AddOn>(`/v1/add_ons/${code}`),
  create: (data: AddOnCreate) =>
    request<AddOn>('/v1/add_ons/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: AddOnUpdate) =>
    request<AddOn>(`/v1/add_ons/${code}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (code: string) =>
    request<void>(`/v1/add_ons/${code}`, { method: 'DELETE' }),
  apply: (data: ApplyAddOnRequest) =>
    request<AppliedAddOn>('/v1/add_ons/apply', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  applicationCounts: () =>
    request<Record<string, number>>('/v1/add_ons/application_counts'),
  applications: (code: string) =>
    request<AppliedAddOnDetail[]>(`/v1/add_ons/${code}/applications`),
}

// Credit Notes API
export const creditNotesApi = {
  list: (params?: { skip?: number; limit?: number; customer_id?: string; invoice_id?: string }) =>
    request<CreditNote[]>(`/v1/credit_notes/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; customer_id?: string; invoice_id?: string; order_by?: string }) =>
    requestWithCount<CreditNote>(`/v1/credit_notes/${buildQuery(params)}`),
  get: (id: string) => request<CreditNote>(`/v1/credit_notes/${id}`),
  create: (data: CreditNoteCreate) =>
    request<CreditNote>('/v1/credit_notes/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: CreditNoteUpdate) =>
    request<CreditNote>(`/v1/credit_notes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  finalize: (id: string) =>
    request<CreditNote>(`/v1/credit_notes/${id}/finalize`, { method: 'POST' }),
  void: (id: string) =>
    request<CreditNote>(`/v1/credit_notes/${id}/void`, { method: 'POST' }),
  downloadPdf: (id: string): Promise<Blob> =>
    requestBlob(`/v1/credit_notes/${id}/download_pdf`, { method: 'POST' }),
  sendEmail: (id: string) =>
    request<{ sent: boolean }>(`/v1/credit_notes/${id}/send_email`, { method: 'POST' }),
}

// Taxes API
export const taxesApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<Tax[]>(`/v1/taxes/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<Tax>(`/v1/taxes/${buildQuery(params)}`),
  get: (code: string) => request<Tax>(`/v1/taxes/${code}`),
  create: (data: TaxCreate) =>
    request<Tax>('/v1/taxes/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: TaxUpdate) =>
    request<Tax>(`/v1/taxes/${code}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (code: string) =>
    request<void>(`/v1/taxes/${code}`, { method: 'DELETE' }),
  apply: (data: ApplyTaxRequest) =>
    request<AppliedTax>('/v1/taxes/apply', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  removeApplied: (appliedTaxId: string) =>
    request<void>(`/v1/taxes/applied/${appliedTaxId}`, { method: 'DELETE' }),
  listApplied: (params: { taxable_type: string; taxable_id: string }) =>
    request<AppliedTax[]>(`/v1/taxes/applied${buildQuery(params)}`),
  applicationCounts: () =>
    request<TaxApplicationCountsResponse>('/v1/taxes/application_counts'),
  appliedEntities: (code: string) =>
    request<TaxAppliedEntitiesResponse>(`/v1/taxes/${code}/applied_entities`),
}

// Webhook Endpoints API
export const webhookEndpointsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<WebhookEndpoint[]>(`/v1/webhook_endpoints/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<WebhookEndpoint>(`/v1/webhook_endpoints/${buildQuery(params)}`),
  get: (id: string) => request<WebhookEndpoint>(`/v1/webhook_endpoints/${id}`),
  create: (data: WebhookEndpointCreate) =>
    request<WebhookEndpoint>('/v1/webhook_endpoints/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: WebhookEndpointUpdate) =>
    request<WebhookEndpoint>(`/v1/webhook_endpoints/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/webhook_endpoints/${id}`, { method: 'DELETE' }),
  listWebhooks: (params?: { skip?: number; limit?: number; endpoint_id?: string; status?: string; webhook_type?: string }) =>
    request<Webhook[]>(`/v1/webhook_endpoints/hooks/list${buildQuery(params)}`),
  listWebhooksPaginated: (params?: { skip?: number; limit?: number; endpoint_id?: string; status?: string; webhook_type?: string }) =>
    requestWithCount<Webhook>(`/v1/webhook_endpoints/hooks/list${buildQuery(params)}`),
  getWebhook: (webhookId: string) =>
    request<Webhook>(`/v1/webhook_endpoints/hooks/${webhookId}`),
  retryWebhook: (webhookId: string) =>
    request<Webhook>(`/v1/webhook_endpoints/hooks/${webhookId}/retry`, { method: 'POST' }),
  deliveryAttempts: (webhookId: string) =>
    request<WebhookDeliveryAttempt[]>(`/v1/webhook_endpoints/hooks/${webhookId}/delivery_attempts`),
  deliveryStats: () =>
    request<EndpointDeliveryStats[]>('/v1/webhook_endpoints/delivery_stats'),
}

// Organizations API
export const organizationsApi = {
  create: (data: OrganizationCreate) =>
    request<Organization & { api_key: ApiKeyCreateResponse }>('/v1/organizations/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  list: () => request<Organization[]>('/v1/organizations/'),
  getCurrent: () => request<Organization>('/v1/organizations/current'),
  updateCurrent: (data: OrganizationUpdate) =>
    request<Organization>('/v1/organizations/current', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  createApiKey: (data: ApiKeyCreate) =>
    request<ApiKeyCreateResponse>('/v1/organizations/current/api_keys', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listApiKeys: () =>
    request<ApiKey[]>('/v1/organizations/current/api_keys'),
  revokeApiKey: (apiKeyId: string) =>
    request<void>(`/v1/organizations/current/api_keys/${apiKeyId}`, { method: 'DELETE' }),
  rotateApiKey: (apiKeyId: string) =>
    request<ApiKeyCreateResponse>(`/v1/organizations/current/api_keys/${apiKeyId}/rotate`, { method: 'POST' }),
}

// Dunning Campaigns API
export const dunningCampaignsApi = {
  list: (params?: { skip?: number; limit?: number; status?: string }) =>
    request<DunningCampaign[]>(`/v1/dunning_campaigns/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; status?: string; order_by?: string }) =>
    requestWithCount<DunningCampaign>(`/v1/dunning_campaigns/${buildQuery(params)}`),
  get: (id: string) => request<DunningCampaign>(`/v1/dunning_campaigns/${id}`),
  create: (data: DunningCampaignCreate) =>
    request<DunningCampaign>('/v1/dunning_campaigns/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: DunningCampaignUpdate) =>
    request<DunningCampaign>(`/v1/dunning_campaigns/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/dunning_campaigns/${id}`, { method: 'DELETE' }),
  performanceStats: () =>
    request<DunningCampaignPerformanceStats>('/v1/dunning_campaigns/performance_stats'),
  executionHistory: (id: string, params?: { skip?: number; limit?: number }) =>
    request<ExecutionHistoryEntry[]>(`/v1/dunning_campaigns/${id}/execution_history${buildQuery(params)}`),
  timeline: (id: string) =>
    request<CampaignTimelineResponse>(`/v1/dunning_campaigns/${id}/timeline`),
  preview: (id: string) =>
    request<CampaignPreviewResponse>(`/v1/dunning_campaigns/${id}/preview`, { method: 'POST' }),
}

// Commitments API
export const commitmentsApi = {
  listForPlan: (planCode: string) =>
    request<Commitment[]>(`/v1/plans/${planCode}/commitments`),
  createForPlan: (planCode: string, data: CommitmentCreateAPI) =>
    request<Commitment>(`/v1/plans/${planCode}/commitments`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: CommitmentUpdate) =>
    request<Commitment>(`/v1/commitments/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/commitments/${id}`, { method: 'DELETE' }),
}

// Usage Thresholds API
export const usageThresholdsApi = {
  listForPlan: (planCode: string) =>
    request<UsageThreshold[]>(`/v1/plans/${planCode}/usage_thresholds`),
  createForPlan: (planCode: string, data: UsageThresholdCreateAPI) =>
    request<UsageThreshold>(`/v1/plans/${planCode}/usage_thresholds`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  createForSubscription: (subscriptionId: string, data: UsageThresholdCreateAPI) =>
    request<UsageThreshold>(`/v1/subscriptions/${subscriptionId}/usage_thresholds`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listForSubscription: (subscriptionId: string) =>
    request<UsageThreshold[]>(`/v1/subscriptions/${subscriptionId}/usage_thresholds`),
  getCurrentUsage: (subscriptionId: string) =>
    request<CurrentUsage>(`/v1/subscriptions/${subscriptionId}/current_usage`),
  delete: (thresholdId: string) =>
    request<void>(`/v1/usage_thresholds/${thresholdId}`, { method: 'DELETE' }),
}

// Integrations API
export const integrationsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<Integration[]>(`/v1/integrations/${buildQuery(params)}`),
  get: (id: string) => request<Integration>(`/v1/integrations/${id}`),
  create: (data: IntegrationCreate) =>
    request<Integration>('/v1/integrations/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: IntegrationUpdate) =>
    request<Integration>(`/v1/integrations/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/integrations/${id}`, { method: 'DELETE' }),
  testConnection: (id: string) =>
    request<{ success: boolean; error?: string; details?: string }>(`/v1/integrations/${id}/test`, {
      method: 'POST',
    }),
  listCustomers: (id: string, params?: { skip?: number; limit?: number }) =>
    request<IntegrationCustomerResponse[]>(`/v1/integrations/${id}/customers${buildQuery(params)}`),
  listMappings: (id: string, params?: { skip?: number; limit?: number }) =>
    request<IntegrationMappingResponse[]>(`/v1/integrations/${id}/mappings${buildQuery(params)}`),
  listSyncHistory: (id: string, params?: { status?: string; resource_type?: string; skip?: number; limit?: number }) =>
    request<IntegrationSyncHistoryResponse[]>(`/v1/integrations/${id}/sync_history${buildQuery(params)}`),
}

// Data Exports API
export const dataExportsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<DataExport[]>(`/v1/data_exports/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<DataExport>(`/v1/data_exports/${buildQuery(params)}`),
  get: (id: string) => request<DataExport>(`/v1/data_exports/${id}`),
  create: (data: DataExportCreate) =>
    request<DataExport>('/v1/data_exports/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  estimate: (data: DataExportCreate) =>
    request<DataExportEstimate>('/v1/data_exports/estimate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  download: (id: string) => requestBlob(`/v1/data_exports/${id}/download`),
}

// Payment Requests API
export const paymentRequestsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<PaymentRequest[]>(`/v1/payment_requests/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<PaymentRequest>(`/v1/payment_requests/${buildQuery(params)}`),
  get: (id: string) => request<PaymentRequest>(`/v1/payment_requests/${id}`),
  create: (data: PaymentRequestCreate) =>
    request<PaymentRequest>('/v1/payment_requests/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  batchCreate: () =>
    request<BatchPaymentRequestResponse>('/v1/payment_requests/batch', {
      method: 'POST',
    }),
  getAttempts: (id: string) =>
    request<PaymentAttemptHistoryResponse>(`/v1/payment_requests/${id}/attempts`),
}

// Audit Logs API
export const auditLogsApi = {
  list: (params?: { resource_type?: string; resource_id?: string; action?: string; skip?: number; limit?: number; start_date?: string; end_date?: string; actor_type?: string }) =>
    request<AuditLog[]>(`/v1/audit_logs/${buildQuery(params)}`),
  listPaginated: (params?: { resource_type?: string; resource_id?: string; action?: string; skip?: number; limit?: number; start_date?: string; end_date?: string; actor_type?: string; order_by?: string }) =>
    requestWithCount<AuditLog>(`/v1/audit_logs/${buildQuery(params)}`),
  getForResource: (resourceType: string, resourceId: string) =>
    request<AuditLog[]>(`/v1/audit_logs/${resourceType}/${resourceId}`),
}

// Billing Entities API
export const billingEntitiesApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<BillingEntity[]>(`/v1/billing_entities/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<BillingEntity>(`/v1/billing_entities/${buildQuery(params)}`),
  get: (code: string) => request<BillingEntity>(`/v1/billing_entities/${code}`),
  create: (data: BillingEntityCreate) =>
    request<BillingEntity>('/v1/billing_entities/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: BillingEntityUpdate) =>
    request<BillingEntity>(`/v1/billing_entities/${code}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (code: string) =>
    request<void>(`/v1/billing_entities/${code}`, { method: 'DELETE' }),
  customerCounts: () =>
    request<Record<string, number>>('/v1/billing_entities/customer_counts'),
}

// Features API
export const featuresApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<Feature[]>(`/v1/features/${buildQuery(params)}`),
  listPaginated: (params?: { skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<Feature>(`/v1/features/${buildQuery(params)}`),
  get: (code: string) => request<Feature>(`/v1/features/${code}`),
  create: (data: FeatureCreate) =>
    request<Feature>('/v1/features/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: FeatureUpdate) =>
    request<Feature>(`/v1/features/${code}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (code: string) =>
    request<void>(`/v1/features/${code}`, { method: 'DELETE' }),
  planCounts: () =>
    request<Record<string, number>>('/v1/features/plan_counts'),
}

// Entitlements API
export const entitlementsApi = {
  list: (params?: { plan_id?: string }) =>
    request<Entitlement[]>(`/v1/entitlements/${buildQuery(params)}`),
  create: (data: EntitlementCreate) =>
    request<Entitlement>('/v1/entitlements/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: EntitlementUpdate) =>
    request<Entitlement>(`/v1/entitlements/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/entitlements/${id}`, { method: 'DELETE' }),
  copy: (data: { source_plan_id: string; target_plan_id: string }) =>
    request<Entitlement[]>('/v1/entitlements/copy', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Usage Alerts API
export const usageAlertsApi = {
  list: (params?: { subscription_id?: string; skip?: number; limit?: number }) =>
    request<UsageAlert[]>(`/v1/usage_alerts/${buildQuery(params)}`),
  listPaginated: (params?: { subscription_id?: string; skip?: number; limit?: number; order_by?: string }) =>
    requestWithCount<UsageAlert>(`/v1/usage_alerts/${buildQuery(params)}`),
  get: (id: string) => request<UsageAlert>(`/v1/usage_alerts/${id}`),
  create: (data: UsageAlertCreate) =>
    request<UsageAlert>('/v1/usage_alerts/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: UsageAlertUpdate) =>
    request<UsageAlert>(`/v1/usage_alerts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/usage_alerts/${id}`, { method: 'DELETE' }),
  getStatus: (id: string) =>
    request<UsageAlertStatusResponse>(`/v1/usage_alerts/${id}/status`),
  listTriggers: (id: string, params?: { skip?: number; limit?: number }) =>
    request<UsageAlertTriggerResponse[]>(`/v1/usage_alerts/${id}/triggers${buildQuery(params)}`),
  test: (id: string) =>
    request<UsageAlertStatusResponse>(`/v1/usage_alerts/${id}/test`, {
      method: 'POST',
    }),
}

type UsageAlertStatusResponse = UsageAlertStatus
type UsageAlertTriggerResponse = UsageAlertTrigger

// Dashboard API
export type DashboardDateRange = { start_date?: string; end_date?: string }

export const dashboardApi = {
  getStats: (params?: DashboardDateRange) =>
    request<{
      total_customers: number
      active_subscriptions: number
      monthly_recurring_revenue: number
      total_invoiced: number
      total_wallet_credits: number
      currency: string
    }>(`/dashboard/stats${buildQuery(params)}`),
  getRecentActivity: (params?: { type?: string }) =>
    request<
      {
        id: string
        type: string
        description: string
        timestamp: string
        resource_type?: string | null
        resource_id?: string | null
      }[]
    >(`/dashboard/activity${buildQuery(params)}`),
  getRevenue: (params?: DashboardDateRange) =>
    request<{
      mrr: number
      total_revenue_this_month: number
      outstanding_invoices: number
      overdue_amount: number
      currency: string
      monthly_trend: { month: string; revenue: number }[]
      mrr_trend: { previous_value: number; change_percent: number | null } | null
    }>(`/dashboard/revenue${buildQuery(params)}`),
  getCustomerMetrics: (params?: DashboardDateRange) =>
    request<{
      total: number
      new_this_month: number
      churned_this_month: number
      new_trend: { previous_value: number; change_percent: number | null } | null
      churned_trend: { previous_value: number; change_percent: number | null } | null
    }>(`/dashboard/customers${buildQuery(params)}`),
  getSubscriptionMetrics: (params?: DashboardDateRange) =>
    request<{
      active: number
      new_this_month: number
      canceled_this_month: number
      by_plan: { plan_name: string; count: number }[]
      new_trend: { previous_value: number; change_percent: number | null } | null
      canceled_trend: { previous_value: number; change_percent: number | null } | null
    }>(`/dashboard/subscriptions${buildQuery(params)}`),
  getUsageMetrics: (params?: DashboardDateRange) =>
    request<{
      top_metrics: { metric_name: string; metric_code: string; event_count: number }[]
    }>(`/dashboard/usage${buildQuery(params)}`),
  getRevenueByPlan: (params?: DashboardDateRange) =>
    request<{
      by_plan: { plan_name: string; revenue: number }[]
      currency: string
    }>(`/dashboard/revenue_by_plan${buildQuery(params)}`),
  getRecentInvoices: () =>
    request<{
      id: string
      invoice_number: string
      customer_name: string
      status: string
      total: number
      currency: string
      created_at: string
    }[]>('/dashboard/recent_invoices'),
  getRecentSubscriptions: () =>
    request<{
      id: string
      external_id: string
      customer_name: string
      plan_name: string
      status: string
      created_at: string
    }[]>('/dashboard/recent_subscriptions'),
  getSparklines: (params?: DashboardDateRange) =>
    request<{
      mrr: { date: string; value: number }[]
      new_customers: { date: string; value: number }[]
      new_subscriptions: { date: string; value: number }[]
    }>(`/dashboard/sparklines${buildQuery(params)}`),
  getRevenueAnalytics: (params?: DashboardDateRange) =>
    request<{
      daily_revenue: { date: string; revenue: number }[]
      revenue_by_type: { invoice_type: string; revenue: number; count: number }[]
      top_customers: { customer_id: string; customer_name: string; revenue: number; invoice_count: number }[]
      collection: {
        total_invoiced: number
        total_collected: number
        collection_rate: number
        average_days_to_payment: number | null
        overdue_count: number
        overdue_amount: number
      }
      net_revenue: {
        gross_revenue: number
        refunds: number
        credit_notes: number
        net_revenue: number
        currency: string
      }
      currency: string
    }>(`/dashboard/revenue_analytics${buildQuery(params)}`),
}

// Global Search API
export type SearchResult = {
  type: 'customer' | 'invoice' | 'subscription' | 'plan'
  id: string
  title: string
  subtitle: string
  url: string
}

export const searchApi = {
  search: (query: string, limit?: number) =>
    request<SearchResult[]>(`/v1/search${buildQuery({ q: query, limit })}`),
}

// Notifications API
export const notificationsApi = {
  list: (params?: { skip?: number; limit?: number; category?: string; is_read?: boolean; order_by?: string }) =>
    request<NotificationResponse[]>(`/v1/notifications/${buildQuery(params as Record<string, string | number | undefined>)}`),
  unreadCount: () =>
    request<NotificationCountResponse>('/v1/notifications/unread_count'),
  markAsRead: (id: string) =>
    request<NotificationResponse>(`/v1/notifications/${id}/read`, { method: 'POST' }),
  markAllAsRead: () =>
    request<NotificationCountResponse>('/v1/notifications/read_all', { method: 'POST' }),
}

export { ApiError }
