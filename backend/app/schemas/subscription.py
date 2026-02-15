from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.subscription import BillingTime, SubscriptionStatus, TerminationAction


class SubscriptionCreate(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=255)
    customer_id: UUID
    plan_id: UUID
    started_at: datetime | None = None
    billing_time: BillingTime = BillingTime.CALENDAR
    trial_period_days: int = 0
    subscription_at: datetime | None = None
    pay_in_advance: bool = False
    on_termination_action: TerminationAction = TerminationAction.GENERATE_INVOICE


class SubscriptionUpdate(BaseModel):
    plan_id: UUID | None = None
    status: SubscriptionStatus | None = None
    ending_at: datetime | None = None
    canceled_at: datetime | None = None
    billing_time: BillingTime | None = None
    trial_period_days: int | None = None
    trial_ended_at: datetime | None = None
    subscription_at: datetime | None = None
    pay_in_advance: bool | None = None
    previous_plan_id: UUID | None = None
    downgraded_at: datetime | None = None
    on_termination_action: TerminationAction | None = None


class SubscriptionResponse(BaseModel):
    id: UUID
    external_id: str
    customer_id: UUID
    plan_id: UUID
    status: SubscriptionStatus
    billing_time: str
    trial_period_days: int
    trial_ended_at: datetime | None
    subscription_at: datetime | None
    pay_in_advance: bool
    previous_plan_id: UUID | None
    downgraded_at: datetime | None
    on_termination_action: str
    started_at: datetime | None
    ending_at: datetime | None
    canceled_at: datetime | None
    paused_at: datetime | None
    resumed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChangePlanPreviewRequest(BaseModel):
    """Request body for plan change preview."""

    new_plan_id: UUID
    effective_date: datetime | None = Field(
        default=None,
        description="When the plan change takes effect. Defaults to now.",
    )


class PlanSummary(BaseModel):
    """Summary of a plan for comparison."""

    id: UUID
    name: str
    code: str
    interval: str
    amount_cents: int
    currency: str


class ProrationDetail(BaseModel):
    """Proration calculation detail."""

    days_remaining: int
    total_days: int
    current_plan_credit_cents: int
    new_plan_charge_cents: int
    net_amount_cents: int


class ChangePlanPreviewResponse(BaseModel):
    """Response for plan change preview showing comparison and proration."""

    current_plan: PlanSummary
    new_plan: PlanSummary
    effective_date: datetime
    proration: ProrationDetail


class NextBillingDateResponse(BaseModel):
    """Response for next billing date calculation."""

    next_billing_date: datetime
    current_period_started_at: datetime
    interval: str
    days_until_next_billing: int


class PortalSubscriptionResponse(BaseModel):
    """Subscription response enriched with plan details for portal display."""

    id: UUID
    external_id: str
    status: SubscriptionStatus
    started_at: datetime | None
    canceled_at: datetime | None
    paused_at: datetime | None
    downgraded_at: datetime | None
    created_at: datetime
    plan: PlanSummary
    pending_downgrade_plan: PlanSummary | None = None


class PortalPlanResponse(BaseModel):
    """Plan info suitable for portal display."""

    id: UUID
    name: str
    code: str
    description: str | None
    interval: str
    amount_cents: int
    currency: str


class PortalChangePlanRequest(BaseModel):
    """Request body for portal plan change."""

    new_plan_id: UUID
