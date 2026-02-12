from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChargeFilterValueCreate(BaseModel):
    billable_metric_filter_id: UUID
    value: str = Field(..., min_length=1, max_length=255)


class ChargeFilterCreate(BaseModel):
    properties: dict[str, Any] = Field(default_factory=dict)
    invoice_display_name: str | None = Field(default=None, max_length=255)
    values: list[ChargeFilterValueCreate] = Field(default_factory=list)


class ChargeFilterValueResponse(BaseModel):
    id: UUID
    charge_filter_id: UUID
    billable_metric_filter_id: UUID
    value: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChargeFilterResponse(BaseModel):
    id: UUID
    charge_id: UUID
    properties: dict[str, Any]
    invoice_display_name: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
