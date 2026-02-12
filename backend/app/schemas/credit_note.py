"""CreditNote and CreditNoteItem schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.credit_note import (
    CreditNoteReason,
    CreditNoteStatus,
    CreditNoteType,
    CreditStatus,
    RefundStatus,
)


class CreditNoteItemCreate(BaseModel):
    fee_id: UUID
    amount_cents: Decimal


class CreditNoteCreate(BaseModel):
    number: str = Field(max_length=50)
    invoice_id: UUID
    customer_id: UUID
    credit_note_type: CreditNoteType
    reason: CreditNoteReason
    description: str | None = None
    credit_amount_cents: Decimal = Decimal("0")
    refund_amount_cents: Decimal = Decimal("0")
    total_amount_cents: Decimal = Decimal("0")
    taxes_amount_cents: Decimal = Decimal("0")
    currency: str = Field(min_length=3, max_length=3)
    items: list[CreditNoteItemCreate] = Field(default_factory=list)


class CreditNoteUpdate(BaseModel):
    description: str | None = None
    credit_amount_cents: Decimal | None = None
    refund_amount_cents: Decimal | None = None
    total_amount_cents: Decimal | None = None
    taxes_amount_cents: Decimal | None = None
    reason: CreditNoteReason | None = None
    status: CreditNoteStatus | None = None
    credit_status: CreditStatus | None = None
    refund_status: RefundStatus | None = None


class CreditNoteItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    credit_note_id: UUID
    fee_id: UUID
    amount_cents: Decimal
    created_at: datetime


class CreditNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: str
    invoice_id: UUID
    customer_id: UUID
    credit_note_type: str
    status: str
    credit_status: str | None = None
    refund_status: str | None = None
    reason: str
    description: str | None = None
    credit_amount_cents: Decimal
    refund_amount_cents: Decimal
    balance_amount_cents: Decimal
    total_amount_cents: Decimal
    taxes_amount_cents: Decimal
    currency: str
    issued_at: datetime | None = None
    voided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
