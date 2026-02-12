"""Fee schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.fee import FeePaymentStatus, FeeType


class FeeCreate(BaseModel):
    """Schema for creating a fee."""

    invoice_id: UUID | None = None
    charge_id: UUID | None = None
    subscription_id: UUID | None = None
    commitment_id: UUID | None = None
    customer_id: UUID
    fee_type: FeeType = FeeType.CHARGE
    amount_cents: Decimal = Decimal("0")
    taxes_amount_cents: Decimal = Decimal("0")
    total_amount_cents: Decimal = Decimal("0")
    units: Decimal = Decimal("0")
    events_count: int = 0
    unit_amount_cents: Decimal = Decimal("0")
    payment_status: FeePaymentStatus = FeePaymentStatus.PENDING
    description: str | None = None
    metric_code: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class FeeUpdate(BaseModel):
    """Schema for updating a fee."""

    payment_status: FeePaymentStatus | None = None
    description: str | None = None
    taxes_amount_cents: Decimal | None = None
    total_amount_cents: Decimal | None = None


class FeeResponse(BaseModel):
    """Schema for fee response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID | None = None
    charge_id: UUID | None = None
    subscription_id: UUID | None = None
    commitment_id: UUID | None = None
    customer_id: UUID
    fee_type: str
    amount_cents: Decimal
    taxes_amount_cents: Decimal
    total_amount_cents: Decimal
    units: Decimal
    events_count: int
    unit_amount_cents: Decimal
    payment_status: str
    description: str | None = None
    metric_code: str | None = None
    properties: dict[str, Any]
    created_at: datetime
    updated_at: datetime
