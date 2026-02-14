from pydantic import BaseModel


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


class RevenueDataPoint(BaseModel):
    month: str
    revenue: float


class RevenueResponse(BaseModel):
    mrr: float
    total_revenue_this_month: float
    outstanding_invoices: float
    overdue_amount: float
    currency: str
    monthly_trend: list[RevenueDataPoint]


class CustomerMetricsResponse(BaseModel):
    total: int
    new_this_month: int
    churned_this_month: int


class SubscriptionPlanBreakdown(BaseModel):
    plan_name: str
    count: int


class SubscriptionMetricsResponse(BaseModel):
    active: int
    new_this_month: int
    canceled_this_month: int
    by_plan: list[SubscriptionPlanBreakdown]


class UsageMetricVolume(BaseModel):
    metric_name: str
    metric_code: str
    event_count: int


class UsageMetricsResponse(BaseModel):
    top_metrics: list[UsageMetricVolume]
