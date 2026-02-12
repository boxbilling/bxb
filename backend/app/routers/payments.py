"""Payment API endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.invoice import InvoiceStatus
from app.models.invoice_settlement import SettlementType
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.invoice_settlement_repository import InvoiceSettlementRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.invoice_settlement import InvoiceSettlementCreate
from app.schemas.payment import (
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    PaymentResponse,
)
from app.services.payment_provider import get_payment_provider
from app.services.webhook_service import WebhookService


def _record_settlement_and_maybe_mark_paid(
    db: Session,
    invoice_id: UUID,
    settlement_type: SettlementType,
    source_id: UUID,
    amount_cents: float | int,
) -> None:
    """Record a settlement and auto-mark invoice as paid if fully settled."""
    from decimal import Decimal

    settlement_repo = InvoiceSettlementRepository(db)
    settlement_repo.create(
        InvoiceSettlementCreate(
            invoice_id=invoice_id,
            settlement_type=settlement_type,
            source_id=source_id,
            amount_cents=Decimal(str(amount_cents)),
        )
    )

    invoice_repo = InvoiceRepository(db)
    invoice = invoice_repo.get_by_id(invoice_id)
    if invoice and invoice.status == InvoiceStatus.FINALIZED.value:
        total_settled = settlement_repo.get_total_settled(invoice_id)
        if total_settled >= Decimal(str(invoice.total)):
            invoice_repo.mark_paid(invoice_id)

router = APIRouter()


@router.get("/", response_model=list[PaymentResponse])
async def list_payments(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    invoice_id: UUID | None = None,
    customer_id: UUID | None = None,
    status: PaymentStatus | None = None,
    provider: PaymentProvider | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Payment]:
    """List payments with optional filters."""
    repo = PaymentRepository(db)
    return repo.get_all(
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        invoice_id=invoice_id,
        customer_id=customer_id,
        status=status,
        provider=provider,
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Payment:
    """Get a payment by ID."""
    repo = PaymentRepository(db)
    payment = repo.get_by_id(payment_id, organization_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    data: CheckoutSessionCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CheckoutSessionResponse:
    """Create a checkout session for an invoice.

    This creates a payment record and returns a URL where the customer
    can complete the payment.
    """
    # Get the invoice
    invoice_repo = InvoiceRepository(db)
    invoice = invoice_repo.get_by_id(data.invoice_id, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Only finalized invoices can be paid
    if invoice.status != InvoiceStatus.FINALIZED.value:
        raise HTTPException(
            status_code=400,
            detail="Only finalized invoices can be paid",
        )

    # Check if there's already a pending payment for this invoice
    payment_repo = PaymentRepository(db)
    existing_payments = payment_repo.get_all(
        invoice_id=data.invoice_id,
        status=PaymentStatus.PENDING,
    )
    if existing_payments:
        # Return existing checkout URL if available
        existing = existing_payments[0]
        if existing.provider_checkout_url:
            return CheckoutSessionResponse(
                payment_id=existing.id,  # type: ignore[arg-type]
                checkout_url=existing.provider_checkout_url,  # type: ignore[arg-type]
                provider=existing.provider,  # type: ignore[arg-type]
                expires_at=None,
            )

    # Get customer email for checkout
    customer_email: str | None = None
    from app.repositories.customer_repository import CustomerRepository

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(invoice.customer_id)  # type: ignore[arg-type]
    if customer:
        customer_email = customer.email  # type: ignore[assignment]

    # Create payment record
    payment = payment_repo.create(
        invoice_id=invoice.id,  # type: ignore[arg-type]
        customer_id=invoice.customer_id,  # type: ignore[arg-type]
        amount=float(invoice.total),
        currency=invoice.currency,  # type: ignore[arg-type]
        provider=data.provider,
    )

    # Create checkout session with payment provider
    provider_svc = get_payment_provider(data.provider)
    try:
        session = provider_svc.create_checkout_session(
            payment_id=payment.id,  # type: ignore[arg-type]
            amount=invoice.total,  # type: ignore[arg-type]
            currency=invoice.currency,  # type: ignore[arg-type]
            customer_email=customer_email,
            invoice_number=invoice.invoice_number,  # type: ignore[arg-type]
            success_url=data.success_url,
            cancel_url=data.cancel_url,
            metadata={"invoice_id": str(invoice.id)},
        )
    except ImportError:
        # Stripe not installed - use mock for testing
        raise HTTPException(
            status_code=503,
            detail="Payment provider not configured",
        ) from None
    except Exception as e:
        # Clean up the payment record on failure
        payment_repo.delete(payment.id)  # type: ignore[arg-type]
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create checkout session: {e!s}",
        ) from None

    # Update payment with provider IDs
    payment_repo.set_provider_ids(
        payment_id=payment.id,  # type: ignore[arg-type]
        provider_checkout_id=session.provider_checkout_id,
        provider_checkout_url=session.checkout_url,
    )

    return CheckoutSessionResponse(
        payment_id=payment.id,  # type: ignore[arg-type]
        checkout_url=session.checkout_url,
        provider=data.provider.value,
        expires_at=session.expires_at,
    )


@router.post("/webhook/{provider}")
async def handle_webhook(
    provider: PaymentProvider,
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    ucp_signature: str | None = Header(None, alias="X-UCP-Signature"),
    gc_signature: str | None = Header(None, alias="Webhook-Signature"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Handle payment provider webhooks.

    This endpoint receives webhook events from payment providers
    and updates payment/invoice status accordingly.
    """
    payload = await request.body()

    # Get the appropriate provider
    try:
        payment_provider = get_payment_provider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid provider") from None

    # Verify signature - check provider-specific headers first
    signature = (
        stripe_signature
        or ucp_signature
        or gc_signature
        or request.headers.get("X-Webhook-Signature", "")
    )
    if not payment_provider.verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse the webhook
    try:
        payload_json = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None

    result = payment_provider.parse_webhook(payload_json)

    # Find the payment - try multiple lookup methods
    payment_repo = PaymentRepository(db)
    payment: Payment | None = None

    if result.provider_checkout_id:
        payment = payment_repo.get_by_provider_checkout_id(result.provider_checkout_id)
    if not payment and result.provider_payment_id:
        payment = payment_repo.get_by_provider_payment_id(result.provider_payment_id)
    if not payment and result.metadata and result.metadata.get("payment_id"):
        payment = payment_repo.get_by_id(UUID(result.metadata["payment_id"]))

    if not payment:
        # Payment not found - might be for a different system
        return {"status": "ignored", "reason": "payment not found"}

    # Update provider payment ID if we have it
    if result.provider_payment_id and not payment.provider_payment_id:
        payment_repo.set_provider_ids(
            payment_id=payment.id,  # type: ignore[arg-type]
            provider_payment_id=result.provider_payment_id,
        )

    # Update payment status
    webhook_service = WebhookService(db)
    if result.status == "succeeded":
        payment_repo.mark_succeeded(payment.id)  # type: ignore[arg-type]

        # Record settlement and auto-mark invoice as paid if fully settled
        _record_settlement_and_maybe_mark_paid(
            db,
            invoice_id=payment.invoice_id,  # type: ignore[arg-type]
            settlement_type=SettlementType.PAYMENT,
            source_id=payment.id,  # type: ignore[arg-type]
            amount_cents=float(payment.amount),
        )

        webhook_service.send_webhook(
            webhook_type="payment.succeeded",
            object_type="payment",
            object_id=payment.id,  # type: ignore[arg-type]
            payload={"payment_id": str(payment.id)},
        )

    elif result.status == "failed":
        payment_repo.mark_failed(payment.id, result.failure_reason)  # type: ignore[arg-type]

        webhook_service.send_webhook(
            webhook_type="payment.failed",
            object_type="payment",
            object_id=payment.id,  # type: ignore[arg-type]
            payload={"payment_id": str(payment.id)},
        )

    elif result.status == "canceled":
        payment_repo.mark_canceled(payment.id)  # type: ignore[arg-type]

    return {"status": "processed", "event_type": result.event_type}


@router.post("/{payment_id}/mark-paid", response_model=PaymentResponse)
async def mark_payment_paid(
    payment_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Payment:
    """Manually mark a payment as paid (for manual/offline payments)."""
    payment_repo = PaymentRepository(db)
    payment = payment_repo.get_by_id(payment_id, organization_id)

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != PaymentStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail="Only pending payments can be marked as paid",
        )

    # Mark payment as succeeded
    updated_payment = payment_repo.mark_succeeded(payment_id)
    if not updated_payment:  # pragma: no cover - race condition
        raise HTTPException(status_code=404, detail="Payment not found")

    # Record settlement and auto-mark invoice as paid if fully settled
    _record_settlement_and_maybe_mark_paid(
        db,
        invoice_id=payment.invoice_id,  # type: ignore[arg-type]
        settlement_type=SettlementType.PAYMENT,
        source_id=payment_id,
        amount_cents=float(payment.amount),
    )

    webhook_service = WebhookService(db)
    webhook_service.send_webhook(
        webhook_type="payment.succeeded",
        object_type="payment",
        object_id=payment_id,
        payload={"payment_id": str(payment_id)},
    )

    return updated_payment


@router.post("/{payment_id}/refund", response_model=PaymentResponse)
async def refund_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Payment:
    """Refund a succeeded payment."""
    payment_repo = PaymentRepository(db)
    payment = payment_repo.get_by_id(payment_id, organization_id)

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    try:
        updated_payment = payment_repo.mark_refunded(payment_id)
        if not updated_payment:  # pragma: no cover - race condition
            raise HTTPException(status_code=404, detail="Payment not found")
        return updated_payment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.delete("/{payment_id}", status_code=204)
async def delete_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a pending payment."""
    payment_repo = PaymentRepository(db)

    try:
        if not payment_repo.delete(payment_id, organization_id):
            raise HTTPException(status_code=404, detail="Payment not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
