"""Coupon and AppliedCoupon schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.coupon import CouponExpiration, CouponFrequency, CouponStatus, CouponType


class CouponCreate(BaseModel):
    code: str = Field(max_length=255)
    name: str = Field(max_length=255)
    description: str | None = None
    coupon_type: CouponType
    amount_cents: Decimal | None = None
    amount_currency: str | None = Field(default=None, min_length=3, max_length=3)
    percentage_rate: Decimal | None = None
    frequency: CouponFrequency
    frequency_duration: int | None = None
    reusable: bool = True
    expiration: CouponExpiration = CouponExpiration.NO_EXPIRATION
    expiration_at: datetime | None = None


class CouponUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    expiration: CouponExpiration | None = None
    expiration_at: datetime | None = None
    status: CouponStatus | None = None


class CouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None = None
    coupon_type: str
    amount_cents: Decimal | None = None
    amount_currency: str | None = None
    percentage_rate: Decimal | None = None
    frequency: str
    frequency_duration: int | None = None
    reusable: bool
    expiration: str
    expiration_at: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ApplyCouponRequest(BaseModel):
    coupon_code: str
    customer_id: UUID
    amount_cents: Decimal | None = None
    amount_currency: str | None = Field(default=None, min_length=3, max_length=3)
    percentage_rate: Decimal | None = None


class AppliedCouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    coupon_id: UUID
    customer_id: UUID
    amount_cents: Decimal | None = None
    amount_currency: str | None = None
    percentage_rate: Decimal | None = None
    frequency: str
    frequency_duration: int | None = None
    frequency_duration_remaining: int | None = None
    status: str
    terminated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CouponAnalyticsResponse(BaseModel):
    """Analytics data for a coupon."""

    times_applied: int
    active_applications: int
    terminated_applications: int
    total_discount_cents: Decimal
    remaining_uses: int | None = None


class PortalRedeemCouponRequest(BaseModel):
    """Request body for portal coupon code redemption."""

    coupon_code: str = Field(max_length=255)


class PortalAppliedCouponResponse(BaseModel):
    """Response for a portal-applied coupon with user-friendly details."""

    id: UUID
    coupon_code: str
    coupon_name: str
    coupon_type: str
    amount_cents: Decimal | None = None
    amount_currency: str | None = None
    percentage_rate: Decimal | None = None
    frequency: str
    frequency_duration: int | None = None
    frequency_duration_remaining: int | None = None
    status: str
    created_at: datetime
