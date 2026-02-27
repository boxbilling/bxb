from pydantic import BaseModel


class TrendIndicator(BaseModel):
    previous_value: float
    change_percent: float | None  # None when previous_value is 0


class DashboardStatsResponse(BaseModel):
    total_customers: int
    active_subscriptions: int
    monthly_recurring_revenue: float
    total_invoiced: float
    total_wallet_credits: float
    currency: str


class RecentActivityResponse(BaseModel):
    id: str
    type: str
    description: str
    timestamp: str
    resource_type: str | None = None
    resource_id: str | None = None


class RevenueDataPoint(BaseModel):
    month: str
    revenue_cents: float


class RevenueResponse(BaseModel):
    mrr_cents: float
    total_revenue_this_month_cents: float
    outstanding_invoices_cents: float
    overdue_amount_cents: float
    currency: str
    monthly_trend: list[RevenueDataPoint]
    mrr_trend: TrendIndicator | None = None


class CustomerMetricsResponse(BaseModel):
    total: int
    new_this_month: int
    churned_this_month: int
    new_trend: TrendIndicator | None = None
    churned_trend: TrendIndicator | None = None


class SubscriptionPlanBreakdown(BaseModel):
    plan_name: str
    count: int


class SubscriptionMetricsResponse(BaseModel):
    active: int
    new_this_month: int
    canceled_this_month: int
    by_plan: list[SubscriptionPlanBreakdown]
    new_trend: TrendIndicator | None = None
    canceled_trend: TrendIndicator | None = None


class PlanRevenueBreakdown(BaseModel):
    plan_name: str
    revenue_cents: float


class RevenueByPlanResponse(BaseModel):
    by_plan: list[PlanRevenueBreakdown]
    currency: str


class UsageMetricVolume(BaseModel):
    metric_name: str
    metric_code: str
    event_count: int


class UsageMetricsResponse(BaseModel):
    top_metrics: list[UsageMetricVolume]


class RecentInvoiceItem(BaseModel):
    id: str
    invoice_number: str
    customer_name: str
    status: str
    total_cents: float
    currency: str
    created_at: str


class RecentSubscriptionItem(BaseModel):
    id: str
    external_id: str
    customer_name: str
    plan_name: str
    status: str
    created_at: str


class SparklinePoint(BaseModel):
    date: str
    value: float


class SparklineData(BaseModel):
    mrr: list[SparklinePoint]
    new_customers: list[SparklinePoint]
    new_subscriptions: list[SparklinePoint]


# --- Revenue Analytics Deep-Dive ---


class DailyRevenuePoint(BaseModel):
    date: str
    revenue_cents: float


class RevenueByTypeBreakdown(BaseModel):
    invoice_type: str
    revenue_cents: float
    count: int


class TopCustomerRevenue(BaseModel):
    customer_id: str
    customer_name: str
    revenue_cents: float
    invoice_count: int


class CollectionMetrics(BaseModel):
    total_invoiced_cents: float
    total_collected_cents: float
    collection_rate: float
    average_days_to_payment: float | None
    overdue_count: int
    overdue_amount_cents: float


class NetRevenueMetrics(BaseModel):
    gross_revenue_cents: float
    refunds_cents: float
    credit_notes_cents: float
    net_revenue_cents: float
    currency: str


class RevenueAnalyticsResponse(BaseModel):
    daily_revenue: list[DailyRevenuePoint]
    revenue_by_type: list[RevenueByTypeBreakdown]
    top_customers: list[TopCustomerRevenue]
    collection: CollectionMetrics
    net_revenue: NetRevenueMetrics
    currency: str
