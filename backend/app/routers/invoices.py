from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas.invoice import InvoiceResponse, InvoiceUpdate

router = APIRouter()


@router.get("/", response_model=list[InvoiceResponse])
async def list_invoices(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    customer_id: UUID | None = None,
    subscription_id: UUID | None = None,
    status: InvoiceStatus | None = None,
    db: Session = Depends(get_db),
) -> list[Invoice]:
    """List invoices with optional filters."""
    repo = InvoiceRepository(db)
    return repo.get_all(
        skip=skip,
        limit=limit,
        customer_id=customer_id,
        subscription_id=subscription_id,
        status=status,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
) -> Invoice:
    """Get an invoice by ID."""
    repo = InvoiceRepository(db)
    invoice = repo.get_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.put("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: UUID,
    data: InvoiceUpdate,
    db: Session = Depends(get_db),
) -> Invoice:
    """Update an invoice."""
    repo = InvoiceRepository(db)
    invoice = repo.update(invoice_id, data)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post("/{invoice_id}/finalize", response_model=InvoiceResponse)
async def finalize_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
) -> Invoice:
    """Finalize a draft invoice."""
    repo = InvoiceRepository(db)
    try:
        invoice = repo.finalize(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/{invoice_id}/pay", response_model=InvoiceResponse)
async def mark_invoice_paid(
    invoice_id: UUID,
    db: Session = Depends(get_db),
) -> Invoice:
    """Mark an invoice as paid."""
    repo = InvoiceRepository(db)
    try:
        invoice = repo.mark_paid(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/{invoice_id}/void", response_model=InvoiceResponse)
async def void_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
) -> Invoice:
    """Void an invoice."""
    repo = InvoiceRepository(db)
    try:
        invoice = repo.void(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete("/{invoice_id}", status_code=204)
async def delete_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a draft invoice."""
    repo = InvoiceRepository(db)
    try:
        if not repo.delete(invoice_id):
            raise HTTPException(status_code=404, detail="Invoice not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
