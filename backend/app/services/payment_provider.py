"""Payment provider abstraction layer.

Supports multiple payment providers (Stripe, manual, etc.)
"""

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.models.payment import PaymentProvider


@dataclass
class CheckoutSession:
    """Checkout session result from provider."""

    provider_checkout_id: str
    checkout_url: str
    expires_at: datetime | None = None


@dataclass
class WebhookResult:
    """Result of processing a webhook."""

    event_type: str
    provider_payment_id: str | None = None
    provider_checkout_id: str | None = None
    status: str | None = None
    failure_reason: str | None = None
    metadata: dict[str, Any] | None = None


class PaymentProviderBase(ABC):
    """Abstract base class for payment providers."""

    @property
    @abstractmethod
    def provider_name(self) -> PaymentProvider:
        """Return the provider enum value."""
        pass  # pragma: no cover

    @abstractmethod
    def create_checkout_session(
        self,
        payment_id: UUID,
        amount: Decimal,
        currency: str,
        customer_email: str | None,
        invoice_number: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutSession:
        """Create a checkout session for the payment."""
        pass  # pragma: no cover

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify the webhook signature."""
        pass  # pragma: no cover

    @abstractmethod
    def parse_webhook(self, payload: dict[str, Any]) -> WebhookResult:
        """Parse a webhook payload and return structured result."""
        pass  # pragma: no cover


class StripeProvider(PaymentProviderBase):
    """Stripe payment provider implementation."""

    def __init__(self, api_key: str | None = None, webhook_secret: str | None = None):
        self.api_key = api_key or settings.stripe_api_key
        self.webhook_secret = webhook_secret or settings.stripe_webhook_secret
        self._stripe: Any = None

    @property
    def stripe(self) -> Any:
        """Lazy-load stripe module."""
        if self._stripe is None:
            try:
                import stripe

                stripe.api_key = self.api_key
                self._stripe = stripe
            except ImportError as e:
                raise ImportError(
                    "stripe package not installed. Run: pip install stripe"
                ) from e
        return self._stripe

    @property
    def provider_name(self) -> PaymentProvider:
        return PaymentProvider.STRIPE

    def create_checkout_session(
        self,
        payment_id: UUID,
        amount: Decimal,
        currency: str,
        customer_email: str | None,
        invoice_number: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutSession:
        """Create a Stripe Checkout Session."""
        # Convert amount to cents (Stripe uses smallest currency unit)
        amount_cents = int(amount * 100)

        session_params: dict[str, Any] = {
            "payment_method_types": ["card"],
            "line_items": [
                {
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {
                            "name": f"Invoice {invoice_number}",
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {
                "payment_id": str(payment_id),
                "invoice_number": invoice_number,
                **(metadata or {}),
            },
        }

        if customer_email:
            session_params["customer_email"] = customer_email

        session = self.stripe.checkout.Session.create(**session_params)

        return CheckoutSession(
            provider_checkout_id=session.id,
            checkout_url=session.url,
            expires_at=datetime.fromtimestamp(session.expires_at, tz=UTC)
            if session.expires_at
            else None,
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Stripe webhook signature."""
        if not self.webhook_secret:
            return False
        try:
            self.stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
            return True
        except (ValueError, self.stripe.error.SignatureVerificationError):
            return False

    def parse_webhook(self, payload: dict[str, Any]) -> WebhookResult:
        """Parse Stripe webhook payload."""
        event_type = payload.get("type", "")
        data_object = payload.get("data", {}).get("object", {})

        result = WebhookResult(
            event_type=event_type,
            metadata=data_object.get("metadata"),
        )

        # Handle different event types
        if event_type == "checkout.session.completed":
            result.provider_checkout_id = data_object.get("id")
            result.provider_payment_id = data_object.get("payment_intent")
            is_paid = data_object.get("payment_status") == "paid"
            result.status = "succeeded" if is_paid else "pending"

        elif event_type == "payment_intent.succeeded":
            result.provider_payment_id = data_object.get("id")
            result.status = "succeeded"

        elif event_type == "payment_intent.payment_failed":
            result.provider_payment_id = data_object.get("id")
            result.status = "failed"
            last_error = data_object.get("last_payment_error", {})
            result.failure_reason = last_error.get("message", "Payment failed")

        elif event_type == "checkout.session.expired":
            result.provider_checkout_id = data_object.get("id")
            result.status = "canceled"

        return result


class ManualProvider(PaymentProviderBase):
    """Manual payment provider for offline/manual payments."""

    @property
    def provider_name(self) -> PaymentProvider:
        return PaymentProvider.MANUAL

    def create_checkout_session(
        self,
        payment_id: UUID,
        amount: Decimal,
        currency: str,
        customer_email: str | None,
        invoice_number: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> CheckoutSession:
        """Manual payments don't have checkout sessions."""
        # Return a placeholder - manual payments are marked paid directly
        return CheckoutSession(
            provider_checkout_id=f"manual_{payment_id}",
            checkout_url="",  # No URL for manual payments
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Manual provider uses HMAC-SHA256 for signature verification."""
        if not settings.manual_webhook_secret:
            return False
        expected = hmac.new(
            settings.manual_webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, payload: dict[str, Any]) -> WebhookResult:
        """Parse manual webhook payload."""
        return WebhookResult(
            event_type=payload.get("event_type", "payment.manual"),
            provider_payment_id=payload.get("payment_id"),
            status=payload.get("status", "succeeded"),
            metadata=payload.get("metadata"),
        )


def get_payment_provider(provider: PaymentProvider) -> PaymentProviderBase:
    """Factory function to get the appropriate payment provider."""
    providers: dict[PaymentProvider, type[PaymentProviderBase]] = {
        PaymentProvider.STRIPE: StripeProvider,
        PaymentProvider.MANUAL: ManualProvider,
    }

    provider_class = providers.get(provider)
    if not provider_class:
        raise ValueError(f"Unsupported payment provider: {provider}")

    return provider_class()
