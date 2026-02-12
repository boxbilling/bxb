"""CreditNote model for refunds, credits, and adjustments."""

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType


class CreditNoteType(str, Enum):
    CREDIT = "credit"
    REFUND = "refund"
    OFFSET = "offset"


class CreditNoteStatus(str, Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"


class CreditStatus(str, Enum):
    AVAILABLE = "available"
    CONSUMED = "consumed"
    VOIDED = "voided"


class RefundStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CreditNoteReason(str, Enum):
    DUPLICATED_CHARGE = "duplicated_charge"
    PRODUCT_UNSATISFACTORY = "product_unsatisfactory"
    ORDER_CHANGE = "order_change"
    ORDER_CANCELLATION = "order_cancellation"
    FRAUDULENT_CHARGE = "fraudulent_charge"
    OTHER = "other"


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class CreditNote(Base):
    """CreditNote model for refunds, credits, and adjustments against invoices."""

    __tablename__ = "credit_notes"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    number = Column(String(50), unique=True, index=True, nullable=False)

    invoice_id = Column(
        UUIDType, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id = Column(
        UUIDType, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    credit_note_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default=CreditNoteStatus.DRAFT.value)
    credit_status = Column(String(20), nullable=True)
    refund_status = Column(String(20), nullable=True)

    reason = Column(String(30), nullable=False)
    description = Column(Text, nullable=True)

    credit_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)
    refund_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)
    balance_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)
    total_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)
    taxes_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)

    currency = Column(String(3), nullable=False)

    issued_at = Column(DateTime(timezone=True), nullable=True)
    voided_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
