"""CreditNote repository for data access."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.credit_note import CreditNote, CreditNoteStatus, CreditStatus
from app.schemas.credit_note import CreditNoteCreate, CreditNoteUpdate


class CreditNoteRepository:
    """Repository for CreditNote model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        customer_id: UUID | None = None,
        invoice_id: UUID | None = None,
        status: CreditNoteStatus | None = None,
        organization_id: UUID | None = None,
    ) -> list[CreditNote]:
        """Get all credit notes with optional filters."""
        query = self.db.query(CreditNote)

        if organization_id is not None:
            query = query.filter(CreditNote.organization_id == organization_id)
        if customer_id:
            query = query.filter(CreditNote.customer_id == customer_id)
        if invoice_id:
            query = query.filter(CreditNote.invoice_id == invoice_id)
        if status:
            query = query.filter(CreditNote.status == status.value)

        return query.order_by(CreditNote.created_at.desc()).offset(skip).limit(limit).all()

    def count(self, organization_id: UUID | None = None) -> int:
        """Count credit notes, optionally filtered by organization."""
        query = self.db.query(func.count(CreditNote.id))
        if organization_id is not None:
            query = query.filter(CreditNote.organization_id == organization_id)
        return query.scalar() or 0

    def get_by_id(
        self,
        credit_note_id: UUID,
        organization_id: UUID | None = None,
    ) -> CreditNote | None:
        """Get a credit note by ID."""
        query = self.db.query(CreditNote).filter(CreditNote.id == credit_note_id)
        if organization_id is not None:
            query = query.filter(CreditNote.organization_id == organization_id)
        return query.first()

    def get_by_number(self, number: str) -> CreditNote | None:
        """Get a credit note by number."""
        return self.db.query(CreditNote).filter(CreditNote.number == number).first()

    def get_by_invoice_id(self, invoice_id: UUID) -> list[CreditNote]:
        """Get all credit notes for an invoice."""
        return (
            self.db.query(CreditNote)
            .filter(CreditNote.invoice_id == invoice_id)
            .order_by(CreditNote.created_at.desc())
            .all()
        )

    def get_by_customer_id(
        self, customer_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[CreditNote]:
        """Get all credit notes for a customer."""
        return (
            self.db.query(CreditNote)
            .filter(CreditNote.customer_id == customer_id)
            .order_by(CreditNote.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_available_credit_by_customer_id(self, customer_id: UUID) -> Decimal:
        """Get total available credit balance for a customer."""
        credit_notes = (
            self.db.query(CreditNote)
            .filter(
                CreditNote.customer_id == customer_id,
                CreditNote.status == CreditNoteStatus.FINALIZED.value,
                CreditNote.credit_status == CreditStatus.AVAILABLE.value,
            )
            .all()
        )
        total = Decimal("0")
        for cn in credit_notes:
            total += Decimal(str(cn.balance_amount_cents))
        return total

    def create(self, data: CreditNoteCreate, organization_id: UUID | None = None) -> CreditNote:
        """Create a new credit note."""
        credit_note = CreditNote(
            number=data.number,
            invoice_id=data.invoice_id,
            customer_id=data.customer_id,
            credit_note_type=data.credit_note_type.value,
            reason=data.reason.value,
            description=data.description,
            credit_amount_cents=data.credit_amount_cents,
            refund_amount_cents=data.refund_amount_cents,
            total_amount_cents=data.total_amount_cents,
            taxes_amount_cents=data.taxes_amount_cents,
            currency=data.currency,
            organization_id=organization_id,
        )
        self.db.add(credit_note)
        self.db.commit()
        self.db.refresh(credit_note)
        return credit_note

    def update(self, credit_note_id: UUID, data: CreditNoteUpdate) -> CreditNote | None:
        """Update a credit note by ID (only allowed in draft status)."""
        credit_note = self.get_by_id(credit_note_id)
        if not credit_note:
            return None

        update_data = data.model_dump(exclude_unset=True)

        if "status" in update_data and update_data["status"]:
            update_data["status"] = update_data["status"].value
        if "credit_status" in update_data and update_data["credit_status"]:
            update_data["credit_status"] = update_data["credit_status"].value
        if "refund_status" in update_data and update_data["refund_status"]:
            update_data["refund_status"] = update_data["refund_status"].value
        if "reason" in update_data and update_data["reason"]:
            update_data["reason"] = update_data["reason"].value

        for key, value in update_data.items():
            setattr(credit_note, key, value)

        self.db.commit()
        self.db.refresh(credit_note)
        return credit_note

    def finalize(self, credit_note_id: UUID) -> CreditNote | None:
        """Finalize a credit note."""
        credit_note = self.get_by_id(credit_note_id)
        if not credit_note:
            return None

        credit_note.status = CreditNoteStatus.FINALIZED.value  # type: ignore[assignment]
        credit_note.issued_at = datetime.now()  # type: ignore[assignment]
        credit_note.balance_amount_cents = credit_note.credit_amount_cents
        credit_note.credit_status = CreditStatus.AVAILABLE.value  # type: ignore[assignment]

        self.db.commit()
        self.db.refresh(credit_note)
        return credit_note

    def void(self, credit_note_id: UUID) -> CreditNote | None:
        """Void a credit note."""
        credit_note = self.get_by_id(credit_note_id)
        if not credit_note:
            return None

        credit_note.credit_status = CreditStatus.VOIDED.value  # type: ignore[assignment]
        credit_note.voided_at = datetime.now()  # type: ignore[assignment]
        credit_note.balance_amount_cents = Decimal("0")  # type: ignore[assignment]

        self.db.commit()
        self.db.refresh(credit_note)
        return credit_note

    def consume_credit(self, credit_note_id: UUID, amount: Decimal) -> CreditNote | None:
        """Consume credit from a credit note's balance."""
        credit_note = self.get_by_id(credit_note_id)
        if not credit_note:
            return None

        current_balance = Decimal(str(credit_note.balance_amount_cents))
        new_balance = current_balance - amount
        if new_balance < 0:
            new_balance = Decimal("0")

        credit_note.balance_amount_cents = new_balance  # type: ignore[assignment]

        if new_balance == 0:
            credit_note.credit_status = CreditStatus.CONSUMED.value  # type: ignore[assignment]

        self.db.commit()
        self.db.refresh(credit_note)
        return credit_note

    def delete(self, credit_note_id: UUID, organization_id: UUID | None = None) -> bool:
        """Delete a credit note by ID."""
        credit_note = self.get_by_id(credit_note_id, organization_id=organization_id)
        if not credit_note:
            return False

        self.db.delete(credit_note)
        self.db.commit()
        return True
