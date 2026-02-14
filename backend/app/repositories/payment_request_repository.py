"""PaymentRequest repository for data access."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.payment_request import PaymentRequest
from app.models.payment_request_invoice import PaymentRequestInvoice


class PaymentRequestRepository:
    """Repository for PaymentRequest model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        customer_id: UUID | None = None,
        payment_status: str | None = None,
    ) -> list[PaymentRequest]:
        """Get all payment requests for an organization."""
        query = self.db.query(PaymentRequest).filter(
            PaymentRequest.organization_id == organization_id,
        )
        if customer_id is not None:
            query = query.filter(PaymentRequest.customer_id == customer_id)
        if payment_status is not None:
            query = query.filter(PaymentRequest.payment_status == payment_status)
        return query.order_by(PaymentRequest.created_at.desc()).offset(skip).limit(limit).all()

    def count(self, organization_id: UUID) -> int:
        """Count payment requests for an organization."""
        return (
            self.db.query(func.count(PaymentRequest.id))
            .filter(PaymentRequest.organization_id == organization_id)
            .scalar()
            or 0
        )

    def get_by_id(
        self,
        request_id: UUID,
        organization_id: UUID,
    ) -> PaymentRequest | None:
        """Get a payment request by ID."""
        return (
            self.db.query(PaymentRequest)
            .filter(
                PaymentRequest.id == request_id,
                PaymentRequest.organization_id == organization_id,
            )
            .first()
        )

    def create(
        self,
        organization_id: UUID,
        customer_id: UUID,
        amount_cents: Decimal,
        amount_currency: str,
        invoice_ids: list[UUID],
        dunning_campaign_id: UUID | None = None,
    ) -> PaymentRequest:
        """Create a new payment request with linked invoices."""
        payment_request = PaymentRequest(
            organization_id=organization_id,
            customer_id=customer_id,
            amount_cents=amount_cents,
            amount_currency=amount_currency,
            dunning_campaign_id=dunning_campaign_id,
        )
        self.db.add(payment_request)
        self.db.flush()

        for invoice_id in invoice_ids:
            join_row = PaymentRequestInvoice(
                payment_request_id=payment_request.id,
                invoice_id=invoice_id,
            )
            self.db.add(join_row)

        self.db.commit()
        self.db.refresh(payment_request)
        return payment_request

    def update_status(
        self,
        request_id: UUID,
        organization_id: UUID,
        payment_status: str,
    ) -> PaymentRequest | None:
        """Update the payment status of a payment request."""
        payment_request = self.get_by_id(request_id, organization_id)
        if not payment_request:
            return None
        payment_request.payment_status = payment_status  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(payment_request)
        return payment_request

    def increment_attempts(
        self,
        request_id: UUID,
        organization_id: UUID,
    ) -> PaymentRequest | None:
        """Increment payment attempts counter."""
        payment_request = self.get_by_id(request_id, organization_id)
        if not payment_request:
            return None
        payment_request.payment_attempts += 1  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(payment_request)
        return payment_request

    def get_invoices(self, request_id: UUID) -> list[PaymentRequestInvoice]:
        """Get all invoice links for a payment request."""
        return (
            self.db.query(PaymentRequestInvoice)
            .filter(PaymentRequestInvoice.payment_request_id == request_id)
            .all()
        )

    def delete(self, request_id: UUID, organization_id: UUID) -> bool:
        """Delete a payment request (only pending requests)."""
        payment_request = self.get_by_id(request_id, organization_id)
        if not payment_request:
            return False
        if payment_request.payment_status != "pending":
            raise ValueError("Only pending payment requests can be deleted")
        # Delete linked invoices first (cascade should handle this but be explicit)
        self.db.query(PaymentRequestInvoice).filter(
            PaymentRequestInvoice.payment_request_id == request_id,
        ).delete()
        self.db.delete(payment_request)
        self.db.commit()
        return True
