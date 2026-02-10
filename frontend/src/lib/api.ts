// API client for bxb billing platform
import type {
  Customer,
  CustomerCreate,
  CustomerUpdate,
  BillableMetric,
  BillableMetricCreate,
  BillableMetricUpdate,
  Plan,
  PlanCreate,
  PlanUpdate,
  Subscription,
  SubscriptionCreate,
  Invoice,
  DashboardStats,
  RecentActivity,
  PaginatedResponse,
} from '@/types/billing'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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
  
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(response.status, error.message || 'Request failed', error)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

// Customers API
export const customersApi = {
  list: (params?: { page?: number; per_page?: number; search?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.per_page) searchParams.set('per_page', String(params.per_page))
    if (params?.search) searchParams.set('search', params.search)
    return request<PaginatedResponse<Customer>>(
      `/v1/customers?${searchParams.toString()}`
    )
  },
  get: (id: string) => request<Customer>(`/v1/customers/${id}`),
  create: (data: CustomerCreate) =>
    request<Customer>('/v1/customers', {
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
}

// Billable Metrics API
export const billableMetricsApi = {
  list: (params?: { page?: number; per_page?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.per_page) searchParams.set('per_page', String(params.per_page))
    return request<PaginatedResponse<BillableMetric>>(
      `/v1/billable_metrics?${searchParams.toString()}`
    )
  },
  get: (code: string) => request<BillableMetric>(`/v1/billable_metrics/${code}`),
  create: (data: BillableMetricCreate) =>
    request<BillableMetric>('/v1/billable_metrics', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: BillableMetricUpdate) =>
    request<BillableMetric>(`/v1/billable_metrics/${code}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (code: string) =>
    request<void>(`/v1/billable_metrics/${code}`, { method: 'DELETE' }),
}

// Plans API
export const plansApi = {
  list: (params?: { page?: number; per_page?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.per_page) searchParams.set('per_page', String(params.per_page))
    return request<PaginatedResponse<Plan>>(
      `/v1/plans?${searchParams.toString()}`
    )
  },
  get: (code: string) => request<Plan>(`/v1/plans/${code}`),
  create: (data: PlanCreate) =>
    request<Plan>('/v1/plans', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (code: string, data: PlanUpdate) =>
    request<Plan>(`/v1/plans/${code}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (code: string) =>
    request<void>(`/v1/plans/${code}`, { method: 'DELETE' }),
}

// Subscriptions API
export const subscriptionsApi = {
  list: (params?: { page?: number; per_page?: number; customer_id?: string; status?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.per_page) searchParams.set('per_page', String(params.per_page))
    if (params?.customer_id) searchParams.set('customer_id', params.customer_id)
    if (params?.status) searchParams.set('status', params.status)
    return request<PaginatedResponse<Subscription>>(
      `/v1/subscriptions?${searchParams.toString()}`
    )
  },
  get: (id: string) => request<Subscription>(`/v1/subscriptions/${id}`),
  create: (data: SubscriptionCreate) =>
    request<Subscription>('/v1/subscriptions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  terminate: (id: string) =>
    request<Subscription>(`/v1/subscriptions/${id}/terminate`, {
      method: 'POST',
    }),
}

// Invoices API
export const invoicesApi = {
  list: (params?: { page?: number; per_page?: number; customer_id?: string; status?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.page) searchParams.set('page', String(params.page))
    if (params?.per_page) searchParams.set('per_page', String(params.per_page))
    if (params?.customer_id) searchParams.set('customer_id', params.customer_id)
    if (params?.status) searchParams.set('status', params.status)
    return request<PaginatedResponse<Invoice>>(
      `/v1/invoices?${searchParams.toString()}`
    )
  },
  get: (id: string) => request<Invoice>(`/v1/invoices/${id}`),
  finalize: (id: string) =>
    request<Invoice>(`/v1/invoices/${id}/finalize`, { method: 'POST' }),
  void: (id: string) =>
    request<Invoice>(`/v1/invoices/${id}/void`, { method: 'POST' }),
  downloadPdf: (id: string) =>
    `${API_BASE_URL}/v1/invoices/${id}/download`,
}

// Dashboard API
export const dashboardApi = {
  getStats: () => request<DashboardStats>('/v1/dashboard/stats'),
  getRecentActivity: () => request<RecentActivity[]>('/v1/dashboard/activity'),
}

export { ApiError }
