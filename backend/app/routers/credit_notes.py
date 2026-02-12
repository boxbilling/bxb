"""CreditNote API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.credit_note import CreditNote, CreditNoteStatus
from app.repositories.credit_note_item_repository import CreditNoteItemRepository
from app.repositories.credit_note_repository import CreditNoteRepository
from app.schemas.credit_note import (
    CreditNoteCreate,
    CreditNoteResponse,
    CreditNoteUpdate,
)

router = APIRouter()


@router.post("/", response_model=CreditNoteResponse, status_code=201)
async def create_credit_note(
    data: CreditNoteCreate,
    db: Session = Depends(get_db),
) -> CreditNote:
    """Create a new credit note with optional items."""
    repo = CreditNoteRepository(db)
    if repo.get_by_number(data.number):
        raise HTTPException(
            status_code=409, detail="Credit note with this number already exists"
        )

    credit_note = repo.create(data)

    if data.items:
        item_repo = CreditNoteItemRepository(db)
        items_data = [
            {
                "credit_note_id": credit_note.id,
                "fee_id": item.fee_id,
                "amount_cents": item.amount_cents,
            }
            for item in data.items
        ]
        item_repo.create_bulk(items_data)

    return credit_note


@router.get("/", response_model=list[CreditNoteResponse])
async def list_credit_notes(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    customer_id: UUID | None = None,
    invoice_id: UUID | None = None,
    status: CreditNoteStatus | None = None,
    db: Session = Depends(get_db),
) -> list[CreditNote]:
    """List credit notes with optional filters."""
    repo = CreditNoteRepository(db)
    return repo.get_all(
        skip=skip,
        limit=limit,
        customer_id=customer_id,
        invoice_id=invoice_id,
        status=status,
    )


@router.get("/{credit_note_id}", response_model=CreditNoteResponse)
async def get_credit_note(
    credit_note_id: UUID,
    db: Session = Depends(get_db),
) -> CreditNote:
    """Get a credit note by ID."""
    repo = CreditNoteRepository(db)
    credit_note = repo.get_by_id(credit_note_id)
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")
    return credit_note


@router.put("/{credit_note_id}", response_model=CreditNoteResponse)
async def update_credit_note(
    credit_note_id: UUID,
    data: CreditNoteUpdate,
    db: Session = Depends(get_db),
) -> CreditNote:
    """Update a credit note (only allowed in draft status)."""
    repo = CreditNoteRepository(db)
    credit_note = repo.get_by_id(credit_note_id)
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if credit_note.status != CreditNoteStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail="Only draft credit notes can be updated")

    updated = repo.update(credit_note_id, data)
    return updated  # type: ignore[return-value]


@router.post("/{credit_note_id}/finalize", response_model=CreditNoteResponse)
async def finalize_credit_note(
    credit_note_id: UUID,
    db: Session = Depends(get_db),
) -> CreditNote:
    """Finalize a credit note."""
    repo = CreditNoteRepository(db)
    credit_note = repo.get_by_id(credit_note_id)
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if credit_note.status != CreditNoteStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail="Only draft credit notes can be finalized")

    finalized = repo.finalize(credit_note_id)
    return finalized  # type: ignore[return-value]


@router.post("/{credit_note_id}/void", response_model=CreditNoteResponse)
async def void_credit_note(
    credit_note_id: UUID,
    db: Session = Depends(get_db),
) -> CreditNote:
    """Void a credit note."""
    repo = CreditNoteRepository(db)
    credit_note = repo.get_by_id(credit_note_id)
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if credit_note.status != CreditNoteStatus.FINALIZED.value:
        raise HTTPException(
            status_code=400, detail="Only finalized credit notes can be voided"
        )

    voided = repo.void(credit_note_id)
    return voided  # type: ignore[return-value]
