"""Wallet model for prepaid credits system."""

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func

from app.core.database import Base
from app.models.customer import UUIDType


class WalletStatus(str, Enum):
    ACTIVE = "active"
    TERMINATED = "terminated"


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class Wallet(Base):
    """Wallet model for prepaid credits."""

    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("customer_id", "code", name="uq_wallets_customer_id_code"),
    )

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    customer_id = Column(
        UUIDType, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name = Column(String(255), nullable=True)
    code = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default=WalletStatus.ACTIVE.value)
    balance_cents = Column(Numeric(12, 4), nullable=False, default=0)
    credits_balance = Column(Numeric(12, 4), nullable=False, default=0)
    consumed_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)
    consumed_credits = Column(Numeric(12, 4), nullable=False, default=0)
    rate_amount = Column(Numeric(12, 4), nullable=False, default=1)
    currency = Column(String(3), nullable=False, default="USD")
    expiration_at = Column(DateTime(timezone=True), nullable=True)
    priority = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
