"""Daily usage schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DailyUsageCreate(BaseModel):
    """Schema for creating/upserting a daily usage record."""

    subscription_id: UUID
    billable_metric_id: UUID
    external_customer_id: str
    usage_date: date
    usage_value: Decimal = Decimal("0")
    events_count: int = 0


class DailyUsageResponse(BaseModel):
    """Schema for daily usage response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subscription_id: UUID
    billable_metric_id: UUID
    external_customer_id: str
    usage_date: date
    usage_value: Decimal
    events_count: int
    created_at: datetime
    updated_at: datetime
