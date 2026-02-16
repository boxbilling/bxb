"""Service for creating and managing in-app notifications."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.repositories.notification_repository import NotificationRepository

# Notification categories
CATEGORY_WEBHOOK = "webhook"
CATEGORY_DUNNING = "dunning"
CATEGORY_WALLET = "wallet"
CATEGORY_INVOICE = "invoice"
CATEGORY_PAYMENT = "payment"
CATEGORY_SUBSCRIPTION = "subscription"


class NotificationService:
    """Service for creating in-app notifications from system events."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = NotificationRepository(db)

    def notify(
        self,
        *,
        organization_id: UUID,
        category: str,
        title: str,
        message: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> Notification:
        """Create a notification."""
        return self.repo.create(
            organization_id=organization_id,
            category=category,
            title=title,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    def notify_webhook_failure(
        self,
        *,
        organization_id: UUID,
        webhook_type: str,
        endpoint_url: str,
        error: str | None = None,
        webhook_id: UUID | None = None,
    ) -> Notification:
        """Create a notification for a failed webhook delivery."""
        msg = f"Webhook delivery to {endpoint_url} failed for event '{webhook_type}'."
        if error:
            msg += f" Error: {error}"
        return self.notify(
            organization_id=organization_id,
            category=CATEGORY_WEBHOOK,
            title="Webhook delivery failed",
            message=msg,
            resource_type="webhook",
            resource_id=webhook_id,
        )

    def notify_dunning_alert(
        self,
        *,
        organization_id: UUID,
        customer_name: str,
        amount_cents: int,
        currency: str,
        payment_request_id: UUID | None = None,
    ) -> Notification:
        """Create a notification when a dunning payment request is created."""
        amount = amount_cents / 100
        return self.notify(
            organization_id=organization_id,
            category=CATEGORY_DUNNING,
            title="Dunning payment request created",
            message=(
                f"Payment request created for {customer_name}: "
                f"{amount:.2f} {currency.upper()}."
            ),
            resource_type="payment_request",
            resource_id=payment_request_id,
        )

    def notify_wallet_expiring(
        self,
        *,
        organization_id: UUID,
        wallet_name: str,
        days_remaining: int,
        wallet_id: UUID | None = None,
    ) -> Notification:
        """Create a notification when a wallet is about to expire."""
        return self.notify(
            organization_id=organization_id,
            category=CATEGORY_WALLET,
            title="Wallet expiring soon",
            message=(
                f"Wallet '{wallet_name}' will expire in {days_remaining} "
                f"day{'s' if days_remaining != 1 else ''}."
            ),
            resource_type="wallet",
            resource_id=wallet_id,
        )

    def notify_invoice_overdue(
        self,
        *,
        organization_id: UUID,
        invoice_number: str,
        customer_name: str,
        amount_cents: int,
        currency: str,
        invoice_id: UUID | None = None,
    ) -> Notification:
        """Create a notification when an invoice becomes overdue."""
        amount = amount_cents / 100
        return self.notify(
            organization_id=organization_id,
            category=CATEGORY_INVOICE,
            title="Invoice overdue",
            message=(
                f"Invoice {invoice_number} for {customer_name} "
                f"({amount:.2f} {currency.upper()}) is overdue."
            ),
            resource_type="invoice",
            resource_id=invoice_id,
        )

    def notify_payment_failed(
        self,
        *,
        organization_id: UUID,
        customer_name: str,
        amount_cents: int,
        currency: str,
        payment_id: UUID | None = None,
    ) -> Notification:
        """Create a notification when a payment fails."""
        amount = amount_cents / 100
        return self.notify(
            organization_id=organization_id,
            category=CATEGORY_PAYMENT,
            title="Payment failed",
            message=(
                f"Payment of {amount:.2f} {currency.upper()} "
                f"from {customer_name} has failed."
            ),
            resource_type="payment",
            resource_id=payment_id,
        )
