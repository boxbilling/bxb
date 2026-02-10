// API client for bxb billing platform
import type { components } from '@/lib/schema'

// Type aliases
type CustomerResponse = components['schemas']['CustomerResponse']
type CustomerCreate = components['schemas']['CustomerCreate']
type CustomerUpdate = components['schemas']['CustomerUpdate']

type BillableMetricResponse = components['schemas']['BillableMetricResponse']
type BillableMetricCreate = components['schemas']['BillableMetricCreate']
type BillableMetricUpdate = components['schemas']['BillableMetricUpdate']

type PlanResponse = components['schemas']['PlanResponse']
type PlanCreate = components['schemas']['PlanCreate']
type PlanUpdate = components['schemas']['PlanUpdate']

type SubscriptionResponse = components['schemas']['SubscriptionResponse']
type SubscriptionCreate = components['schemas']['SubscriptionCreate']
type SubscriptionUpdate = components['schemas']['SubscriptionUpdate']

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
    throw new ApiError(response.status, error.message || error.detail || 'Request failed', error)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

// Customers API
export const customersApi = {
  list: (params?: { skip?: number; limit?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.skip) searchParams.set('skip', String(params.skip))
    if (params?.limit) searchParams.set('limit', String(params.limit))
    const query = searchParams.toString()
    return request<CustomerResponse[]>(`/v1/customers/${query ? `?${query}` : ''}`)
  },
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
}

// Billable Metrics API
export const billableMetricsApi = {
  list: (params?: { skip?: number; limit?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.skip) searchParams.set('skip', String(params.skip))
    if (params?.limit) searchParams.set('limit', String(params.limit))
    const query = searchParams.toString()
    return request<BillableMetricResponse[]>(`/v1/billable_metrics/${query ? `?${query}` : ''}`)
  },
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
}

// Plans API
export const plansApi = {
  list: (params?: { skip?: number; limit?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.skip) searchParams.set('skip', String(params.skip))
    if (params?.limit) searchParams.set('limit', String(params.limit))
    const query = searchParams.toString()
    return request<PlanResponse[]>(`/v1/plans/${query ? `?${query}` : ''}`)
  },
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
}

// Subscriptions API
export const subscriptionsApi = {
  list: (params?: { skip?: number; limit?: number; customer_id?: string }) => {
    const searchParams = new URLSearchParams()
    if (params?.skip) searchParams.set('skip', String(params.skip))
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.customer_id) searchParams.set('customer_id', params.customer_id)
    const query = searchParams.toString()
    return request<SubscriptionResponse[]>(`/v1/subscriptions/${query ? `?${query}` : ''}`)
  },
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
  cancel: (id: string) =>
    request<SubscriptionResponse>(`/v1/subscriptions/${id}/cancel`, {
      method: 'POST',
    }),
  terminate: (id: string) =>
    request<void>(`/v1/subscriptions/${id}`, { method: 'DELETE' }),
}

// Dashboard API (mock for now - not implemented in backend)
export const dashboardApi = {
  getStats: async () => {
    return {
      total_customers: 0,
      active_subscriptions: 0,
      monthly_recurring_revenue: 0,
      total_invoiced: 0,
      currency: 'USD',
    }
  },
  getRecentActivity: async () => {
    return []
  },
}

// Invoices API (mock for now - not implemented in backend)
export const invoicesApi = {
  list: async () => [],
  get: async (_id: string) => null,
  finalize: async (_id: string) => null,
  void: async (_id: string) => null,
  downloadPdf: (id: string) => `${API_BASE_URL}/v1/invoices/${id}/download`,
}

export { ApiError }
