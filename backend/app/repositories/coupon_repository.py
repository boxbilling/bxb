"""Coupon repository for data access."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.coupon import Coupon, CouponStatus
from app.schemas.coupon import CouponCreate, CouponUpdate


class CouponRepository:
    """Repository for Coupon model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: CouponStatus | None = None,
    ) -> list[Coupon]:
        """Get all coupons with optional filters."""
        query = self.db.query(Coupon)

        if status:
            query = query.filter(Coupon.status == status.value)

        return query.order_by(Coupon.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_id(self, coupon_id: UUID) -> Coupon | None:
        """Get a coupon by ID."""
        return self.db.query(Coupon).filter(Coupon.id == coupon_id).first()

    def get_by_code(self, code: str) -> Coupon | None:
        """Get a coupon by code."""
        return self.db.query(Coupon).filter(Coupon.code == code).first()

    def create(self, data: CouponCreate) -> Coupon:
        """Create a new coupon."""
        coupon = Coupon(
            code=data.code,
            name=data.name,
            description=data.description,
            coupon_type=data.coupon_type.value,
            amount_cents=data.amount_cents,
            amount_currency=data.amount_currency,
            percentage_rate=data.percentage_rate,
            frequency=data.frequency.value,
            frequency_duration=data.frequency_duration,
            reusable=data.reusable,
            expiration=data.expiration.value,
            expiration_at=data.expiration_at,
        )
        self.db.add(coupon)
        self.db.commit()
        self.db.refresh(coupon)
        return coupon

    def update(self, code: str, data: CouponUpdate) -> Coupon | None:
        """Update a coupon by code."""
        coupon = self.get_by_code(code)
        if not coupon:
            return None

        update_data = data.model_dump(exclude_unset=True)

        if "status" in update_data and update_data["status"]:
            update_data["status"] = update_data["status"].value
        if "expiration" in update_data and update_data["expiration"]:
            update_data["expiration"] = update_data["expiration"].value

        for key, value in update_data.items():
            setattr(coupon, key, value)

        self.db.commit()
        self.db.refresh(coupon)
        return coupon

    def terminate(self, code: str) -> Coupon | None:
        """Terminate a coupon by code."""
        coupon = self.get_by_code(code)
        if not coupon:
            return None

        coupon.status = CouponStatus.TERMINATED.value  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(coupon)
        return coupon

    def delete(self, code: str) -> bool:
        """Delete a coupon by code."""
        coupon = self.get_by_code(code)
        if not coupon:
            return False

        self.db.delete(coupon)
        self.db.commit()
        return True
