"""AppliedCoupon model for tracking coupon applications to customers."""

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func

from app.core.database import Base
from app.models.customer import UUIDType


class AppliedCouponStatus(str, Enum):
    ACTIVE = "active"
    TERMINATED = "terminated"


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class AppliedCoupon(Base):
    """AppliedCoupon model for tracking coupon applications to customers."""

    __tablename__ = "applied_coupons"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    coupon_id = Column(
        UUIDType, ForeignKey("coupons.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id = Column(
        UUIDType, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    amount_cents = Column(Numeric(12, 4), nullable=True)
    amount_currency = Column(String(3), nullable=True)
    percentage_rate = Column(Numeric(5, 2), nullable=True)

    frequency = Column(String(20), nullable=False)
    frequency_duration = Column(Integer, nullable=True)
    frequency_duration_remaining = Column(Integer, nullable=True)

    status = Column(String(20), nullable=False, default=AppliedCouponStatus.ACTIVE.value)
    terminated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
