"""Payment request service for manual payment request management."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_request import PaymentRequest
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_request_repository import PaymentRequestRepository
from app.schemas.payment_request import (
    BatchPaymentRequestResult,
    PaymentAttemptEntry,
)
from app.services.webhook_service import WebhookService


class PaymentRequestService:
    """Service for creating and managing manual payment requests."""

    def __init__(self, db: Session):
        self.db = db
        self.pr_repo = PaymentRequestRepository(db)
        self.invoice_repo = InvoiceRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.webhook_service = WebhookService(db)

    def create_manual_payment_request(
        self,
        organization_id: UUID,
        customer_id: UUID,
        invoice_ids: list[UUID],
    ) -> PaymentRequest:
        """Create a PaymentRequest manually for specific invoices.

        Validates that all invoices belong to the customer and are finalized (unpaid).
        Computes the total amount from the invoices.
        """
        # Verify customer exists
        customer = self.customer_repo.get_by_id(customer_id, organization_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        # Validate all invoices
        total_amount = Decimal("0")
        currency: str | None = None
        for invoice_id in invoice_ids:
            invoice = self.invoice_repo.get_by_id(invoice_id, organization_id)
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found")
            inv_customer_id: UUID = invoice.customer_id  # type: ignore[assignment]
            if inv_customer_id != customer_id:
                raise ValueError(f"Invoice {invoice_id} does not belong to customer {customer_id}")
            if invoice.status != InvoiceStatus.FINALIZED.value:
                raise ValueError(f"Invoice {invoice_id} is not in finalized status")

            # Ensure all invoices have the same currency
            if currency is None:
                currency = str(invoice.currency)
            elif str(invoice.currency) != currency:
                raise ValueError("All invoices must have the same currency")

            total_amount += Decimal(str(invoice.total_cents))

        if currency is None:
            raise ValueError("No invoices provided")

        pr = self.pr_repo.create(
            organization_id=organization_id,
            customer_id=customer_id,
            amount_cents=total_amount,
            amount_currency=currency,
            invoice_ids=invoice_ids,
        )

        self.webhook_service.send_webhook(
            webhook_type="payment_request.created",
            object_type="payment_request",
            object_id=pr.id,  # type: ignore[arg-type]
            payload={
                "payment_request_id": str(pr.id),
                "customer_id": str(customer_id),
                "amount_cents": str(total_amount),
                "amount_currency": currency,
            },
        )

        return pr

    def get_customer_outstanding(
        self,
        customer_id: UUID,
        organization_id: UUID,
    ) -> Decimal:
        """Sum all unpaid (finalized) invoice totals for a customer."""
        invoices = self.invoice_repo.get_all(
            organization_id=organization_id,
            customer_id=customer_id,
            status=InvoiceStatus.FINALIZED,
        )
        return sum(
            (Decimal(str(inv.total_cents)) for inv in invoices),
            Decimal("0"),
        )

    def batch_create_for_overdue(
        self,
        organization_id: UUID,
    ) -> list[BatchPaymentRequestResult]:
        """Create payment requests for all customers with overdue finalized invoices.

        Groups overdue invoices by customer and currency, creating one payment
        request per customer+currency combination.
        """
        from datetime import UTC
        from datetime import datetime as dt

        now = dt.now(UTC)

        # Get all finalized invoices that are overdue (due_date in the past)
        invoices = self.invoice_repo.get_all(
            organization_id=organization_id,
            status=InvoiceStatus.FINALIZED,
        )
        overdue = []
        for inv in invoices:
            if inv.due_date is None:
                continue
            due = inv.due_date
            # Handle naive datetimes (SQLite) by assuming UTC
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            if due < now:
                overdue.append(inv)

        if not overdue:
            return []

        # Group by (customer_id, currency)
        groups: dict[tuple[UUID, str], list[Invoice]] = {}
        for inv in overdue:
            cust_id: UUID = inv.customer_id  # type: ignore[assignment]
            key = (cust_id, str(inv.currency or "USD"))
            groups.setdefault(key, []).append(inv)

        results: list[BatchPaymentRequestResult] = []
        for (customer_id, currency), group_invoices in groups.items():
            customer = self.customer_repo.get_by_id(customer_id, organization_id)
            customer_name = str(customer.name) if customer else str(customer_id)
            total = Decimal("0")
            for inv in group_invoices:
                total += Decimal(str(inv.total_cents))
            invoice_ids: list[UUID] = [inv.id for inv in group_invoices]  # type: ignore[misc]

            try:
                pr = self.pr_repo.create(
                    organization_id=organization_id,
                    customer_id=customer_id,
                    amount_cents=total,
                    amount_currency=currency,
                    invoice_ids=invoice_ids,
                )
                self.webhook_service.send_webhook(
                    webhook_type="payment_request.created",
                    object_type="payment_request",
                    object_id=pr.id,  # type: ignore[arg-type]
                    payload={
                        "payment_request_id": str(pr.id),
                        "customer_id": str(customer_id),
                        "amount_cents": str(total),
                        "amount_currency": currency,
                    },
                )
                results.append(BatchPaymentRequestResult(
                    customer_id=customer_id,
                    customer_name=customer_name,
                    payment_request_id=pr.id,  # type: ignore[arg-type]
                    invoice_count=len(group_invoices),
                    amount_cents=total,
                    amount_currency=currency,
                    status="created",
                ))
            except Exception as e:
                results.append(BatchPaymentRequestResult(
                    customer_id=customer_id,
                    customer_name=customer_name,
                    invoice_count=len(group_invoices),
                    amount_cents=total,
                    amount_currency=currency,
                    status="error",
                    error=str(e),
                ))

        return results

    def get_attempt_history(
        self,
        request_id: UUID,
        organization_id: UUID,
    ) -> list[PaymentAttemptEntry]:
        """Get the payment attempt history for a payment request.

        Pulls from audit logs to reconstruct the timeline of status changes.
        """
        pr = self.pr_repo.get_by_id(request_id, organization_id)
        if not pr:
            return []

        # Query audit logs for this payment request
        logs: list[AuditLog] = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.resource_type == "payment_request",
                AuditLog.resource_id == request_id,
                AuditLog.organization_id == organization_id,
            )
            .order_by(AuditLog.created_at.asc())
            .all()
        )

        entries: list[PaymentAttemptEntry] = []

        # Always include creation as the first entry
        entries.append(PaymentAttemptEntry(
            timestamp=pr.created_at,  # type: ignore[arg-type]
            action="created",
            new_status="pending",
            attempt_number=0,
        ))

        for log in logs:
            changes: dict[str, object] = dict(log.changes) if log.changes else {}
            action = str(log.action)
            old_status_val = changes.get("old_status")
            new_status_val = changes.get("new_status") or changes.get("status")
            attempt_num_val = changes.get("attempt_number")

            entries.append(PaymentAttemptEntry(
                timestamp=log.created_at,  # type: ignore[arg-type]
                action=action,
                old_status=str(old_status_val) if old_status_val else None,
                new_status=str(new_status_val) if new_status_val else None,
                attempt_number=int(str(attempt_num_val)) if attempt_num_val is not None else None,
                details=changes if changes else None,
            ))

        return entries
