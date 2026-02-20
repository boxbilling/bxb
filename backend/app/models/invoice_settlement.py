"""InvoiceSettlement model for tracking how invoices are paid."""

from enum import Enum

from sqlalchemy import Column, DateTime, Index, Numeric, String, func
from sqlalchemy.schema import ForeignKey

from app.core.database import Base
from app.models.shared import UUIDType, generate_uuid


class SettlementType(str, Enum):
    """Settlement type enum."""

    PAYMENT = "payment"
    CREDIT_NOTE = "credit_note"
    WALLET_CREDIT = "wallet_credit"


class InvoiceSettlement(Base):
    """InvoiceSettlement model - tracks how invoices are settled.

    Each record represents a portion of an invoice being settled
    by a payment, credit note, or wallet credit.
    """

    __tablename__ = "invoice_settlements"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    invoice_id = Column(
        UUIDType, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    settlement_type = Column(String(20), nullable=False)
    source_id = Column(UUIDType, nullable=False)
    amount_cents = Column(Numeric(12, 4), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_invoice_settlements_type_source", "settlement_type", "source_id"),)
