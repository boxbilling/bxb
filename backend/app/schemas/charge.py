from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.charge import ChargeModel


class ChargeCreate(BaseModel):
    billable_metric_id: UUID
    charge_model: ChargeModel
    properties: dict[str, Any] = Field(default_factory=dict)


class ChargeUpdate(BaseModel):
    charge_model: ChargeModel | None = None
    properties: dict[str, Any] | None = None


class ChargeResponse(BaseModel):
    id: UUID
    plan_id: UUID
    billable_metric_id: UUID
    charge_model: ChargeModel
    properties: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
