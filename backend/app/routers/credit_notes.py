"""CreditNote API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.credit_note import CreditNote, CreditNoteStatus
from app.repositories.credit_note_item_repository import CreditNoteItemRepository
from app.repositories.credit_note_repository import CreditNoteRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.credit_note import (
    CreditNoteCreate,
    CreditNoteResponse,
    CreditNoteUpdate,
)
from app.services.pdf_service import PdfService

router = APIRouter()


@router.post(
    "/",
    response_model=CreditNoteResponse,
    status_code=201,
    summary="Create credit note",
    responses={
        401: {"description": "Unauthorized"},
        409: {"description": "Credit note with this number already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_credit_note(
    data: CreditNoteCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CreditNote:
    """Create a new credit note with optional items."""
    repo = CreditNoteRepository(db)
    if repo.get_by_number(data.number):
        raise HTTPException(status_code=409, detail="Credit note with this number already exists")

    credit_note = repo.create(data, organization_id)

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


@router.get(
    "/",
    response_model=list[CreditNoteResponse],
    summary="List credit notes",
    responses={401: {"description": "Unauthorized"}},
)
async def list_credit_notes(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    customer_id: UUID | None = None,
    invoice_id: UUID | None = None,
    status: CreditNoteStatus | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[CreditNote]:
    """List credit notes with optional filters."""
    repo = CreditNoteRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        customer_id=customer_id,
        invoice_id=invoice_id,
        status=status,
    )


@router.get(
    "/{credit_note_id}",
    response_model=CreditNoteResponse,
    summary="Get credit note",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Credit note not found"},
    },
)
async def get_credit_note(
    credit_note_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CreditNote:
    """Get a credit note by ID."""
    repo = CreditNoteRepository(db)
    credit_note = repo.get_by_id(credit_note_id, organization_id)
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")
    return credit_note


@router.put(
    "/{credit_note_id}",
    response_model=CreditNoteResponse,
    summary="Update credit note",
    responses={
        400: {"description": "Only draft credit notes can be updated"},
        401: {"description": "Unauthorized"},
        404: {"description": "Credit note not found"},
        422: {"description": "Validation error"},
    },
)
async def update_credit_note(
    credit_note_id: UUID,
    data: CreditNoteUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CreditNote:
    """Update a credit note (only allowed in draft status)."""
    repo = CreditNoteRepository(db)
    credit_note = repo.get_by_id(credit_note_id, organization_id)
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if credit_note.status != CreditNoteStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail="Only draft credit notes can be updated")

    updated = repo.update(credit_note_id, data)
    return updated  # type: ignore[return-value]


@router.post(
    "/{credit_note_id}/finalize",
    response_model=CreditNoteResponse,
    summary="Finalize credit note",
    responses={
        400: {"description": "Only draft credit notes can be finalized"},
        401: {"description": "Unauthorized"},
        404: {"description": "Credit note not found"},
    },
)
async def finalize_credit_note(
    credit_note_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CreditNote:
    """Finalize a credit note."""
    repo = CreditNoteRepository(db)
    credit_note = repo.get_by_id(credit_note_id, organization_id)
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if credit_note.status != CreditNoteStatus.DRAFT.value:
        raise HTTPException(status_code=400, detail="Only draft credit notes can be finalized")

    finalized = repo.finalize(credit_note_id)
    return finalized  # type: ignore[return-value]


@router.post(
    "/{credit_note_id}/void",
    response_model=CreditNoteResponse,
    summary="Void credit note",
    responses={
        400: {"description": "Only finalized credit notes can be voided"},
        401: {"description": "Unauthorized"},
        404: {"description": "Credit note not found"},
    },
)
async def void_credit_note(
    credit_note_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CreditNote:
    """Void a credit note."""
    repo = CreditNoteRepository(db)
    credit_note = repo.get_by_id(credit_note_id, organization_id)
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if credit_note.status != CreditNoteStatus.FINALIZED.value:
        raise HTTPException(status_code=400, detail="Only finalized credit notes can be voided")

    voided = repo.void(credit_note_id)
    return voided  # type: ignore[return-value]


@router.post(
    "/{credit_note_id}/download_pdf",
    summary="Download credit note PDF",
    responses={
        400: {"description": "Credit note must be finalized to generate PDF"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Credit note not found"},
    },
)
async def download_credit_note_pdf(
    credit_note_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Response:
    """Generate and download a PDF for a finalized credit note."""
    repo = CreditNoteRepository(db)
    credit_note = repo.get_by_id(credit_note_id, organization_id)
    if not credit_note:
        raise HTTPException(status_code=404, detail="Credit note not found")

    if credit_note.status != CreditNoteStatus.FINALIZED.value:
        raise HTTPException(
            status_code=400,
            detail="Credit note must be finalized to generate PDF",
        )

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(credit_note.customer_id)  # type: ignore[arg-type]

    org_repo = OrganizationRepository(db)
    organization = org_repo.get_by_id(organization_id)

    item_repo = CreditNoteItemRepository(db)
    items = item_repo.get_by_credit_note_id(credit_note_id)

    pdf_service = PdfService()
    pdf_bytes = pdf_service.generate_credit_note_pdf(
        credit_note=credit_note,
        items=items,
        customer=customer,  # type: ignore[arg-type]
        organization=organization,  # type: ignore[arg-type]
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="credit_note_{credit_note.number}.pdf"'
        },
    )
