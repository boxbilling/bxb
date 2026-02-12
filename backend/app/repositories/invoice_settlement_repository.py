"""Invoice settlement repository for data access."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.invoice_settlement import InvoiceSettlement
from app.schemas.invoice_settlement import InvoiceSettlementCreate


class InvoiceSettlementRepository:
    """Repository for InvoiceSettlement model."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, data: InvoiceSettlementCreate) -> InvoiceSettlement:
        """Create a new invoice settlement."""
        settlement = InvoiceSettlement(
            invoice_id=data.invoice_id,
            settlement_type=data.settlement_type.value,
            source_id=data.source_id,
            amount_cents=data.amount_cents,
        )
        self.db.add(settlement)
        self.db.commit()
        self.db.refresh(settlement)
        return settlement

    def get_by_invoice_id(self, invoice_id: UUID) -> list[InvoiceSettlement]:
        """Get all settlements for an invoice."""
        return (
            self.db.query(InvoiceSettlement)
            .filter(InvoiceSettlement.invoice_id == invoice_id)
            .order_by(InvoiceSettlement.created_at.asc())
            .all()
        )

    def get_total_settled(self, invoice_id: UUID) -> Decimal:
        """Get the total amount settled for an invoice."""
        result = (
            self.db.query(sa_func.sum(InvoiceSettlement.amount_cents))
            .filter(InvoiceSettlement.invoice_id == invoice_id)
            .scalar()
        )
        return Decimal(str(result)) if result else Decimal("0")
