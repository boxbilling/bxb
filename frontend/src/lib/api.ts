// API client for bxb billing platform
import type { components } from '@/lib/schema'

// Type aliases
type CustomerResponse = components['schemas']['CustomerResponse']
type CustomerCreate = components['schemas']['CustomerCreate']
type CustomerUpdate = components['schemas']['CustomerUpdate']

type BillableMetricResponse = components['schemas']['BillableMetricResponse']
type BillableMetricCreate = components['schemas']['BillableMetricCreate']
type BillableMetricUpdate = components['schemas']['BillableMetricUpdate']
type BillableMetricFilterCreate = components['schemas']['BillableMetricFilterCreate']
type BillableMetricFilterResponse = components['schemas']['BillableMetricFilterResponse']

type PlanResponse = components['schemas']['PlanResponse']
type PlanCreate = components['schemas']['PlanCreate']
type PlanUpdate = components['schemas']['PlanUpdate']
type PlanSimulateRequest = components['schemas']['PlanSimulateRequest']
type PlanSimulateResponse = components['schemas']['PlanSimulateResponse']

type SubscriptionResponse = components['schemas']['SubscriptionResponse']
type SubscriptionCreate = components['schemas']['SubscriptionCreate']
type SubscriptionUpdate = components['schemas']['SubscriptionUpdate']
type SubscriptionLifecycleResponse = components['schemas']['SubscriptionLifecycleResponse']
type ChangePlanPreviewRequest = components['schemas']['ChangePlanPreviewRequest']
type ChangePlanPreviewResponse = components['schemas']['ChangePlanPreviewResponse']
type NextBillingDateResponse = components['schemas']['NextBillingDateResponse']
type UsageTrendResponse = components['schemas']['UsageTrendResponse']

type InvoiceResponse = components['schemas']['InvoiceResponse']
type InvoiceUpdate = components['schemas']['InvoiceUpdate']
type InvoiceStatus = components['schemas']['InvoiceStatus']

type PaymentResponse = components['schemas']['PaymentResponse']
type PaymentStatus = components['schemas']['PaymentStatus']
type PaymentProvider = components['schemas']['PaymentProvider']
type CheckoutSessionCreate = components['schemas']['CheckoutSessionCreate']
type CheckoutSessionResponse = components['schemas']['CheckoutSessionResponse']

type FeeResponse = components['schemas']['FeeResponse']
type FeeUpdate = components['schemas']['FeeUpdate']
type FeeType = components['schemas']['FeeType']
type FeePaymentStatus = components['schemas']['FeePaymentStatus']

type WalletResponse = components['schemas']['WalletResponse']
type WalletCreate = components['schemas']['WalletCreate']
type WalletUpdate = components['schemas']['WalletUpdate']
type WalletTopUp = components['schemas']['WalletTopUp']
type WalletTransactionResponse = components['schemas']['WalletTransactionResponse']

type CouponResponse = components['schemas']['CouponResponse']
type CouponCreate = components['schemas']['CouponCreate']
type CouponUpdate = components['schemas']['CouponUpdate']
type CouponStatus = components['schemas']['CouponStatus']
type ApplyCouponRequest = components['schemas']['ApplyCouponRequest']
type AppliedCouponResponse = components['schemas']['AppliedCouponResponse']

type AddOnResponse = components['schemas']['AddOnResponse']
type AddOnCreate = components['schemas']['AddOnCreate']
type AddOnUpdate = components['schemas']['AddOnUpdate']
type ApplyAddOnRequest = components['schemas']['ApplyAddOnRequest']
type AppliedAddOnResponse = components['schemas']['AppliedAddOnResponse']

type CreditNoteResponse = components['schemas']['CreditNoteResponse']
type CreditNoteCreate = components['schemas']['CreditNoteCreate']
type CreditNoteUpdate = components['schemas']['CreditNoteUpdate']

type TaxResponse = components['schemas']['TaxResponse']
type TaxCreate = components['schemas']['TaxCreate']
type TaxUpdate = components['schemas']['TaxUpdate']
type ApplyTaxRequest = components['schemas']['ApplyTaxRequest']
type AppliedTaxResponse = components['schemas']['AppliedTaxResponse']

type WebhookEndpointResponse = components['schemas']['WebhookEndpointResponse']
type WebhookEndpointCreate = components['schemas']['WebhookEndpointCreate']
type WebhookEndpointUpdate = components['schemas']['WebhookEndpointUpdate']
type WebhookResponse = components['schemas']['WebhookResponse']

type OrganizationResponse = components['schemas']['OrganizationResponse']
type OrganizationCreate = components['schemas']['OrganizationCreate']
type OrganizationUpdate = components['schemas']['OrganizationUpdate']
type ApiKeyCreate = components['schemas']['ApiKeyCreate']
type ApiKeyCreateResponse = components['schemas']['ApiKeyCreateResponse']
type ApiKeyListResponse = components['schemas']['ApiKeyListResponse']

type DunningCampaignResponse = components['schemas']['DunningCampaignResponse']
type DunningCampaignCreate = components['schemas']['DunningCampaignCreate']
type DunningCampaignUpdate = components['schemas']['DunningCampaignUpdate']

type CommitmentResponse = components['schemas']['CommitmentResponse']
type CommitmentCreateAPI = components['schemas']['CommitmentCreateAPI']
type CommitmentUpdate = components['schemas']['CommitmentUpdate']

type UsageThresholdResponse = components['schemas']['UsageThresholdResponse']
type UsageThresholdCreateAPI = components['schemas']['UsageThresholdCreateAPI']
type CurrentUsageResponse = components['schemas']['app__schemas__usage_threshold__CurrentUsageResponse']
type CustomerCurrentUsageResponse = components['schemas']['app__schemas__usage__CurrentUsageResponse']

type IntegrationResponse = components['schemas']['IntegrationResponse']
type IntegrationCreate = components['schemas']['IntegrationCreate']
type IntegrationUpdate = components['schemas']['IntegrationUpdate']

type DataExportResponse = components['schemas']['DataExportResponse']
type DataExportCreate = components['schemas']['DataExportCreate']

type EventResponse = components['schemas']['EventResponse']
type EventCreate = components['schemas']['EventCreate']
type EventBatchCreate = components['schemas']['EventBatchCreate']
type EventBatchResponse = components['schemas']['EventBatchResponse']

type InvoicePreviewRequest = components['schemas']['InvoicePreviewRequest']
type InvoicePreviewResponse = components['schemas']['InvoicePreviewResponse']
type EstimateFeesRequest = components['schemas']['EstimateFeesRequest']
type EstimateFeesResponse = components['schemas']['EstimateFeesResponse']

type PaymentMethodResponse = components['schemas']['PaymentMethodResponse']
type PaymentMethodCreate = components['schemas']['PaymentMethodCreate']
type SetupSessionCreate = components['schemas']['SetupSessionCreate']
type SetupSessionResponse = components['schemas']['SetupSessionResponse']

type PaymentRequestResponse = components['schemas']['PaymentRequestResponse']
type PaymentRequestCreate = components['schemas']['PaymentRequestCreate']

type AuditLogResponse = components['schemas']['AuditLogResponse']

type BillingEntityResponse = components['schemas']['BillingEntityResponse']
type BillingEntityCreate = components['schemas']['BillingEntityCreate']
type BillingEntityUpdate = components['schemas']['BillingEntityUpdate']

type FeatureResponse = components['schemas']['FeatureResponse']
type FeatureCreate = components['schemas']['FeatureCreate']
type FeatureUpdate = components['schemas']['FeatureUpdate']

type EntitlementResponse = components['schemas']['EntitlementResponse']
type EntitlementCreate = components['schemas']['EntitlementCreate']
type EntitlementUpdate = components['schemas']['EntitlementUpdate']

type UsageAlertResponse = components['schemas']['UsageAlertResponse']
type UsageAlertCreate = components['schemas']['UsageAlertCreate']
type UsageAlertUpdate = components['schemas']['UsageAlertUpdate']

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
  getCustomer: (token: string) =>
    portalRequest<CustomerResponse>('/portal/customer', token),
  listInvoices: (token: string) =>
    portalRequest<InvoiceResponse[]>('/portal/invoices', token),
  getInvoice: (token: string, id: string) =>
    portalRequest<InvoiceResponse>(`/portal/invoices/${id}`, token),
  downloadInvoicePdf: (token: string, id: string) =>
    portalRequestBlob(`/portal/invoices/${id}/download_pdf`, token),
  getCurrentUsage: (token: string, subscriptionId: string) =>
    portalRequest<CustomerCurrentUsageResponse>(`/portal/current_usage?subscription_id=${subscriptionId}`, token),
  listPayments: (token: string) =>
    portalRequest<PaymentResponse[]>('/portal/payments', token),
  getWallet: (token: string) =>
    portalRequest<WalletResponse>('/portal/wallet', token),
}

// Customers API
export const customersApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<CustomerResponse[]>(`/v1/customers/${buildQuery(params)}`),
  get: (id: string) => request<CustomerResponse>(`/v1/customers/${id}`),
  create: (data: CustomerCreate) =>
    request<CustomerResponse>('/v1/customers/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: CustomerUpdate) =>
    request<CustomerResponse>(`/v1/customers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/customers/${id}`, { method: 'DELETE' }),
  getAppliedCoupons: (customerId: string) =>
    request<AppliedCouponResponse[]>(`/v1/customers/${customerId}/applied_coupons`),
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
}

// Billable Metrics API
export const billableMetricsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<BillableMetricResponse[]>(`/v1/billable_metrics/${buildQuery(params)}`),
  get: (id: string) => request<BillableMetricResponse>(`/v1/billable_metrics/${id}`),
  create: (data: BillableMetricCreate) =>
    request<BillableMetricResponse>('/v1/billable_metrics/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: BillableMetricUpdate) =>
    request<BillableMetricResponse>(`/v1/billable_metrics/${id}`, {
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
    request<BillableMetricFilterResponse>(`/v1/billable_metrics/${code}/filters`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listFilters: (code: string) =>
    request<BillableMetricFilterResponse[]>(`/v1/billable_metrics/${code}/filters`),
  deleteFilter: (code: string, filterId: string) =>
    request<void>(`/v1/billable_metrics/${code}/filters/${filterId}`, { method: 'DELETE' }),
}

// Plans API
export const plansApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<PlanResponse[]>(`/v1/plans/${buildQuery(params)}`),
  get: (id: string) => request<PlanResponse>(`/v1/plans/${id}`),
  create: (data: PlanCreate) =>
    request<PlanResponse>('/v1/plans/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: PlanUpdate) =>
    request<PlanResponse>(`/v1/plans/${id}`, {
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
    request<SubscriptionResponse[]>(`/v1/subscriptions/${buildQuery(params)}`),
  get: (id: string) => request<SubscriptionResponse>(`/v1/subscriptions/${id}`),
  create: (data: SubscriptionCreate) =>
    request<SubscriptionResponse>('/v1/subscriptions/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: SubscriptionUpdate) =>
    request<SubscriptionResponse>(`/v1/subscriptions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  cancel: (id: string, onTerminationAction?: string) =>
    request<SubscriptionResponse>(`/v1/subscriptions/${id}/cancel${buildQuery({ on_termination_action: onTerminationAction })}`, {
      method: 'POST',
    }),
  terminate: (id: string, onTerminationAction?: string) =>
    request<void>(`/v1/subscriptions/${id}${buildQuery({ on_termination_action: onTerminationAction })}`, { method: 'DELETE' }),
  pause: (id: string) =>
    request<SubscriptionResponse>(`/v1/subscriptions/${id}/pause`, { method: 'POST' }),
  resume: (id: string) =>
    request<SubscriptionResponse>(`/v1/subscriptions/${id}/resume`, { method: 'POST' }),
  getEntitlements: (externalId: string) =>
    request<EntitlementResponse[]>(`/v1/subscriptions/${externalId}/entitlements`),
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
}

// Events API
export const eventsApi = {
  list: (params?: { skip?: number; limit?: number; external_customer_id?: string; code?: string; from_timestamp?: string; to_timestamp?: string }) =>
    request<EventResponse[]>(`/v1/events/${buildQuery(params)}`),
  get: (id: string) => request<EventResponse>(`/v1/events/${id}`),
  create: (data: EventCreate) =>
    request<EventResponse>('/v1/events/', {
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
  }) => request<FeeResponse[]>(`/v1/fees/${buildQuery(params)}`),
  get: (id: string) => request<FeeResponse>(`/v1/fees/${id}`),
  update: (id: string, data: FeeUpdate) =>
    request<FeeResponse>(`/v1/fees/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
}

// Invoices API
export const invoicesApi = {
  list: (params?: { skip?: number; limit?: number; customer_id?: string; status?: InvoiceStatus; subscription_id?: string }) =>
    request<InvoiceResponse[]>(`/v1/invoices/${buildQuery(params)}`),
  get: (id: string) => request<InvoiceResponse>(`/v1/invoices/${id}`),
  update: (id: string, data: InvoiceUpdate) =>
    request<InvoiceResponse>(`/v1/invoices/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  finalize: (id: string) => request<InvoiceResponse>(`/v1/invoices/${id}/finalize`, { method: 'POST' }),
  pay: (id: string) => request<InvoiceResponse>(`/v1/invoices/${id}/pay`, { method: 'POST' }),
  void: (id: string) => request<InvoiceResponse>(`/v1/invoices/${id}/void`, { method: 'POST' }),
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
  }) => request<PaymentResponse[]>(`/v1/payments/${buildQuery(params)}`),
  get: (id: string) => request<PaymentResponse>(`/v1/payments/${id}`),
  createCheckout: (data: CheckoutSessionCreate) =>
    request<CheckoutSessionResponse>('/v1/payments/checkout', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  markPaid: (id: string) =>
    request<PaymentResponse>(`/v1/payments/${id}/mark-paid`, { method: 'POST' }),
  refund: (id: string) =>
    request<PaymentResponse>(`/v1/payments/${id}/refund`, { method: 'POST' }),
  delete: (id: string) => request<void>(`/v1/payments/${id}`, { method: 'DELETE' }),
}

// Payment Methods API
export const paymentMethodsApi = {
  list: (params?: { customer_id?: string }) =>
    request<PaymentMethodResponse[]>(`/v1/payment_methods/${buildQuery(params)}`),
  get: (id: string) => request<PaymentMethodResponse>(`/v1/payment_methods/${id}`),
  create: (data: PaymentMethodCreate) =>
    request<PaymentMethodResponse>('/v1/payment_methods/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/payment_methods/${id}`, { method: 'DELETE' }),
  setDefault: (id: string) =>
    request<PaymentMethodResponse>(`/v1/payment_methods/${id}/set_default`, {
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
    request<WalletResponse[]>(`/v1/wallets/${buildQuery(params)}`),
  get: (id: string) => request<WalletResponse>(`/v1/wallets/${id}`),
  create: (data: WalletCreate) =>
    request<WalletResponse>('/v1/wallets/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: WalletUpdate) =>
    request<WalletResponse>(`/v1/wallets/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  terminate: (id: string) =>
    request<void>(`/v1/wallets/${id}`, { method: 'DELETE' }),
  topUp: (id: string, data: WalletTopUp) =>
    request<WalletTransactionResponse>(`/v1/wallets/${id}/top_up`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listTransactions: (walletId: string, params?: { skip?: number; limit?: number }) =>
    request<WalletTransactionResponse[]>(`/v1/wallets/${walletId}/transactions${buildQuery(params)}`),
}

// Coupons API
export const couponsApi = {
  list: (params?: { skip?: number; limit?: number; status?: CouponStatus }) =>
    request<CouponResponse[]>(`/v1/coupons/${buildQuery(params)}`),
  get: (code: string) => request<CouponResponse>(`/v1/coupons/${code}`),
  create: (data: CouponCreate) =>
    request<CouponResponse>('/v1/coupons/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: CouponUpdate) =>
    request<CouponResponse>(`/v1/coupons/${code}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  terminate: (code: string) =>
    request<void>(`/v1/coupons/${code}`, { method: 'DELETE' }),
  apply: (data: ApplyCouponRequest) =>
    request<AppliedCouponResponse>('/v1/coupons/apply', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Add-ons API
export const addOnsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<AddOnResponse[]>(`/v1/add_ons/${buildQuery(params)}`),
  get: (code: string) => request<AddOnResponse>(`/v1/add_ons/${code}`),
  create: (data: AddOnCreate) =>
    request<AddOnResponse>('/v1/add_ons/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: AddOnUpdate) =>
    request<AddOnResponse>(`/v1/add_ons/${code}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (code: string) =>
    request<void>(`/v1/add_ons/${code}`, { method: 'DELETE' }),
  apply: (data: ApplyAddOnRequest) =>
    request<AppliedAddOnResponse>('/v1/add_ons/apply', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Credit Notes API
export const creditNotesApi = {
  list: (params?: { skip?: number; limit?: number; customer_id?: string; invoice_id?: string }) =>
    request<CreditNoteResponse[]>(`/v1/credit_notes/${buildQuery(params)}`),
  get: (id: string) => request<CreditNoteResponse>(`/v1/credit_notes/${id}`),
  create: (data: CreditNoteCreate) =>
    request<CreditNoteResponse>('/v1/credit_notes/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: CreditNoteUpdate) =>
    request<CreditNoteResponse>(`/v1/credit_notes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  finalize: (id: string) =>
    request<CreditNoteResponse>(`/v1/credit_notes/${id}/finalize`, { method: 'POST' }),
  void: (id: string) =>
    request<CreditNoteResponse>(`/v1/credit_notes/${id}/void`, { method: 'POST' }),
  downloadPdf: (id: string): Promise<Blob> =>
    requestBlob(`/v1/credit_notes/${id}/download_pdf`, { method: 'POST' }),
  sendEmail: (id: string) =>
    request<{ sent: boolean }>(`/v1/credit_notes/${id}/send_email`, { method: 'POST' }),
}

// Taxes API
export const taxesApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<TaxResponse[]>(`/v1/taxes/${buildQuery(params)}`),
  get: (code: string) => request<TaxResponse>(`/v1/taxes/${code}`),
  create: (data: TaxCreate) =>
    request<TaxResponse>('/v1/taxes/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: TaxUpdate) =>
    request<TaxResponse>(`/v1/taxes/${code}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (code: string) =>
    request<void>(`/v1/taxes/${code}`, { method: 'DELETE' }),
  apply: (data: ApplyTaxRequest) =>
    request<AppliedTaxResponse>('/v1/taxes/apply', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  removeApplied: (appliedTaxId: string) =>
    request<void>(`/v1/taxes/applied/${appliedTaxId}`, { method: 'DELETE' }),
  listApplied: (params: { taxable_type: string; taxable_id: string }) =>
    request<AppliedTaxResponse[]>(`/v1/taxes/applied${buildQuery(params)}`),
}

// Webhook Endpoints API
export const webhookEndpointsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<WebhookEndpointResponse[]>(`/v1/webhook_endpoints/${buildQuery(params)}`),
  get: (id: string) => request<WebhookEndpointResponse>(`/v1/webhook_endpoints/${id}`),
  create: (data: WebhookEndpointCreate) =>
    request<WebhookEndpointResponse>('/v1/webhook_endpoints/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: WebhookEndpointUpdate) =>
    request<WebhookEndpointResponse>(`/v1/webhook_endpoints/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/webhook_endpoints/${id}`, { method: 'DELETE' }),
  listWebhooks: (params?: { skip?: number; limit?: number; endpoint_id?: string; status?: string }) =>
    request<WebhookResponse[]>(`/v1/webhook_endpoints/hooks/list${buildQuery(params)}`),
  getWebhook: (webhookId: string) =>
    request<WebhookResponse>(`/v1/webhook_endpoints/hooks/${webhookId}`),
  retryWebhook: (webhookId: string) =>
    request<WebhookResponse>(`/v1/webhook_endpoints/hooks/${webhookId}/retry`, { method: 'POST' }),
}

// Organizations API
export const organizationsApi = {
  create: (data: OrganizationCreate) =>
    request<OrganizationResponse & { api_key: ApiKeyCreateResponse }>('/v1/organizations/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  list: () => request<OrganizationResponse[]>('/v1/organizations/'),
  getCurrent: () => request<OrganizationResponse>('/v1/organizations/current'),
  updateCurrent: (data: OrganizationUpdate) =>
    request<OrganizationResponse>('/v1/organizations/current', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  createApiKey: (data: ApiKeyCreate) =>
    request<ApiKeyCreateResponse>('/v1/organizations/current/api_keys', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listApiKeys: () =>
    request<ApiKeyListResponse[]>('/v1/organizations/current/api_keys'),
  revokeApiKey: (apiKeyId: string) =>
    request<void>(`/v1/organizations/current/api_keys/${apiKeyId}`, { method: 'DELETE' }),
}

// Dunning Campaigns API
export const dunningCampaignsApi = {
  list: (params?: { skip?: number; limit?: number; status?: string }) =>
    request<DunningCampaignResponse[]>(`/v1/dunning_campaigns/${buildQuery(params)}`),
  get: (id: string) => request<DunningCampaignResponse>(`/v1/dunning_campaigns/${id}`),
  create: (data: DunningCampaignCreate) =>
    request<DunningCampaignResponse>('/v1/dunning_campaigns/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: DunningCampaignUpdate) =>
    request<DunningCampaignResponse>(`/v1/dunning_campaigns/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/dunning_campaigns/${id}`, { method: 'DELETE' }),
}

// Commitments API
export const commitmentsApi = {
  listForPlan: (planCode: string) =>
    request<CommitmentResponse[]>(`/v1/plans/${planCode}/commitments`),
  createForPlan: (planCode: string, data: CommitmentCreateAPI) =>
    request<CommitmentResponse>(`/v1/plans/${planCode}/commitments`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: CommitmentUpdate) =>
    request<CommitmentResponse>(`/v1/commitments/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/commitments/${id}`, { method: 'DELETE' }),
}

// Usage Thresholds API
export const usageThresholdsApi = {
  listForPlan: (planCode: string) =>
    request<UsageThresholdResponse[]>(`/v1/plans/${planCode}/usage_thresholds`),
  createForPlan: (planCode: string, data: UsageThresholdCreateAPI) =>
    request<UsageThresholdResponse>(`/v1/plans/${planCode}/usage_thresholds`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  createForSubscription: (subscriptionId: string, data: UsageThresholdCreateAPI) =>
    request<UsageThresholdResponse>(`/v1/subscriptions/${subscriptionId}/usage_thresholds`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listForSubscription: (subscriptionId: string) =>
    request<UsageThresholdResponse[]>(`/v1/subscriptions/${subscriptionId}/usage_thresholds`),
  getCurrentUsage: (subscriptionId: string) =>
    request<CurrentUsageResponse>(`/v1/subscriptions/${subscriptionId}/current_usage`),
  delete: (thresholdId: string) =>
    request<void>(`/v1/usage_thresholds/${thresholdId}`, { method: 'DELETE' }),
}

// Integrations API
export const integrationsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<IntegrationResponse[]>(`/v1/integrations/${buildQuery(params)}`),
  get: (id: string) => request<IntegrationResponse>(`/v1/integrations/${id}`),
  create: (data: IntegrationCreate) =>
    request<IntegrationResponse>('/v1/integrations/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: IntegrationUpdate) =>
    request<IntegrationResponse>(`/v1/integrations/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/integrations/${id}`, { method: 'DELETE' }),
  testConnection: (id: string) =>
    request<{ success: boolean; error?: string; details?: string }>(`/v1/integrations/${id}/test`, {
      method: 'POST',
    }),
}

// Data Exports API
export const dataExportsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<DataExportResponse[]>(`/v1/data_exports/${buildQuery(params)}`),
  get: (id: string) => request<DataExportResponse>(`/v1/data_exports/${id}`),
  create: (data: DataExportCreate) =>
    request<DataExportResponse>('/v1/data_exports/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  downloadUrl: (id: string) => `${API_BASE_URL}/v1/data_exports/${id}/download`,
}

// Payment Requests API
export const paymentRequestsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    request<PaymentRequestResponse[]>(`/v1/payment_requests/${buildQuery(params)}`),
  get: (id: string) => request<PaymentRequestResponse>(`/v1/payment_requests/${id}`),
  create: (data: PaymentRequestCreate) =>
    request<PaymentRequestResponse>('/v1/payment_requests/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Audit Logs API
export const auditLogsApi = {
  list: (params?: { resource_type?: string; resource_id?: string; action?: string; skip?: number; limit?: number }) =>
    request<AuditLogResponse[]>(`/v1/audit_logs/${buildQuery(params)}`),
  getForResource: (resourceType: string, resourceId: string) =>
    request<AuditLogResponse[]>(`/v1/audit_logs/${resourceType}/${resourceId}`),
}

// Billing Entities API
export const billingEntitiesApi = {
  list: () =>
    request<BillingEntityResponse[]>('/v1/billing_entities/'),
  get: (code: string) => request<BillingEntityResponse>(`/v1/billing_entities/${code}`),
  create: (data: BillingEntityCreate) =>
    request<BillingEntityResponse>('/v1/billing_entities/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: BillingEntityUpdate) =>
    request<BillingEntityResponse>(`/v1/billing_entities/${code}`, {
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
  list: () =>
    request<FeatureResponse[]>('/v1/features/'),
  get: (code: string) => request<FeatureResponse>(`/v1/features/${code}`),
  create: (data: FeatureCreate) =>
    request<FeatureResponse>('/v1/features/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: FeatureUpdate) =>
    request<FeatureResponse>(`/v1/features/${code}`, {
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
    request<EntitlementResponse[]>(`/v1/entitlements/${buildQuery(params)}`),
  create: (data: EntitlementCreate) =>
    request<EntitlementResponse>('/v1/entitlements/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: EntitlementUpdate) =>
    request<EntitlementResponse>(`/v1/entitlements/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/entitlements/${id}`, { method: 'DELETE' }),
  copy: (data: { source_plan_id: string; target_plan_id: string }) =>
    request<EntitlementResponse[]>('/v1/entitlements/copy', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// Usage Alerts API
export const usageAlertsApi = {
  list: (params?: { subscription_id?: string; skip?: number; limit?: number }) =>
    request<UsageAlertResponse[]>(`/v1/usage_alerts/${buildQuery(params)}`),
  get: (id: string) => request<UsageAlertResponse>(`/v1/usage_alerts/${id}`),
  create: (data: UsageAlertCreate) =>
    request<UsageAlertResponse>('/v1/usage_alerts/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: UsageAlertUpdate) =>
    request<UsageAlertResponse>(`/v1/usage_alerts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/v1/usage_alerts/${id}`, { method: 'DELETE' }),
}

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
}

export { ApiError }
