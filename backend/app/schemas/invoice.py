from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.invoice import InvoiceStatus, InvoiceType


class InvoiceLineItem(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    charge_id: UUID | None = None
    metric_code: str | None = None


class InvoiceCreate(BaseModel):
    customer_id: UUID
    subscription_id: UUID | None = None
    billing_entity_id: UUID | None = None
    billing_period_start: datetime
    billing_period_end: datetime
    invoice_type: InvoiceType = InvoiceType.SUBSCRIPTION
    currency: str = Field(default="USD", min_length=3, max_length=3)
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    issued_at: datetime | None = None
    due_date: datetime | None = None


class InvoiceUpdate(BaseModel):
    status: InvoiceStatus | None = None
    due_date: datetime | None = None
    issued_at: datetime | None = None
    paid_at: datetime | None = None


class InvoiceResponse(BaseModel):
    id: UUID
    invoice_number: str
    customer_id: UUID
    subscription_id: UUID | None
    status: str
    invoice_type: str
    billing_period_start: datetime
    billing_period_end: datetime
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    prepaid_credit_amount: Decimal
    coupons_amount_cents: Decimal
    progressive_billing_credit_amount_cents: Decimal
    currency: str
    line_items: list[dict[str, Any]]
    due_date: datetime | None
    issued_at: datetime | None
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
