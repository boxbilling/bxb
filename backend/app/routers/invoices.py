from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_settlement import InvoiceSettlement
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.invoice_settlement_repository import InvoiceSettlementRepository
from app.schemas.invoice import InvoiceResponse, InvoiceUpdate
from app.schemas.invoice_settlement import InvoiceSettlementResponse
from app.services.wallet_service import WalletService
from app.services.webhook_service import WebhookService

router = APIRouter()


@router.get(
    "/",
    response_model=list[InvoiceResponse],
    summary="List invoices",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_invoices(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    customer_id: UUID | None = None,
    subscription_id: UUID | None = None,
    status: InvoiceStatus | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Invoice]:
    """List invoices with optional filters."""
    repo = InvoiceRepository(db)
    return repo.get_all(
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        customer_id=customer_id,
        subscription_id=subscription_id,
        status=status,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get invoice",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
    },
)
async def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Invoice:
    """Get an invoice by ID."""
    repo = InvoiceRepository(db)
    invoice = repo.get_by_id(invoice_id, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.put(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Update invoice",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
        422: {"description": "Validation error"},
    },
)
async def update_invoice(
    invoice_id: UUID,
    data: InvoiceUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Invoice:
    """Update an invoice."""
    repo = InvoiceRepository(db)
    invoice = repo.update(invoice_id, data, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post(
    "/{invoice_id}/finalize",
    response_model=InvoiceResponse,
    summary="Finalize invoice",
    responses={
        400: {"description": "Invoice cannot be finalized in current state"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
    },
)
async def finalize_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Invoice:
    """Finalize a draft invoice and apply wallet credits if available."""
    repo = InvoiceRepository(db)
    invoice = repo.get_by_id(invoice_id, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        invoice = repo.finalize(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        # Apply wallet credits after finalization
        invoice_total = Decimal(str(invoice.total))
        if invoice_total > 0:
            wallet_service = WalletService(db)
            result = wallet_service.consume_credits(
                customer_id=invoice.customer_id,  # type: ignore[arg-type]
                amount_cents=invoice_total,
                invoice_id=invoice.id,  # type: ignore[arg-type]
            )

            if result.total_consumed > 0:
                invoice.prepaid_credit_amount = result.total_consumed  # type: ignore[assignment]

                if result.remaining_amount <= 0:
                    # Wallet covers full amount — mark as paid
                    invoice.status = InvoiceStatus.PAID.value  # type: ignore[assignment]
                    from datetime import datetime

                    invoice.paid_at = datetime.now()  # type: ignore[assignment]

                db.commit()
                db.refresh(invoice)

        webhook_service = WebhookService(db)
        webhook_service.send_webhook(
            webhook_type="invoice.finalized",
            object_type="invoice",
            object_id=invoice.id,  # type: ignore[arg-type]
            payload={"invoice_id": str(invoice.id)},
        )

        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post(
    "/{invoice_id}/pay",
    response_model=InvoiceResponse,
    summary="Mark invoice paid",
    responses={
        400: {"description": "Invoice cannot be marked paid in current state"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
    },
)
async def mark_invoice_paid(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Invoice:
    """Mark an invoice as paid."""
    repo = InvoiceRepository(db)
    invoice = repo.get_by_id(invoice_id, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        invoice = repo.mark_paid(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        webhook_service = WebhookService(db)
        webhook_service.send_webhook(
            webhook_type="invoice.paid",
            object_type="invoice",
            object_id=invoice.id,  # type: ignore[arg-type]
            payload={"invoice_id": str(invoice.id)},
        )

        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post(
    "/{invoice_id}/void",
    response_model=InvoiceResponse,
    summary="Void invoice",
    responses={
        400: {"description": "Invoice cannot be voided in current state"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
    },
)
async def void_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Invoice:
    """Void an invoice."""
    repo = InvoiceRepository(db)
    invoice = repo.get_by_id(invoice_id, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        invoice = repo.void(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        webhook_service = WebhookService(db)
        webhook_service.send_webhook(
            webhook_type="invoice.voided",
            object_type="invoice",
            object_id=invoice.id,  # type: ignore[arg-type]
            payload={"invoice_id": str(invoice.id)},
        )

        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get(
    "/{invoice_id}/settlements",
    response_model=list[InvoiceSettlementResponse],
    summary="List invoice settlements",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
    },
)
async def list_invoice_settlements(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[InvoiceSettlement]:
    """List all settlements for an invoice."""
    invoice_repo = InvoiceRepository(db)
    invoice = invoice_repo.get_by_id(invoice_id, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    settlement_repo = InvoiceSettlementRepository(db)
    return settlement_repo.get_by_invoice_id(invoice_id)


@router.delete(
    "/{invoice_id}",
    status_code=204,
    summary="Delete draft invoice",
    responses={
        400: {"description": "Only draft invoices can be deleted"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
    },
)
async def delete_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a draft invoice."""
    repo = InvoiceRepository(db)
    try:
        if not repo.delete(invoice_id, organization_id):
            raise HTTPException(status_code=404, detail="Invoice not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
