from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate


class InvoiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def _generate_invoice_number(self) -> str:
        """Generate a unique invoice number."""
        today = datetime.now().strftime("%Y%m%d")
        prefix = f"INV-{today}-"

        # Get the highest invoice number for today
        result = (
            self.db.query(Invoice.invoice_number)
            .filter(Invoice.invoice_number.like(f"{prefix}%"))
            .order_by(Invoice.invoice_number.desc())
            .first()
        )

        if result:
            # Extract number from INV-YYYYMMDD-XXXX format
            try:
                last_num = int(result[0].split("-")[-1])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1

        return f"{prefix}{new_num:04d}"

    def get_all(
        self,
        organization_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
        customer_id: UUID | None = None,
        subscription_id: UUID | None = None,
        status: InvoiceStatus | None = None,
    ) -> list[Invoice]:
        query = self.db.query(Invoice)

        if organization_id is not None:
            query = query.filter(Invoice.organization_id == organization_id)
        if customer_id:
            query = query.filter(Invoice.customer_id == customer_id)
        if subscription_id:
            query = query.filter(Invoice.subscription_id == subscription_id)
        if status:
            query = query.filter(Invoice.status == status.value)

        return query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_id(self, invoice_id: UUID, organization_id: UUID | None = None) -> Invoice | None:
        query = self.db.query(Invoice).filter(Invoice.id == invoice_id)
        if organization_id is not None:
            query = query.filter(Invoice.organization_id == organization_id)
        return query.first()

    def get_by_invoice_number(self, invoice_number: str) -> Invoice | None:
        return self.db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()

    def create(self, data: InvoiceCreate, organization_id: UUID | None = None) -> Invoice:
        # Calculate totals from line items
        subtotal = Decimal(0)
        for item in data.line_items:
            subtotal += item.amount

        # Convert line items to dict format for JSON storage
        line_items_json = [item.model_dump(mode="json") for item in data.line_items]

        kwargs: dict[str, Any] = {
            "invoice_number": self._generate_invoice_number(),
            "customer_id": data.customer_id,
            "subscription_id": data.subscription_id,
            "billing_period_start": data.billing_period_start,
            "billing_period_end": data.billing_period_end,
            "invoice_type": data.invoice_type.value,
            "currency": data.currency,
            "subtotal": subtotal,
            "tax_amount": Decimal(0),
            "total": subtotal,
            "line_items": line_items_json,
            "issued_at": data.issued_at,
            "due_date": data.due_date,
        }
        if organization_id is not None:
            kwargs["organization_id"] = organization_id

        invoice = Invoice(**kwargs)
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def update(
        self, invoice_id: UUID, data: InvoiceUpdate, organization_id: UUID | None = None
    ) -> Invoice | None:
        invoice = self.get_by_id(invoice_id, organization_id)
        if not invoice:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Convert status enum to string value
        if "status" in update_data and update_data["status"]:
            update_data["status"] = update_data["status"].value

        for key, value in update_data.items():
            setattr(invoice, key, value)

        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def finalize(self, invoice_id: UUID) -> Invoice | None:
        """Finalize an invoice (set status and issued_at)."""
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        if invoice.status != InvoiceStatus.DRAFT.value:
            raise ValueError("Only draft invoices can be finalized")

        invoice.status = InvoiceStatus.FINALIZED.value  # type: ignore[assignment]
        invoice.issued_at = datetime.now()  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def mark_paid(self, invoice_id: UUID) -> Invoice | None:
        """Mark an invoice as paid."""
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        if invoice.status not in [InvoiceStatus.FINALIZED.value]:
            raise ValueError("Only finalized invoices can be marked as paid")

        invoice.status = InvoiceStatus.PAID.value  # type: ignore[assignment]
        invoice.paid_at = datetime.now()  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def void(self, invoice_id: UUID) -> Invoice | None:
        """Void an invoice."""
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        if invoice.status == InvoiceStatus.PAID.value:
            raise ValueError("Paid invoices cannot be voided")

        invoice.status = InvoiceStatus.VOIDED.value  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(invoice)
        return invoice

    def get_progressive_billing_invoices(
        self,
        subscription_id: UUID,
        billing_period_start: datetime,
        billing_period_end: datetime,
    ) -> list[Invoice]:
        """Get all progressive billing invoices for a subscription in a billing period."""
        return (
            self.db.query(Invoice)
            .filter(
                Invoice.subscription_id == subscription_id,
                Invoice.invoice_type == InvoiceType.PROGRESSIVE_BILLING.value,
                Invoice.billing_period_start == billing_period_start,
                Invoice.billing_period_end == billing_period_end,
                Invoice.status != InvoiceStatus.VOIDED.value,
            )
            .order_by(Invoice.created_at.asc())
            .all()
        )

    def delete(self, invoice_id: UUID, organization_id: UUID | None = None) -> bool:
        """Delete a draft invoice."""
        invoice = self.get_by_id(invoice_id, organization_id)
        if not invoice:
            return False
        if invoice.status != InvoiceStatus.DRAFT.value:
            raise ValueError("Only draft invoices can be deleted")

        self.db.delete(invoice)
        self.db.commit()
        return True
