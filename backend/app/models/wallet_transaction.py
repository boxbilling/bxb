"""WalletTransaction model for tracking wallet credit movements."""

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType


class TransactionType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"


class TransactionTransactionStatus(str, Enum):
    PURCHASED = "purchased"
    GRANTED = "granted"
    VOIDED = "voided"
    INVOICED = "invoiced"


class TransactionSource(str, Enum):
    MANUAL = "manual"
    INTERVAL = "interval"
    THRESHOLD = "threshold"


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class WalletTransaction(Base):
    """WalletTransaction model for tracking credit movements."""

    __tablename__ = "wallet_transactions"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    wallet_id = Column(
        UUIDType, ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id = Column(
        UUIDType, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    transaction_type = Column(String(20), nullable=False)
    transaction_status = Column(
        String(20), nullable=False, default=TransactionTransactionStatus.GRANTED.value
    )
    source = Column(String(20), nullable=False, default=TransactionSource.MANUAL.value)
    status = Column(String(20), nullable=False, default=TransactionStatus.PENDING.value)
    amount = Column(Numeric(12, 4), nullable=False, default=0)
    credit_amount = Column(Numeric(12, 4), nullable=False, default=0)
    invoice_id = Column(
        UUIDType, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
