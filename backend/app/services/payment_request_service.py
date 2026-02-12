"""Payment request service for manual payment request management."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.invoice import InvoiceStatus
from app.models.payment_request import PaymentRequest
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_request_repository import PaymentRequestRepository
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
                raise ValueError(
                    f"Invoice {invoice_id} does not belong to customer {customer_id}"
                )
            if invoice.status != InvoiceStatus.FINALIZED.value:
                raise ValueError(
                    f"Invoice {invoice_id} is not in finalized status"
                )

            # Ensure all invoices have the same currency
            if currency is None:
                currency = str(invoice.currency)
            elif str(invoice.currency) != currency:
                raise ValueError("All invoices must have the same currency")

            total_amount += Decimal(str(invoice.total))

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
        self, customer_id: UUID, organization_id: UUID,
    ) -> Decimal:
        """Sum all unpaid (finalized) invoice totals for a customer."""
        invoices = self.invoice_repo.get_all(
            organization_id=organization_id,
            customer_id=customer_id,
            status=InvoiceStatus.FINALIZED,
        )
        return sum(
            (Decimal(str(inv.total)) for inv in invoices),
            Decimal("0"),
        )
