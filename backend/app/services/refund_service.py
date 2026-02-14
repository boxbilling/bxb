"""Refund service for executing refunds through payment providers."""

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.credit_note import CreditNoteType, RefundStatus
from app.models.invoice_settlement import SettlementType
from app.models.payment import PaymentProvider
from app.repositories.credit_note_repository import CreditNoteRepository
from app.repositories.invoice_settlement_repository import InvoiceSettlementRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.credit_note import CreditNoteUpdate
from app.services.payment_provider import get_payment_provider
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)


class RefundService:
    """Service for processing refunds through payment providers."""

    def __init__(self, db: Session):
        self.db = db
        self.credit_note_repo = CreditNoteRepository(db)
        self.settlement_repo = InvoiceSettlementRepository(db)
        self.payment_repo = PaymentRepository(db)
        self.webhook_service = WebhookService(db)

    def process_refund(self, credit_note_id: UUID) -> bool:
        """Process a refund for a credit note.

        Loads the credit note, finds the associated invoice's payment(s),
        determines the payment provider, calls the provider's create_refund,
        and updates the credit note's refund_status.

        Args:
            credit_note_id: The credit note to process a refund for.

        Returns:
            True if the refund succeeded, False otherwise.
        """
        credit_note = self.credit_note_repo.get_by_id(credit_note_id)
        if not credit_note:
            logger.error("Credit note %s not found", credit_note_id)
            return False

        if credit_note.credit_note_type != CreditNoteType.REFUND.value:
            logger.error("Credit note %s is not a refund type", credit_note_id)
            return False

        # Set refund status to pending
        self.credit_note_repo.update(
            credit_note_id,
            CreditNoteUpdate(refund_status=RefundStatus.PENDING),
        )

        # Find payment settlements for the invoice
        invoice_id = UUID(str(credit_note.invoice_id))
        settlements = self.settlement_repo.get_by_invoice_id(invoice_id)
        payment_settlements = [
            s for s in settlements if s.settlement_type == SettlementType.PAYMENT.value
        ]

        if not payment_settlements:
            logger.warning(
                "No payment found for credit note %s invoice %s",
                credit_note_id,
                invoice_id,
            )
            self.credit_note_repo.update(
                credit_note_id,
                CreditNoteUpdate(refund_status=RefundStatus.FAILED),
            )
            self.webhook_service.send_webhook(
                webhook_type="credit_note.refund.failed",
                object_type="credit_note",
                object_id=credit_note_id,
                payload={
                    "credit_note_id": str(credit_note_id),
                    "failure_reason": "No payment found for invoice",
                },
            )
            return False

        # Use the first payment settlement to find the payment record
        payment_source_id = UUID(str(payment_settlements[0].source_id))
        payment = self.payment_repo.get_by_id(payment_source_id)

        if not payment or not payment.provider_payment_id:
            logger.warning(
                "Payment record not found or missing provider ID for credit note %s",
                credit_note_id,
            )
            self.credit_note_repo.update(
                credit_note_id,
                CreditNoteUpdate(refund_status=RefundStatus.FAILED),
            )
            self.webhook_service.send_webhook(
                webhook_type="credit_note.refund.failed",
                object_type="credit_note",
                object_id=credit_note_id,
                payload={
                    "credit_note_id": str(credit_note_id),
                    "failure_reason": "Payment record not found or missing provider ID",
                },
            )
            return False

        # Determine the provider and execute the refund
        provider_enum = PaymentProvider(payment.provider)
        provider = get_payment_provider(provider_enum)

        refund_amount = Decimal(str(credit_note.refund_amount_cents))
        currency = str(credit_note.currency)
        provider_payment_id = str(payment.provider_payment_id)

        result = provider.create_refund(
            provider_payment_id=provider_payment_id,
            amount=refund_amount,
            currency=currency,
            metadata={"credit_note_id": str(credit_note_id)},
        )

        if result.status == "failed":
            self.credit_note_repo.update(
                credit_note_id,
                CreditNoteUpdate(refund_status=RefundStatus.FAILED),
            )
            self.webhook_service.send_webhook(
                webhook_type="credit_note.refund.failed",
                object_type="credit_note",
                object_id=credit_note_id,
                payload={
                    "credit_note_id": str(credit_note_id),
                    "provider_refund_id": result.provider_refund_id,
                    "failure_reason": result.failure_reason,
                },
            )
            return False

        # Refund succeeded or is pending
        refund_status = (
            RefundStatus.SUCCEEDED if result.status == "succeeded" else RefundStatus.PENDING
        )
        self.credit_note_repo.update(
            credit_note_id,
            CreditNoteUpdate(refund_status=refund_status),
        )
        self.webhook_service.send_webhook(
            webhook_type="credit_note.refund.succeeded",
            object_type="credit_note",
            object_id=credit_note_id,
            payload={
                "credit_note_id": str(credit_note_id),
                "provider_refund_id": result.provider_refund_id,
                "status": result.status,
            },
        )
        return True
