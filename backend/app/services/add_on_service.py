"""Add-on service for applying add-ons to customers."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.applied_add_on import AppliedAddOn
from app.models.fee import FeeType
from app.models.invoice import Invoice
from app.repositories.add_on_repository import AddOnRepository
from app.repositories.applied_add_on_repository import AppliedAddOnRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.fee import FeeCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem


class AddOnService:
    """Service for applying add-ons to customers and generating one-off invoices."""

    def __init__(self, db: Session):
        self.db = db
        self.add_on_repo = AddOnRepository(db)
        self.applied_add_on_repo = AppliedAddOnRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.fee_repo = FeeRepository(db)

    def apply_add_on(
        self,
        add_on_code: str,
        customer_id: UUID,
        amount_override: Decimal | None = None,
    ) -> tuple[AppliedAddOn, Invoice]:
        """Apply an add-on to a customer, creating an AppliedAddOn and a one-off Invoice with Fee.

        Args:
            add_on_code: The add-on code to apply.
            customer_id: The customer to apply the add-on to.
            amount_override: Optional override for the amount in cents.

        Returns:
            Tuple of (AppliedAddOn, Invoice) created.

        Raises:
            ValueError: If validation fails.
        """
        # Validate add-on exists
        add_on = self.add_on_repo.get_by_code(add_on_code)
        if not add_on:
            raise ValueError(f"Add-on '{add_on_code}' not found")

        # Validate customer exists
        customer = self.customer_repo.get_by_id(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        # Determine amount
        amount_cents = (
            amount_override if amount_override is not None else Decimal(str(add_on.amount_cents))
        )
        amount_currency = str(add_on.amount_currency)

        # Create AppliedAddOn record
        applied_add_on = self.applied_add_on_repo.create(
            add_on_id=add_on.id,  # type: ignore[arg-type]
            customer_id=customer_id,
            amount_cents=amount_cents,  # type: ignore[arg-type]
            amount_currency=amount_currency,
        )

        # Build line item for the invoice
        display_name = str(add_on.invoice_display_name or add_on.name)
        line_item = InvoiceLineItem(
            description=display_name,
            quantity=Decimal("1"),
            unit_price=amount_cents,
            amount=amount_cents,
        )

        # Create one-off invoice (no subscription)
        now = datetime.now()
        invoice_data = InvoiceCreate(
            customer_id=customer_id,
            billing_period_start=now,
            billing_period_end=now,
            currency=amount_currency,
            line_items=[line_item],
        )
        invoice = self.invoice_repo.create(invoice_data)

        # Create Fee record linked to the invoice
        invoice_id = UUID(str(invoice.id))
        fee_data = FeeCreate(
            invoice_id=invoice_id,
            customer_id=customer_id,
            fee_type=FeeType.ADD_ON,
            amount_cents=amount_cents,
            total_amount_cents=amount_cents,
            units=Decimal("1"),
            unit_amount_cents=amount_cents,
            description=display_name,
        )
        self.fee_repo.create(fee_data)

        return applied_add_on, invoice
