from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    total_customers: int
    active_subscriptions: int
    monthly_recurring_revenue: float
    total_invoiced: float
    currency: str


class RecentActivityResponse(BaseModel):
    id: str
    type: str
    description: str
    timestamp: str
