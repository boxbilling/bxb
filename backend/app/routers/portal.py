"""Customer self-service portal API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_portal_customer
from app.core.database import get_db
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.wallet import Wallet
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.customer import CustomerResponse
from app.schemas.invoice import InvoiceResponse
from app.schemas.payment import PaymentResponse
from app.schemas.usage import CurrentUsageResponse
from app.schemas.wallet import WalletResponse
from app.services.pdf_service import PdfService
from app.services.usage_query_service import UsageQueryService

router = APIRouter()


@router.get(
    "/customer",
    response_model=CustomerResponse,
    summary="Get customer profile",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Customer not found"},
    },
)
async def get_portal_customer_profile(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> Customer:
    """Get the authenticated customer's profile information."""
    customer_id, organization_id = portal_auth
    repo = CustomerRepository(db)
    customer = repo.get_by_id(customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get(
    "/invoices",
    response_model=list[InvoiceResponse],
    summary="List customer invoices",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_invoices(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[Invoice]:
    """List invoices for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = InvoiceRepository(db)
    return repo.get_all(
        organization_id=organization_id,
        customer_id=customer_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get invoice detail",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Invoice not found"},
    },
)
async def get_portal_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> Invoice:
    """Get a specific invoice for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = InvoiceRepository(db)
    invoice = repo.get_by_id(invoice_id, organization_id)
    if not invoice or UUID(str(invoice.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get(
    "/invoices/{invoice_id}/download_pdf",
    summary="Download invoice PDF",
    responses={
        400: {"description": "Invoice must be finalized or paid to generate PDF"},
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Invoice not found"},
    },
)
async def download_portal_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> Response:
    """Download a PDF for a finalized or paid invoice."""
    customer_id, organization_id = portal_auth
    invoice_repo = InvoiceRepository(db)
    invoice = invoice_repo.get_by_id(invoice_id, organization_id)
    if not invoice or UUID(str(invoice.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status not in (InvoiceStatus.FINALIZED.value, InvoiceStatus.PAID.value):
        raise HTTPException(
            status_code=400,
            detail="Invoice must be finalized or paid to generate PDF",
        )

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(customer_id)

    org_repo = OrganizationRepository(db)
    organization = org_repo.get_by_id(organization_id)

    fee_repo = FeeRepository(db)
    fees = fee_repo.get_by_invoice_id(invoice_id)

    pdf_service = PdfService()
    pdf_bytes = pdf_service.generate_invoice_pdf(
        invoice=invoice,
        fees=fees,
        customer=customer,  # type: ignore[arg-type]
        organization=organization,  # type: ignore[arg-type]
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        },
    )


@router.get(
    "/current_usage",
    response_model=CurrentUsageResponse,
    summary="Get current usage",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Subscription not found"},
    },
)
async def get_portal_current_usage(
    subscription_id: UUID = Query(...),
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> CurrentUsageResponse:
    """Get current usage for the authenticated customer's subscription."""
    customer_id, organization_id = portal_auth

    from app.repositories.subscription_repository import SubscriptionRepository

    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(subscription_id, organization_id)
    if not subscription or UUID(str(subscription.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(customer_id)
    if not customer:  # pragma: no cover – FK guarantees existence
        raise HTTPException(status_code=404, detail="Customer not found")

    service = UsageQueryService(db)
    return service.get_current_usage(
        subscription_id=subscription_id,
        external_customer_id=str(customer.external_id),
    )


@router.get(
    "/payments",
    response_model=list[PaymentResponse],
    summary="List customer payments",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_payments(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[Payment]:
    """List payments for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = PaymentRepository(db)
    return repo.get_all(
        organization_id=organization_id,
        customer_id=customer_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/wallet",
    response_model=list[WalletResponse],
    summary="Get wallet balance and transactions",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def get_portal_wallet(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[Wallet]:
    """Get wallet balance and recent transactions for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = WalletRepository(db)
    return repo.get_all(
        organization_id=organization_id,
        customer_id=customer_id,
    )
