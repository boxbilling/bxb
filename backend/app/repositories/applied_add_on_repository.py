"""AppliedAddOn repository for data access."""

from uuid import UUID

from sqlalchemy.orm import Session

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
    ) -> list[AppliedAddOn]:
        """Get all applied add-ons with optional filters."""
        query = self.db.query(AppliedAddOn)

        if customer_id:
            query = query.filter(AppliedAddOn.customer_id == customer_id)

        return query.order_by(AppliedAddOn.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_id(self, applied_add_on_id: UUID) -> AppliedAddOn | None:
        """Get an applied add-on by ID."""
        return (
            self.db.query(AppliedAddOn).filter(AppliedAddOn.id == applied_add_on_id).first()
        )

    def get_by_customer_id(self, customer_id: UUID) -> list[AppliedAddOn]:
        """Get all applied add-ons for a customer."""
        return (
            self.db.query(AppliedAddOn)
            .filter(AppliedAddOn.customer_id == customer_id)
            .order_by(AppliedAddOn.created_at.desc())
            .all()
        )

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
