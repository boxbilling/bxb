from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UsageAlertCreate(BaseModel):
    subscription_id: UUID
    billable_metric_id: UUID
    threshold_value: Decimal = Field(..., gt=0)
    recurring: bool = False
    name: str | None = Field(default=None, max_length=255)


class UsageAlertUpdate(BaseModel):
    threshold_value: Decimal | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, max_length=255)
    recurring: bool | None = None


class UsageAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    subscription_id: UUID
    billable_metric_id: UUID
    threshold_value: Decimal
    recurring: bool
    name: str | None = None
    times_triggered: int
    triggered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
