"""PaymentRequest schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PaymentRequestInvoiceResponse(BaseModel):
    """Schema for payment request invoice join response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_request_id: UUID
    invoice_id: UUID
    created_at: datetime


class PaymentRequestCreate(BaseModel):
    """Schema for creating a manual payment request."""

    customer_id: UUID
    invoice_ids: list[UUID] = Field(..., min_length=1)


class PaymentRequestResponse(BaseModel):
    """Schema for payment request response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    customer_id: UUID
    dunning_campaign_id: UUID | None = None
    amount_cents: Decimal
    amount_currency: str
    payment_status: str
    payment_attempts: int
    ready_for_payment_processing: bool
    invoices: list[PaymentRequestInvoiceResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
