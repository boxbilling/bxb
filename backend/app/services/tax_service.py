"""Tax calculation service for determining and applying taxes."""

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.applied_tax import AppliedTax
from app.models.customer import DEFAULT_ORGANIZATION_ID
from app.models.tax import Tax
from app.repositories.applied_tax_repository import AppliedTaxRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.tax_repository import TaxRepository


@dataclass
class TaxCalculationResult:
    """Result of a tax calculation."""

    taxes_amount_cents: Decimal
    applied_taxes: list[AppliedTax] = field(default_factory=list)


class TaxCalculationService:
    """Service for tax calculation and application."""

    def __init__(self, db: Session):
        self.db = db
        self.tax_repo = TaxRepository(db)
        self.applied_tax_repo = AppliedTaxRepository(db)
        self.fee_repo = FeeRepository(db)
        self.invoice_repo = InvoiceRepository(db)

    def get_applicable_taxes(
        self,
        customer_id: UUID,
        plan_id: UUID | None = None,
        charge_id: UUID | None = None,
        organization_id: UUID = DEFAULT_ORGANIZATION_ID,
    ) -> list[Tax]:
        """Determine which taxes apply by checking hierarchy.

        Priority order: charge-level -> plan-level -> customer-level -> org defaults.
        Returns the first non-empty level found.
        """
        # Check charge-level taxes
        if charge_id:
            applied = self.applied_tax_repo.get_by_taxable("charge", charge_id)
            if applied:
                return self._resolve_taxes(applied)

        # Check plan-level taxes
        if plan_id:
            applied = self.applied_tax_repo.get_by_taxable("plan", plan_id)
            if applied:
                return self._resolve_taxes(applied)

        # Check customer-level taxes
        applied = self.applied_tax_repo.get_by_taxable("customer", customer_id)
        if applied:
            return self._resolve_taxes(applied)

        # Fall back to organization defaults
        return self.tax_repo.get_organization_defaults(organization_id)

    def calculate_tax(
        self,
        subtotal_cents: Decimal,
        taxes: list[Tax],
    ) -> TaxCalculationResult:
        """Calculate tax amount from subtotal and applicable taxes.

        Sums all tax rates and computes tax_amount = subtotal * combined_rate.
        """
        if not taxes:
            return TaxCalculationResult(taxes_amount_cents=Decimal("0"))

        combined_rate = sum(Decimal(str(t.rate)) for t in taxes)
        tax_amount = subtotal_cents * combined_rate

        return TaxCalculationResult(
            taxes_amount_cents=tax_amount,
            applied_taxes=[],
        )

    def apply_taxes_to_fee(self, fee_id: UUID, taxes: list[Tax]) -> list[AppliedTax]:
        """Create AppliedTax records for a fee, update fee amounts."""
        fee = self.fee_repo.get_by_id(fee_id)
        if not fee:
            raise ValueError(f"Fee {fee_id} not found")

        subtotal = Decimal(str(fee.amount_cents))
        result = self.calculate_tax(subtotal, taxes)

        applied_records: list[AppliedTax] = []
        for tax in taxes:
            rate = Decimal(str(tax.rate))
            amount = subtotal * rate
            applied = self.applied_tax_repo.create(
                tax_id=tax.id,  # type: ignore[arg-type]
                taxable_type="fee",
                taxable_id=fee_id,
                tax_rate=rate,
                tax_amount_cents=amount,
            )
            applied_records.append(applied)

        # Update fee amounts
        fee.taxes_amount_cents = result.taxes_amount_cents  # type: ignore[assignment]
        fee.total_amount_cents = subtotal + result.taxes_amount_cents  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(fee)

        return applied_records

    def apply_taxes_to_invoice(self, invoice_id: UUID) -> Decimal:
        """Aggregate tax amounts from all fees on an invoice into invoice.tax_amount."""
        invoice = self.invoice_repo.get_by_id(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        fees = self.fee_repo.get_by_invoice_id(invoice_id)
        total_tax = Decimal("0")
        for fee in fees:
            total_tax += Decimal(str(fee.taxes_amount_cents))

        invoice.tax_amount = total_tax  # type: ignore[assignment]
        subtotal = Decimal(str(invoice.subtotal))
        coupons = Decimal(str(invoice.coupons_amount_cents))
        invoice.total = subtotal - coupons + total_tax  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(invoice)

        return total_tax

    def apply_tax_to_entity(
        self,
        tax_code: str,
        taxable_type: str,
        taxable_id: UUID,
        organization_id: UUID = DEFAULT_ORGANIZATION_ID,
    ) -> AppliedTax:
        """Apply a tax to any entity by code."""
        tax = self.tax_repo.get_by_code(tax_code, organization_id)
        if not tax:
            raise ValueError(f"Tax '{tax_code}' not found")

        return self.applied_tax_repo.create(
            tax_id=tax.id,  # type: ignore[arg-type]
            taxable_type=taxable_type,
            taxable_id=taxable_id,
            tax_rate=Decimal(str(tax.rate)),
        )

    def remove_tax_from_entity(
        self,
        tax_code: str,
        taxable_type: str,
        taxable_id: UUID,
        organization_id: UUID = DEFAULT_ORGANIZATION_ID,
    ) -> bool:
        """Remove a tax from an entity by code."""
        tax = self.tax_repo.get_by_code(tax_code, organization_id)
        if not tax:
            raise ValueError(f"Tax '{tax_code}' not found")

        applied_taxes = self.applied_tax_repo.get_by_taxable(taxable_type, taxable_id)
        for applied in applied_taxes:
            if applied.tax_id == tax.id:
                return self.applied_tax_repo.delete_by_id(applied.id)  # type: ignore[arg-type]

        return False

    def _resolve_taxes(self, applied_taxes: list[AppliedTax]) -> list[Tax]:
        """Resolve AppliedTax records to their Tax objects."""
        taxes: list[Tax] = []
        for applied in applied_taxes:
            tax = self.tax_repo.get_by_id(applied.tax_id)  # type: ignore[arg-type]
            if tax:
                taxes.append(tax)
        return taxes
