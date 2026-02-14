"""Invoice preview schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class FeePreview(BaseModel):
    """Preview of a single fee/line item."""

    description: str
    units: Decimal
    unit_amount_cents: Decimal
    amount_cents: Decimal
    charge_model: str | None = None
    metric_code: str | None = None


class InvoicePreviewResponse(BaseModel):
    """Response for an invoice preview."""

    subtotal: Decimal
    tax_amount: Decimal
    coupons_amount: Decimal
    prepaid_credit_amount: Decimal
    total: Decimal
    currency: str
    fees: list[FeePreview]


class InvoicePreviewRequest(BaseModel):
    """Request body for invoice preview."""

    subscription_id: UUID
    billing_period_start: datetime | None = None
    billing_period_end: datetime | None = None


class EstimateFeesRequest(BaseModel):
    """Request body for fee estimation from a hypothetical event."""

    subscription_id: UUID
    code: str
    properties: dict[str, Any] = {}


class EstimateFeesResponse(BaseModel):
    """Response for fee estimation."""

    charge_model: str | None = None
    metric_code: str
    units: Decimal
    amount_cents: Decimal
    unit_amount_cents: Decimal
