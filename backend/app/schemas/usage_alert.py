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


class UsageAlertTriggerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usage_alert_id: UUID
    current_usage: Decimal
    threshold_value: Decimal
    metric_code: str
    triggered_at: datetime


class UsageAlertStatusResponse(BaseModel):
    alert_id: UUID
    current_usage: Decimal
    threshold_value: Decimal
    usage_percentage: Decimal
    billing_period_start: datetime
    billing_period_end: datetime
