"""Payment repository for data access."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.schemas.payment import PaymentUpdate


class PaymentRepository:
    """Repository for Payment model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        invoice_id: UUID | None = None,
        customer_id: UUID | None = None,
        status: PaymentStatus | None = None,
        provider: PaymentProvider | None = None,
        organization_id: UUID | None = None,
    ) -> list[Payment]:
        """Get all payments with optional filters."""
        query = self.db.query(Payment)

        if organization_id is not None:
            query = query.filter(Payment.organization_id == organization_id)
        if invoice_id:
            query = query.filter(Payment.invoice_id == invoice_id)
        if customer_id:
            query = query.filter(Payment.customer_id == customer_id)
        if status:
            query = query.filter(Payment.status == status.value)
        if provider:
            query = query.filter(Payment.provider == provider.value)

        return query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_id(self, payment_id: UUID, organization_id: UUID | None = None) -> Payment | None:
        """Get a payment by ID."""
        query = self.db.query(Payment).filter(Payment.id == payment_id)
        if organization_id is not None:
            query = query.filter(Payment.organization_id == organization_id)
        return query.first()

    def get_by_provider_payment_id(self, provider_payment_id: str) -> Payment | None:
        """Get a payment by provider payment ID (e.g., Stripe PaymentIntent ID)."""
        return (
            self.db.query(Payment)
            .filter(Payment.provider_payment_id == provider_payment_id)
            .first()
        )

    def get_by_provider_checkout_id(self, provider_checkout_id: str) -> Payment | None:
        """Get a payment by provider checkout session ID."""
        return (
            self.db.query(Payment)
            .filter(Payment.provider_checkout_id == provider_checkout_id)
            .first()
        )

    def create(
        self,
        invoice_id: UUID,
        customer_id: UUID,
        amount: float,
        currency: str,
        provider: PaymentProvider = PaymentProvider.STRIPE,
        metadata: dict[str, Any] | None = None,
        organization_id: UUID | None = None,
    ) -> Payment:
        """Create a new payment."""
        payment = Payment(
            invoice_id=invoice_id,
            customer_id=customer_id,
            amount=amount,
            currency=currency,
            provider=provider.value,
            status=PaymentStatus.PENDING.value,
            payment_metadata=metadata or {},
            organization_id=organization_id,
        )
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def update(
        self,
        payment_id: UUID,
        data: PaymentUpdate,
        organization_id: UUID | None = None,
    ) -> Payment | None:
        """Update a payment."""
        payment = self.get_by_id(payment_id, organization_id=organization_id)
        if not payment:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Convert status enum to string value, or remove if None
        if "status" in update_data:
            if update_data["status"]:
                update_data["status"] = update_data["status"].value
            else:
                # Don't update status if it's None (would violate NOT NULL)
                del update_data["status"]

        for key, value in update_data.items():
            setattr(payment, key, value)

        self.db.commit()
        self.db.refresh(payment)
        return payment

    def set_provider_ids(
        self,
        payment_id: UUID,
        provider_payment_id: str | None = None,
        provider_checkout_id: str | None = None,
        provider_checkout_url: str | None = None,
    ) -> Payment | None:
        """Set provider-specific IDs on a payment."""
        payment = self.get_by_id(payment_id)
        if not payment:
            return None

        if provider_payment_id:
            payment.provider_payment_id = provider_payment_id  # type: ignore[assignment]
        if provider_checkout_id:
            payment.provider_checkout_id = provider_checkout_id  # type: ignore[assignment]
        if provider_checkout_url:
            payment.provider_checkout_url = provider_checkout_url  # type: ignore[assignment]

        self.db.commit()
        self.db.refresh(payment)
        return payment

    def mark_processing(self, payment_id: UUID) -> Payment | None:
        """Mark a payment as processing."""
        payment = self.get_by_id(payment_id)
        if not payment:
            return None

        payment.status = PaymentStatus.PROCESSING.value  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def mark_succeeded(self, payment_id: UUID) -> Payment | None:
        """Mark a payment as succeeded."""
        payment = self.get_by_id(payment_id)
        if not payment:
            return None

        payment.status = PaymentStatus.SUCCEEDED.value  # type: ignore[assignment]
        payment.completed_at = datetime.now(UTC)  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def mark_failed(self, payment_id: UUID, reason: str | None = None) -> Payment | None:
        """Mark a payment as failed."""
        payment = self.get_by_id(payment_id)
        if not payment:
            return None

        payment.status = PaymentStatus.FAILED.value  # type: ignore[assignment]
        if reason:
            payment.failure_reason = reason  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def mark_canceled(self, payment_id: UUID) -> Payment | None:
        """Mark a payment as canceled."""
        payment = self.get_by_id(payment_id)
        if not payment:
            return None

        payment.status = PaymentStatus.CANCELED.value  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def mark_refunded(self, payment_id: UUID) -> Payment | None:
        """Mark a payment as refunded."""
        payment = self.get_by_id(payment_id)
        if not payment:
            return None
        if payment.status != PaymentStatus.SUCCEEDED.value:
            raise ValueError("Only succeeded payments can be refunded")

        payment.status = PaymentStatus.REFUNDED.value  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def delete(self, payment_id: UUID, organization_id: UUID | None = None) -> bool:
        """Delete a payment (only pending payments can be deleted)."""
        payment = self.get_by_id(payment_id, organization_id=organization_id)
        if not payment:
            return False
        if payment.status != PaymentStatus.PENDING.value:
            raise ValueError("Only pending payments can be deleted")

        self.db.delete(payment)
        self.db.commit()
        return True
