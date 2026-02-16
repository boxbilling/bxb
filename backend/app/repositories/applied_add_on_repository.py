"""AppliedAddOn repository for data access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.applied_add_on import AppliedAddOn


class AppliedAddOnRepository:
    """Repository for AppliedAddOn model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        customer_id: UUID | None = None,
        order_by: str | None = None,
    ) -> list[AppliedAddOn]:
        """Get all applied add-ons with optional filters."""
        query = self.db.query(AppliedAddOn)

        if customer_id:
            query = query.filter(AppliedAddOn.customer_id == customer_id)

        query = apply_order_by(query, AppliedAddOn, order_by)
        return query.offset(skip).limit(limit).all()

    def get_by_id(self, applied_add_on_id: UUID) -> AppliedAddOn | None:
        """Get an applied add-on by ID."""
        return self.db.query(AppliedAddOn).filter(AppliedAddOn.id == applied_add_on_id).first()

    def get_by_customer_id(self, customer_id: UUID) -> list[AppliedAddOn]:
        """Get all applied add-ons for a customer."""
        return (
            self.db.query(AppliedAddOn)
            .filter(AppliedAddOn.customer_id == customer_id)
            .order_by(AppliedAddOn.created_at.desc())
            .all()
        )

    def get_by_add_on_id(self, add_on_id: UUID) -> list[AppliedAddOn]:
        """Get all applied add-ons for an add-on."""
        return (
            self.db.query(AppliedAddOn)
            .filter(AppliedAddOn.add_on_id == add_on_id)
            .order_by(AppliedAddOn.created_at.desc())
            .all()
        )

    def application_counts(self) -> dict[str, int]:
        """Return a mapping of add_on_id -> application count."""
        rows = (
            self.db.query(
                AppliedAddOn.add_on_id,
                func.count(AppliedAddOn.id),
            )
            .group_by(AppliedAddOn.add_on_id)
            .all()
        )
        return {str(add_on_id): cnt for add_on_id, cnt in rows}

    def create(
        self,
        add_on_id: UUID,
        customer_id: UUID,
        amount_cents: float,
        amount_currency: str,
    ) -> AppliedAddOn:
        """Create a new applied add-on."""
        applied_add_on = AppliedAddOn(
            add_on_id=add_on_id,
            customer_id=customer_id,
            amount_cents=amount_cents,
            amount_currency=amount_currency,
        )
        self.db.add(applied_add_on)
        self.db.commit()
        self.db.refresh(applied_add_on)
        return applied_add_on
