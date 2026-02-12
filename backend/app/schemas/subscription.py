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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
