from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.plan import PlanInterval


class PlanCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    interval: PlanInterval
    amount_cents: int = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    trial_period_days: int = Field(default=0, ge=0)


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    amount_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    trial_period_days: int | None = Field(default=None, ge=0)


class PlanResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    interval: PlanInterval
    amount_cents: int
    currency: str
    trial_period_days: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
