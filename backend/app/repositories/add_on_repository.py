"""AddOn repository for data access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.add_on import AddOn
from app.schemas.add_on import AddOnCreate, AddOnUpdate


class AddOnRepository:
    """Repository for AddOn model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[AddOn]:
        """Get all add-ons with pagination."""
        query = (
            self.db.query(AddOn)
            .filter(AddOn.organization_id == organization_id)
        )
        query = apply_order_by(query, AddOn, order_by)
        return query.offset(skip).limit(limit).all()

    def count(self, organization_id: UUID) -> int:
        """Count add-ons for an organization."""
        return (
            self.db.query(func.count(AddOn.id))
            .filter(AddOn.organization_id == organization_id)
            .scalar()
            or 0
        )

    def get_by_id(self, add_on_id: UUID, organization_id: UUID | None = None) -> AddOn | None:
        """Get an add-on by ID."""
        query = self.db.query(AddOn).filter(AddOn.id == add_on_id)
        if organization_id is not None:
            query = query.filter(AddOn.organization_id == organization_id)
        return query.first()

    def get_by_code(self, code: str, organization_id: UUID) -> AddOn | None:
        """Get an add-on by code."""
        return (
            self.db.query(AddOn)
            .filter(AddOn.code == code, AddOn.organization_id == organization_id)
            .first()
        )

    def create(self, data: AddOnCreate, organization_id: UUID) -> AddOn:
        """Create a new add-on."""
        add_on = AddOn(
            code=data.code,
            name=data.name,
            description=data.description,
            amount_cents=data.amount_cents,
            amount_currency=data.amount_currency,
            invoice_display_name=data.invoice_display_name,
            organization_id=organization_id,
        )
        self.db.add(add_on)
        self.db.commit()
        self.db.refresh(add_on)
        return add_on

    def update(self, code: str, data: AddOnUpdate, organization_id: UUID) -> AddOn | None:
        """Update an add-on by code."""
        add_on = self.get_by_code(code, organization_id=organization_id)
        if not add_on:
            return None

        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(add_on, key, value)

        self.db.commit()
        self.db.refresh(add_on)
        return add_on

    def delete(self, code: str, organization_id: UUID) -> bool:
        """Delete an add-on by code."""
        add_on = self.get_by_code(code, organization_id=organization_id)
        if not add_on:
            return False

        self.db.delete(add_on)
        self.db.commit()
        return True
