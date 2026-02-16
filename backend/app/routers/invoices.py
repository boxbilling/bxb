from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.core.idempotency import IdempotencyResult, check_idempotency, record_idempotency_response
from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
from app.models.invoice_settlement import InvoiceSettlement
from app.models.payment import PaymentProvider
from app.repositories.customer_repository import CustomerRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.invoice_settlement_repository import InvoiceSettlementRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.invoice import (
    BulkFinalizeRequest,
    BulkFinalizeResponse,
    BulkFinalizeResult,
    BulkVoidRequest,
    BulkVoidResponse,
    BulkVoidResult,
    InvoiceResponse,
    InvoiceUpdate,
    OneOffInvoiceCreate,
    SendReminderResponse,
)
from app.schemas.invoice_preview import InvoicePreviewRequest, InvoicePreviewResponse
from app.schemas.invoice_settlement import InvoiceSettlementResponse
from app.services.audit_service import AuditService
from app.services.email_service import EmailService
from app.services.invoice_preview_service import InvoicePreviewService
from app.services.payment_provider import get_payment_provider
from app.services.pdf_service import PdfService
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
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    order_by: str | None = Query(default=None),
    customer_id: UUID | None = None,
    subscription_id: UUID | None = None,
    status: InvoiceStatus | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Invoice]:
    """List invoices with optional filters."""
    repo = InvoiceRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        order_by=order_by,
        customer_id=customer_id,
        subscription_id=subscription_id,
        status=status,
    )


@router.post(
    "/one_off",
    response_model=InvoiceResponse,
    summary="Create a one-off invoice",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer not found"},
        422: {"description": "Validation error"},
    },
)
async def create_one_off_invoice(
    data: OneOffInvoiceCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Invoice:
    """Create a one-off invoice with custom line items (not tied to a subscription)."""
    from datetime import datetime

    from app.schemas.invoice import InvoiceCreate

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(data.customer_id)
    if not customer or customer.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    now = datetime.now()
    invoice_data = InvoiceCreate(
        customer_id=data.customer_id,
        billing_entity_id=data.billing_entity_id,
        billing_period_start=now,
        billing_period_end=now,
        invoice_type=InvoiceType.ONE_OFF,
        currency=data.currency,
        line_items=data.line_items,
        due_date=data.due_date,
    )

    repo = InvoiceRepository(db)
    invoice = repo.create(invoice_data, organization_id)

    audit_service = AuditService(db)
    audit_service.log_status_change(
        resource_type="invoice",
        resource_id=invoice.id,  # type: ignore[arg-type]
        organization_id=organization_id,
        old_status="",
        new_status="draft",
        actor_type="api_key",
    )

    return invoice


@router.post(
    "/bulk_finalize",
    response_model=BulkFinalizeResponse,
    summary="Bulk finalize draft invoices",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
    },
)
async def bulk_finalize_invoices(
    data: BulkFinalizeRequest,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> BulkFinalizeResponse:
    """Finalize multiple draft invoices in one request."""
    repo = InvoiceRepository(db)
    audit_service = AuditService(db)
    results: list[BulkFinalizeResult] = []
    finalized_count = 0
    failed_count = 0

    for invoice_id in data.invoice_ids:
        invoice = repo.get_by_id(invoice_id, organization_id)
        if not invoice:
            results.append(BulkFinalizeResult(
                invoice_id=invoice_id, success=False, error="Invoice not found"
            ))
            failed_count += 1
            continue

        try:
            finalized = repo.finalize(invoice_id)
            if not finalized:
                results.append(BulkFinalizeResult(
                    invoice_id=invoice_id, success=False, error="Failed to finalize"
                ))
                failed_count += 1
                continue

            audit_service.log_status_change(
                resource_type="invoice",
                resource_id=invoice_id,
                organization_id=organization_id,
                old_status="draft",
                new_status="finalized",
                actor_type="api_key",
            )

            results.append(BulkFinalizeResult(invoice_id=invoice_id, success=True))
            finalized_count += 1
        except ValueError as e:
            results.append(BulkFinalizeResult(
                invoice_id=invoice_id, success=False, error=str(e)
            ))
            failed_count += 1

    return BulkFinalizeResponse(
        results=results,
        finalized_count=finalized_count,
        failed_count=failed_count,
    )


@router.post(
    "/bulk_void",
    response_model=BulkVoidResponse,
    summary="Bulk void invoices",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
    },
)
async def bulk_void_invoices(
    data: BulkVoidRequest,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> BulkVoidResponse:
    """Void multiple invoices in one request."""
    repo = InvoiceRepository(db)
    audit_service = AuditService(db)
    webhook_service = WebhookService(db)
    results: list[BulkVoidResult] = []
    voided_count = 0
    failed_count = 0

    for invoice_id in data.invoice_ids:
        invoice = repo.get_by_id(invoice_id, organization_id)
        if not invoice:
            results.append(BulkVoidResult(
                invoice_id=invoice_id, success=False, error="Invoice not found"
            ))
            failed_count += 1
            continue

        try:
            old_status = str(invoice.status)
            voided = repo.void(invoice_id)
            if not voided:
                results.append(BulkVoidResult(
                    invoice_id=invoice_id, success=False, error="Failed to void"
                ))
                failed_count += 1
                continue

            audit_service.log_status_change(
                resource_type="invoice",
                resource_id=invoice_id,
                organization_id=organization_id,
                old_status=old_status,
                new_status="voided",
                actor_type="api_key",
            )

            webhook_service.send_webhook(
                webhook_type="invoice.voided",
                object_type="invoice",
                object_id=invoice_id,
                payload={"invoice_id": str(invoice_id)},
            )

            results.append(BulkVoidResult(invoice_id=invoice_id, success=True))
            voided_count += 1
        except ValueError as e:
            results.append(BulkVoidResult(
                invoice_id=invoice_id, success=False, error=str(e)
            ))
            failed_count += 1

    return BulkVoidResponse(
        results=results,
        voided_count=voided_count,
        failed_count=failed_count,
    )


@router.post(
    "/preview",
    response_model=InvoicePreviewResponse,
    summary="Preview invoice",
    responses={
        400: {"description": "Subscription not found or not active"},
        401: {"description": "Unauthorized – invalid or missing API key"},
    },
)
async def preview_invoice(
    data: InvoicePreviewRequest,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> InvoicePreviewResponse:
    """Preview an invoice for a subscription without persisting anything."""
    from app.repositories.subscription_repository import SubscriptionRepository

    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(data.subscription_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(subscription.customer_id)  # type: ignore[arg-type]
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    service = InvoicePreviewService(db)
    try:
        return service.preview_invoice(
            subscription_id=data.subscription_id,
            external_customer_id=str(customer.external_id),
            billing_period_start=data.billing_period_start,
            billing_period_end=data.billing_period_end,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


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
    request: Request,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Invoice | JSONResponse:
    """Finalize a draft invoice and apply wallet credits if available."""
    idempotency = check_idempotency(request, db, organization_id)
    if isinstance(idempotency, JSONResponse):
        return idempotency

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

        # Auto-charge using default payment method if invoice still not paid
        if invoice.status == InvoiceStatus.FINALIZED.value:
            remaining = Decimal(str(invoice.total)) - Decimal(
                str(invoice.prepaid_credit_amount)
            )
            if remaining > 0:
                pm_repo = PaymentMethodRepository(db)
                default_pm = pm_repo.get_default(
                    customer_id=invoice.customer_id,  # type: ignore[arg-type]
                    organization_id=organization_id,
                )
                if default_pm:
                    payment_repo = PaymentRepository(db)
                    provider_enum = PaymentProvider(default_pm.provider)
                    payment = payment_repo.create(
                        invoice_id=invoice.id,  # type: ignore[arg-type]
                        customer_id=invoice.customer_id,  # type: ignore[arg-type]
                        amount=float(remaining),
                        currency=str(invoice.currency),
                        provider=provider_enum,
                        organization_id=organization_id,
                    )
                    payment_repo.mark_processing(payment.id)  # type: ignore[arg-type]

                    provider = get_payment_provider(provider_enum)
                    charge_result = provider.charge_payment_method(
                        payment_method_id=str(
                            default_pm.provider_payment_method_id
                        ),
                        amount=remaining,
                        currency=str(invoice.currency),
                        metadata={"invoice_id": str(invoice.id)},
                    )

                    payment_repo.set_provider_ids(
                        payment.id,  # type: ignore[arg-type]
                        provider_payment_id=charge_result.provider_payment_id,
                    )

                    if charge_result.status == "succeeded":
                        payment_repo.mark_succeeded(payment.id)  # type: ignore[arg-type]
                        paid = repo.mark_paid(invoice.id)  # type: ignore[arg-type]
                        if paid:
                            invoice = paid
                    else:
                        payment_repo.mark_failed(
                            payment.id,  # type: ignore[arg-type]
                            reason=charge_result.failure_reason,
                        )

        audit_service = AuditService(db)
        audit_service.log_status_change(
            resource_type="invoice",
            resource_id=invoice.id,  # type: ignore[arg-type]
            organization_id=organization_id,
            old_status="draft",
            new_status=str(invoice.status),
            actor_type="api_key",
        )

        webhook_service = WebhookService(db)
        webhook_service.send_webhook(
            webhook_type="invoice.finalized",
            object_type="invoice",
            object_id=invoice.id,  # type: ignore[arg-type]
            payload={"invoice_id": str(invoice.id)},
        )

        if isinstance(idempotency, IdempotencyResult):
            body = InvoiceResponse.model_validate(invoice).model_dump(mode="json")
            record_idempotency_response(db, organization_id, idempotency.key, 200, body)

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

        audit_service = AuditService(db)
        audit_service.log_status_change(
            resource_type="invoice",
            resource_id=invoice.id,  # type: ignore[arg-type]
            organization_id=organization_id,
            old_status="finalized",
            new_status="paid",
            actor_type="api_key",
        )

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

        audit_service = AuditService(db)
        audit_service.log_status_change(
            resource_type="invoice",
            resource_id=invoice.id,  # type: ignore[arg-type]
            organization_id=organization_id,
            old_status="finalized",
            new_status="voided",
            actor_type="api_key",
        )

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


@router.post(
    "/{invoice_id}/send_email",
    summary="Send invoice email",
    responses={
        400: {"description": "Invoice must be finalized or paid to send email"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
    },
)
async def send_invoice_email(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> dict[str, bool]:
    """Send an invoice notification email to the customer."""
    invoice_repo = InvoiceRepository(db)
    invoice = invoice_repo.get_by_id(invoice_id, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status not in (InvoiceStatus.FINALIZED.value, InvoiceStatus.PAID.value):
        raise HTTPException(
            status_code=400,
            detail="Invoice must be finalized or paid to send email",
        )

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(invoice.customer_id)  # type: ignore[arg-type]

    org_repo = OrganizationRepository(db)
    organization = org_repo.get_by_id(organization_id)

    pdf_bytes: bytes | None = None
    fee_repo = FeeRepository(db)
    fees = fee_repo.get_by_invoice_id(invoice_id)
    pdf_service = PdfService()
    pdf_bytes = pdf_service.generate_invoice_pdf(
        invoice=invoice,
        fees=fees,
        customer=customer,  # type: ignore[arg-type]
        organization=organization,  # type: ignore[arg-type]
    )

    email_service = EmailService()
    sent = await email_service.send_invoice_email(
        invoice=invoice,
        customer=customer,  # type: ignore[arg-type]
        organization=organization,  # type: ignore[arg-type]
        pdf_bytes=pdf_bytes,
    )
    return {"sent": sent}


@router.post(
    "/{invoice_id}/send_reminder",
    response_model=SendReminderResponse,
    summary="Send payment reminder for overdue invoice",
    responses={
        400: {"description": "Invoice is not overdue or finalized"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
    },
)
async def send_invoice_reminder(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> SendReminderResponse:
    """Send a payment reminder email for an overdue or finalized invoice."""
    invoice_repo = InvoiceRepository(db)
    invoice = invoice_repo.get_by_id(invoice_id, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != InvoiceStatus.FINALIZED.value:
        raise HTTPException(
            status_code=400,
            detail="Reminders can only be sent for finalized invoices",
        )

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(invoice.customer_id)  # type: ignore[arg-type]
    if not customer or not customer.email:
        raise HTTPException(status_code=400, detail="Customer has no email address")

    org_repo = OrganizationRepository(db)
    organization = org_repo.get_by_id(organization_id)

    org_name = str(organization.name or "") if organization else ""

    from app.services.email_service import _format_amount, _format_date

    html_body = (
        f"<h2>Payment Reminder</h2>"
        f"<p>Dear {customer.name or 'Customer'},</p>"
        f"<p>This is a friendly reminder that invoice "
        f"<strong>{invoice.invoice_number}</strong> from {org_name} "
        f"is awaiting payment.</p>"
        f"<table>"
        f"<tr><td><strong>Invoice #:</strong></td><td>{invoice.invoice_number}</td></tr>"
        f"<tr><td><strong>Amount Due:</strong></td>"
        f"<td>{_format_amount(invoice.total)} {invoice.currency}</td></tr>"
        f"<tr><td><strong>Due Date:</strong></td>"
        f"<td>{_format_date(invoice.due_date)}</td></tr>"
        f"</table>"
        f"<p>Please arrange payment at your earliest convenience.</p>"
        f"<p>Thank you.</p>"
    )

    email_service = EmailService()
    sent = await email_service.send_email(
        to=str(customer.email),
        subject=f"Payment Reminder: Invoice {invoice.invoice_number}",
        html_body=html_body,
    )

    return SendReminderResponse(sent=sent, invoice_id=invoice_id)


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


@router.get(
    "/{invoice_id}/pdf_preview",
    summary="Get invoice PDF for inline preview",
    responses={
        400: {"description": "Invoice must be finalized or paid to generate PDF"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
    },
)
async def preview_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Response:
    """Generate and return a PDF for inline preview (Content-Disposition: inline)."""
    invoice_repo = InvoiceRepository(db)
    invoice = invoice_repo.get_by_id(invoice_id, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status not in (InvoiceStatus.FINALIZED.value, InvoiceStatus.PAID.value):
        raise HTTPException(
            status_code=400,
            detail="Invoice must be finalized or paid to generate PDF",
        )

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(invoice.customer_id)  # type: ignore[arg-type]

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
            "Content-Disposition": f'inline; filename="invoice_{invoice.invoice_number}.pdf"'
        },
    )


@router.post(
    "/{invoice_id}/download_pdf",
    summary="Download invoice PDF",
    responses={
        400: {"description": "Invoice must be finalized or paid to generate PDF"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Invoice not found"},
    },
)
async def download_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Response:
    """Generate and download a PDF for a finalized or paid invoice."""
    invoice_repo = InvoiceRepository(db)
    invoice = invoice_repo.get_by_id(invoice_id, organization_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status not in (InvoiceStatus.FINALIZED.value, InvoiceStatus.PAID.value):
        raise HTTPException(
            status_code=400,
            detail="Invoice must be finalized or paid to generate PDF",
        )

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(invoice.customer_id)  # type: ignore[arg-type]

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
