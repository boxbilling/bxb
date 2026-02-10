from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.subscription import SubscriptionStatus


class SubscriptionCreate(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=255)
    customer_id: UUID
    plan_id: UUID
    started_at: datetime | None = None


class SubscriptionUpdate(BaseModel):
    status: SubscriptionStatus | None = None
    ending_at: datetime | None = None
    canceled_at: datetime | None = None


class SubscriptionResponse(BaseModel):
    id: UUID
    external_id: str
    customer_id: UUID
    plan_id: UUID
    status: SubscriptionStatus
    started_at: datetime | None
    ending_at: datetime | None
    canceled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
