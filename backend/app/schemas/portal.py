from datetime import datetime
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
