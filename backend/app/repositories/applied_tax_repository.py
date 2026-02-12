"""AppliedTax repository for data access."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.applied_tax import AppliedTax


class AppliedTaxRepository:
    """Repository for AppliedTax model."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        tax_id: UUID,
        taxable_type: str,
        taxable_id: UUID,
        tax_rate: Decimal | None = None,
        tax_amount_cents: Decimal | int = 0,
    ) -> AppliedTax:
        """Create a new applied tax record."""
        applied_tax = AppliedTax(
            tax_id=tax_id,
            taxable_type=taxable_type,
            taxable_id=taxable_id,
            tax_rate=tax_rate,
            tax_amount_cents=tax_amount_cents,
        )
        self.db.add(applied_tax)
        self.db.commit()
        self.db.refresh(applied_tax)
        return applied_tax

    def get_by_id(self, applied_tax_id: UUID) -> AppliedTax | None:
        """Get an applied tax by ID."""
        return self.db.query(AppliedTax).filter(AppliedTax.id == applied_tax_id).first()

    def get_by_taxable(self, taxable_type: str, taxable_id: UUID) -> list[AppliedTax]:
        """Get all applied taxes for a given entity."""
        return (
            self.db.query(AppliedTax)
            .filter(
                AppliedTax.taxable_type == taxable_type,
                AppliedTax.taxable_id == taxable_id,
            )
            .all()
        )

    def delete_by_taxable(self, taxable_type: str, taxable_id: UUID) -> int:
        """Delete all applied taxes for a given entity. Returns count deleted."""
        count = (
            self.db.query(AppliedTax)
            .filter(
                AppliedTax.taxable_type == taxable_type,
                AppliedTax.taxable_id == taxable_id,
            )
            .delete()
        )
        self.db.commit()
        return count

    def get_taxes_for_entity(self, taxable_type: str, taxable_id: UUID) -> list[AppliedTax]:
        """Get applied taxes for a specific entity (alias for get_by_taxable)."""
        return self.get_by_taxable(taxable_type, taxable_id)

    def delete_by_id(self, applied_tax_id: UUID) -> bool:
        """Delete an applied tax by ID."""
        applied_tax = self.get_by_id(applied_tax_id)
        if not applied_tax:
            return False
        self.db.delete(applied_tax)
        self.db.commit()
        return True
