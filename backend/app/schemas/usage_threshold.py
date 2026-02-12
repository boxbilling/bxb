from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UsageThresholdCreate(BaseModel):
    plan_id: UUID | None = None
    subscription_id: UUID | None = None
    amount_cents: Decimal = Field(..., ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    recurring: bool = False
    threshold_display_name: str | None = Field(default=None, max_length=255)


class UsageThresholdResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID | None = None
    subscription_id: UUID | None = None
    amount_cents: Decimal
    currency: str
    recurring: bool
    threshold_display_name: str | None = None
    created_at: datetime
    updated_at: datetime


class AppliedUsageThresholdResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usage_threshold_id: UUID
    subscription_id: UUID
    invoice_id: UUID | None = None
    crossed_at: datetime
    lifetime_usage_amount_cents: Decimal | None = None
    created_at: datetime
