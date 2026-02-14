"""Invoice preview schemas."""

from decimal import Decimal

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
