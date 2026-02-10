"""Payment schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentProvider, PaymentStatus


class PaymentCreate(BaseModel):
    """Schema for creating a payment."""

    invoice_id: UUID
    provider: PaymentProvider = PaymentProvider.STRIPE
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaymentUpdate(BaseModel):
    """Schema for updating a payment."""

    status: PaymentStatus | None = None
    provider_payment_id: str | None = None
    failure_reason: str | None = None
    metadata: dict[str, Any] | None = None


class PaymentResponse(BaseModel):
    """Schema for payment response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    customer_id: UUID
    amount: Decimal
    currency: str
    status: str
    provider: str
    provider_payment_id: str | None = None
    provider_checkout_id: str | None = None
    provider_checkout_url: str | None = None
    failure_reason: str | None = None
    payment_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class CheckoutSessionCreate(BaseModel):
    """Schema for creating a checkout session."""

    invoice_id: UUID
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment is canceled")


class CheckoutSessionResponse(BaseModel):
    """Schema for checkout session response."""

    payment_id: UUID
    checkout_url: str
    provider: str
    expires_at: datetime | None = None


class WebhookEvent(BaseModel):
    """Schema for incoming webhook events."""

    provider: PaymentProvider
    event_type: str
    event_id: str
    payload: dict[str, Any]
