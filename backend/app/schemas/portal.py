from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PortalUrlResponse(BaseModel):
    portal_url: str


class PortalNextBillingInfo(BaseModel):
    """Next billing date info for a single subscription."""

    subscription_id: UUID
    subscription_external_id: str
    plan_name: str
    plan_interval: str
    next_billing_date: datetime
    days_until_next_billing: int
    amount_cents: int
    currency: str


class PortalUpcomingCharge(BaseModel):
    """Upcoming charge estimate for a subscription."""

    subscription_id: UUID
    subscription_external_id: str
    plan_name: str
    base_amount_cents: int
    usage_amount_cents: int
    total_estimated_cents: int
    currency: str


class PortalUsageProgress(BaseModel):
    """Usage progress toward a plan limit/entitlement."""

    feature_name: str
    feature_code: str
    feature_type: str
    entitlement_value: str
    current_usage: Decimal | None = None
    usage_percentage: float | None = None


class PortalQuickActions(BaseModel):
    """Data for quick action cards on the portal dashboard."""

    outstanding_invoice_count: int
    outstanding_amount_cents: int
    has_wallet: bool
    wallet_balance_cents: int
    has_active_subscription: bool
    currency: str


class PortalDashboardSummaryResponse(BaseModel):
    """Aggregated dashboard summary for the portal."""

    next_billing: list[PortalNextBillingInfo]
    upcoming_charges: list[PortalUpcomingCharge]
    usage_progress: list[PortalUsageProgress]
    quick_actions: PortalQuickActions


class PortalUsageTrendPoint(BaseModel):
    """A single data point in the portal usage trend."""

    date: date
    value: Decimal
    events_count: int


class PortalUsageTrendResponse(BaseModel):
    """Usage trend response for the portal."""

    subscription_id: UUID
    start_date: date
    end_date: date
    data_points: list[PortalUsageTrendPoint]


class PortalUsageLimitItem(BaseModel):
    """A single usage limit with current usage and limit value."""

    feature_name: str
    feature_code: str
    feature_type: str
    limit_value: Decimal | None = None
    current_usage: Decimal
    usage_percentage: float | None = None


class PortalUsageLimitsResponse(BaseModel):
    """Usage limits response for a subscription."""

    subscription_id: UUID
    items: list[PortalUsageLimitItem]


class PortalProjectedUsageItem(BaseModel):
    """Projected usage for a single charge at end of billing period."""

    metric_name: str
    metric_code: str
    current_units: Decimal
    projected_units: Decimal
    current_amount_cents: Decimal
    projected_amount_cents: Decimal
    charge_model: str


class PortalProjectedUsageResponse(BaseModel):
    """Projected end-of-period usage response."""

    subscription_id: UUID
    period_start: datetime
    period_end: datetime
    days_elapsed: int
    days_remaining: int
    total_days: int
    current_total_cents: Decimal
    projected_total_cents: Decimal
    currency: str
    charges: list[PortalProjectedUsageItem]
