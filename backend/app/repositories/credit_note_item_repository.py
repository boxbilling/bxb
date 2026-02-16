"""CreditNoteItem repository for data access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.credit_note_item import CreditNoteItem


class CreditNoteItemRepository:
    """Repository for CreditNoteItem model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        credit_note_id: UUID | None = None,
        order_by: str | None = None,
    ) -> list[CreditNoteItem]:
        """Get all credit note items with optional filters."""
        query = self.db.query(CreditNoteItem)

        if credit_note_id:
            query = query.filter(CreditNoteItem.credit_note_id == credit_note_id)

        query = apply_order_by(query, CreditNoteItem, order_by)
        return query.offset(skip).limit(limit).all()

    def get_by_id(self, item_id: UUID) -> CreditNoteItem | None:
        """Get a credit note item by ID."""
        return self.db.query(CreditNoteItem).filter(CreditNoteItem.id == item_id).first()

    def get_by_credit_note_id(self, credit_note_id: UUID) -> list[CreditNoteItem]:
        """Get all items for a credit note."""
        return (
            self.db.query(CreditNoteItem)
            .filter(CreditNoteItem.credit_note_id == credit_note_id)
            .order_by(CreditNoteItem.created_at.asc())
            .all()
        )

    def create(
        self,
        credit_note_id: UUID,
        fee_id: UUID,
        amount_cents: float,
    ) -> CreditNoteItem:
        """Create a new credit note item."""
        item = CreditNoteItem(
            credit_note_id=credit_note_id,
            fee_id=fee_id,
            amount_cents=amount_cents,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def create_bulk(
        self,
        items_data: list[dict[str, object]],
    ) -> list[CreditNoteItem]:
        """Create multiple credit note items at once."""
        items = []
        for data in items_data:
            item = CreditNoteItem(
                credit_note_id=data["credit_note_id"],
                fee_id=data["fee_id"],
                amount_cents=data["amount_cents"],
            )
            self.db.add(item)
            items.append(item)

        self.db.commit()
        for item in items:
            self.db.refresh(item)
        return items

    def delete(self, item_id: UUID) -> bool:
        """Delete a credit note item by ID."""
        item = self.get_by_id(item_id)
        if not item:
            return False

        self.db.delete(item)
        self.db.commit()
        return True
