"""AddOn repository for data access."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.add_on import AddOn
from app.schemas.add_on import AddOnCreate, AddOnUpdate


class AddOnRepository:
    """Repository for AddOn model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AddOn]:
        """Get all add-ons with pagination."""
        return (
            self.db.query(AddOn)
            .order_by(AddOn.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id(self, add_on_id: UUID) -> AddOn | None:
        """Get an add-on by ID."""
        return self.db.query(AddOn).filter(AddOn.id == add_on_id).first()

    def get_by_code(self, code: str) -> AddOn | None:
        """Get an add-on by code."""
        return self.db.query(AddOn).filter(AddOn.code == code).first()

    def create(self, data: AddOnCreate) -> AddOn:
        """Create a new add-on."""
        add_on = AddOn(
            code=data.code,
            name=data.name,
            description=data.description,
            amount_cents=data.amount_cents,
            amount_currency=data.amount_currency,
            invoice_display_name=data.invoice_display_name,
        )
        self.db.add(add_on)
        self.db.commit()
        self.db.refresh(add_on)
        return add_on

    def update(self, code: str, data: AddOnUpdate) -> AddOn | None:
        """Update an add-on by code."""
        add_on = self.get_by_code(code)
        if not add_on:
            return None

        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(add_on, key, value)

        self.db.commit()
        self.db.refresh(add_on)
        return add_on

    def delete(self, code: str) -> bool:
        """Delete an add-on by code."""
        add_on = self.get_by_code(code)
        if not add_on:
            return False

        self.db.delete(add_on)
        self.db.commit()
        return True
