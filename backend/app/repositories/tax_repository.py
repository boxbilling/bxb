"""Tax repository for data access."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.tax import Tax
from app.schemas.tax import TaxCreate, TaxUpdate


class TaxRepository:
    """Repository for Tax model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(self, organization_id: UUID, skip: int = 0, limit: int = 100) -> list[Tax]:
        """Get all taxes."""
        return (
            self.db.query(Tax)
            .filter(Tax.organization_id == organization_id)
            .order_by(Tax.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id(self, tax_id: UUID, organization_id: UUID | None = None) -> Tax | None:
        """Get a tax by ID."""
        query = self.db.query(Tax).filter(Tax.id == tax_id)
        if organization_id is not None:
            query = query.filter(Tax.organization_id == organization_id)
        return query.first()

    def get_by_code(self, code: str, organization_id: UUID) -> Tax | None:
        """Get a tax by code."""
        return (
            self.db.query(Tax)
            .filter(Tax.code == code, Tax.organization_id == organization_id)
            .first()
        )

    def get_organization_defaults(self, organization_id: UUID) -> list[Tax]:
        """Get taxes that apply to the entire organization."""
        return (
            self.db.query(Tax)
            .filter(
                Tax.applied_to_organization.is_(True),
                Tax.organization_id == organization_id,
            )
            .order_by(Tax.created_at.desc())
            .all()
        )

    def create(self, data: TaxCreate, organization_id: UUID) -> Tax:
        """Create a new tax."""
        tax = Tax(
            code=data.code,
            name=data.name,
            rate=data.rate,
            description=data.description,
            applied_to_organization=data.applied_to_organization,
            organization_id=organization_id,
        )
        self.db.add(tax)
        self.db.commit()
        self.db.refresh(tax)
        return tax

    def update(self, code: str, data: TaxUpdate, organization_id: UUID) -> Tax | None:
        """Update a tax by code."""
        tax = self.get_by_code(code, organization_id=organization_id)
        if not tax:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(tax, key, value)

        self.db.commit()
        self.db.refresh(tax)
        return tax

    def delete(self, code: str, organization_id: UUID) -> bool:
        """Delete a tax by code."""
        tax = self.get_by_code(code, organization_id=organization_id)
        if not tax:
            return False

        self.db.delete(tax)
        self.db.commit()
        return True
