"""AppliedCoupon repository for data access."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.applied_coupon import AppliedCoupon, AppliedCouponStatus


class AppliedCouponRepository:
    """Repository for AppliedCoupon model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        customer_id: UUID | None = None,
        status: AppliedCouponStatus | None = None,
        order_by: str | None = None,
    ) -> list[AppliedCoupon]:
        """Get all applied coupons with optional filters."""
        query = self.db.query(AppliedCoupon)

        if customer_id:
            query = query.filter(AppliedCoupon.customer_id == customer_id)
        if status:
            query = query.filter(AppliedCoupon.status == status.value)

        query = apply_order_by(query, AppliedCoupon, order_by)
        return query.offset(skip).limit(limit).all()

    def get_by_id(self, applied_coupon_id: UUID) -> AppliedCoupon | None:
        """Get an applied coupon by ID."""
        return self.db.query(AppliedCoupon).filter(AppliedCoupon.id == applied_coupon_id).first()

    def get_active_by_customer_id(self, customer_id: UUID) -> list[AppliedCoupon]:
        """Get all active applied coupons for a customer."""
        return (
            self.db.query(AppliedCoupon)
            .filter(
                AppliedCoupon.customer_id == customer_id,
                AppliedCoupon.status == AppliedCouponStatus.ACTIVE.value,
            )
            .order_by(AppliedCoupon.created_at.asc())
            .all()
        )

    def get_by_coupon_and_customer(
        self, coupon_id: UUID, customer_id: UUID
    ) -> AppliedCoupon | None:
        """Get an applied coupon by coupon and customer."""
        return (
            self.db.query(AppliedCoupon)
            .filter(
                AppliedCoupon.coupon_id == coupon_id,
                AppliedCoupon.customer_id == customer_id,
            )
            .first()
        )

    def create(
        self,
        coupon_id: UUID,
        customer_id: UUID,
        amount_cents: float | None,
        amount_currency: str | None,
        percentage_rate: float | None,
        frequency: str,
        frequency_duration: int | None,
    ) -> AppliedCoupon:
        """Create a new applied coupon."""
        frequency_duration_remaining = frequency_duration if frequency == "recurring" else None

        applied_coupon = AppliedCoupon(
            coupon_id=coupon_id,
            customer_id=customer_id,
            amount_cents=amount_cents,
            amount_currency=amount_currency,
            percentage_rate=percentage_rate,
            frequency=frequency,
            frequency_duration=frequency_duration,
            frequency_duration_remaining=frequency_duration_remaining,
        )
        self.db.add(applied_coupon)
        self.db.commit()
        self.db.refresh(applied_coupon)
        return applied_coupon

    def decrement_frequency(self, applied_coupon_id: UUID) -> AppliedCoupon | None:
        """Decrement frequency_duration_remaining, terminate if reaches 0."""
        applied_coupon = self.get_by_id(applied_coupon_id)
        if not applied_coupon:
            return None

        if applied_coupon.frequency_duration_remaining is not None:
            applied_coupon.frequency_duration_remaining -= 1  # type: ignore[assignment]
            if applied_coupon.frequency_duration_remaining <= 0:
                applied_coupon.status = AppliedCouponStatus.TERMINATED.value  # type: ignore[assignment]
                applied_coupon.terminated_at = datetime.now()  # type: ignore[assignment]

        self.db.commit()
        self.db.refresh(applied_coupon)
        return applied_coupon

    def terminate(self, applied_coupon_id: UUID) -> AppliedCoupon | None:
        """Terminate an applied coupon."""
        applied_coupon = self.get_by_id(applied_coupon_id)
        if not applied_coupon:
            return None

        applied_coupon.status = AppliedCouponStatus.TERMINATED.value  # type: ignore[assignment]
        applied_coupon.terminated_at = datetime.now()  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(applied_coupon)
        return applied_coupon

    def get_all_by_coupon_id(self, coupon_id: UUID) -> list[AppliedCoupon]:
        """Get all applied coupons for a specific coupon."""
        return (
            self.db.query(AppliedCoupon)
            .filter(AppliedCoupon.coupon_id == coupon_id)
            .order_by(AppliedCoupon.created_at.desc())
            .all()
        )

    def count_by_coupon_id(self, coupon_id: UUID) -> int:
        """Count applied coupons for a specific coupon."""
        from sqlalchemy import func as sa_func

        return (
            self.db.query(sa_func.count(AppliedCoupon.id))
            .filter(AppliedCoupon.coupon_id == coupon_id)
            .scalar()
            or 0
        )
