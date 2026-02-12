"""CreditNoteItem model for individual line items in a credit note."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, func

from app.core.database import Base
from app.models.customer import UUIDType


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class CreditNoteItem(Base):
    """CreditNoteItem model - line item referencing a fee within a credit note."""

    __tablename__ = "credit_note_items"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    credit_note_id = Column(
        UUIDType,
        ForeignKey("credit_notes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fee_id = Column(
        UUIDType, ForeignKey("fees.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    amount_cents = Column(Numeric(12, 4), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
