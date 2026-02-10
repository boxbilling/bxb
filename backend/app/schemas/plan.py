from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.charge import ChargeModel
from app.models.plan import PlanInterval


class ChargeInput(BaseModel):
    """Charge input when creating/updating a plan."""

    billable_metric_id: UUID
    charge_model: ChargeModel
    properties: dict[str, Any] = Field(default_factory=dict)


class ChargeOutput(BaseModel):
    """Charge output in plan responses."""

    id: UUID
    plan_id: UUID
    billable_metric_id: UUID
    charge_model: ChargeModel
    properties: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlanCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    interval: PlanInterval
    amount_cents: int = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    trial_period_days: int = Field(default=0, ge=0)
    charges: list[ChargeInput] = Field(default_factory=list)


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    amount_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    trial_period_days: int | None = Field(default=None, ge=0)
    charges: list[ChargeInput] | None = None


class PlanResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    interval: PlanInterval
    amount_cents: int
    currency: str
    trial_period_days: int
    charges: list[ChargeOutput] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
