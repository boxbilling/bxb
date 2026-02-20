"""Coupon model for promotional discounts."""

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.core.database import Base
from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class CouponType(str, Enum):
    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE = "percentage"


class CouponFrequency(str, Enum):
    ONCE = "once"
    RECURRING = "recurring"
    FOREVER = "forever"


class CouponExpiration(str, Enum):
    NO_EXPIRATION = "no_expiration"
    TIME_LIMIT = "time_limit"


class CouponStatus(str, Enum):
    ACTIVE = "active"
    TERMINATED = "terminated"


class Coupon(Base):
    """Coupon model for promotional discounts."""

    __tablename__ = "coupons"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    code = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    coupon_type = Column(String(20), nullable=False)
    amount_cents = Column(Numeric(12, 4), nullable=True)
    amount_currency = Column(String(3), nullable=True)
    percentage_rate = Column(Numeric(5, 2), nullable=True)

    frequency = Column(String(20), nullable=False)
    frequency_duration = Column(Integer, nullable=True)

    reusable = Column(Boolean, nullable=False, default=True)

    expiration = Column(String(20), nullable=False, default=CouponExpiration.NO_EXPIRATION.value)
    expiration_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(20), nullable=False, default=CouponStatus.ACTIVE.value)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
