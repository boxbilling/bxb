"""Customer self-service portal API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_portal_customer
from app.core.database import get_db
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.payment_method import PaymentMethod
from app.models.wallet import Wallet
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.customer import CustomerResponse, PortalProfileUpdate
from app.schemas.invoice import InvoiceResponse
from app.schemas.organization import PortalBrandingResponse
from app.schemas.payment import PaymentResponse
from app.schemas.payment_method import PaymentMethodCreate, PaymentMethodResponse
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


@router.patch(
    "/profile",
    response_model=CustomerResponse,
    summary="Update customer profile",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Customer not found"},
        422: {"description": "Validation error"},
    },
)
async def update_portal_profile(
    data: PortalProfileUpdate,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> Customer:
    """Update the authenticated customer's profile (name, email, timezone)."""
    customer_id, organization_id = portal_auth
    repo = CustomerRepository(db)
    customer = repo.get_by_id(customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.get(
    "/branding",
    response_model=PortalBrandingResponse,
    summary="Get organization branding for portal",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Organization not found"},
    },
)
async def get_portal_branding(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PortalBrandingResponse:
    """Get the organization's branding information for portal display."""
    _customer_id, organization_id = portal_auth
    repo = OrganizationRepository(db)
    org = repo.get_by_id(organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return PortalBrandingResponse(
        name=org.name,  # type: ignore[arg-type]
        logo_url=org.logo_url,  # type: ignore[arg-type]
        accent_color=org.portal_accent_color,  # type: ignore[arg-type]
        welcome_message=org.portal_welcome_message,  # type: ignore[arg-type]
    )


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


@router.get(
    "/payment_methods",
    response_model=list[PaymentMethodResponse],
    summary="List customer payment methods",
    responses={401: {"description": "Invalid or expired portal token"}},
)
async def list_portal_payment_methods(
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> list[PaymentMethod]:
    """List payment methods for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = PaymentMethodRepository(db)
    return repo.get_by_customer_id(customer_id, organization_id)


@router.post(
    "/payment_methods",
    response_model=PaymentMethodResponse,
    status_code=201,
    summary="Add a payment method",
    responses={
        401: {"description": "Invalid or expired portal token"},
        422: {"description": "Validation error"},
    },
)
async def add_portal_payment_method(
    data: PaymentMethodCreate,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PaymentMethod:
    """Add a new payment method for the authenticated customer."""
    customer_id, organization_id = portal_auth
    if data.customer_id != customer_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot add payment method for another customer",
        )
    repo = PaymentMethodRepository(db)
    return repo.create(data, organization_id)


@router.delete(
    "/payment_methods/{payment_method_id}",
    status_code=204,
    summary="Remove a payment method",
    responses={
        400: {"description": "Cannot delete default payment method"},
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Payment method not found"},
    },
)
async def remove_portal_payment_method(
    payment_method_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> None:
    """Remove a payment method. Cannot remove the default payment method."""
    customer_id, organization_id = portal_auth
    repo = PaymentMethodRepository(db)
    pm = repo.get_by_id(payment_method_id, organization_id)
    if not pm or UUID(str(pm.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Payment method not found")
    if pm.is_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the default payment method",
        )
    repo.delete(payment_method_id, organization_id)


@router.post(
    "/payment_methods/{payment_method_id}/set_default",
    response_model=PaymentMethodResponse,
    summary="Set default payment method",
    responses={
        401: {"description": "Invalid or expired portal token"},
        404: {"description": "Payment method not found"},
    },
)
async def set_portal_default_payment_method(
    payment_method_id: UUID,
    db: Session = Depends(get_db),
    portal_auth: tuple[UUID, UUID] = Depends(get_portal_customer),
) -> PaymentMethod:
    """Set a payment method as the default for the authenticated customer."""
    customer_id, organization_id = portal_auth
    repo = PaymentMethodRepository(db)
    pm = repo.get_by_id(payment_method_id, organization_id)
    if not pm or UUID(str(pm.customer_id)) != customer_id:
        raise HTTPException(status_code=404, detail="Payment method not found")
    result = repo.set_default(payment_method_id)
    if not result:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Payment method not found")
    return result
