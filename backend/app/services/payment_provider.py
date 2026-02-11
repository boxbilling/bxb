"""Payment provider abstraction layer.

Supports multiple payment providers (Stripe, UCP, manual, etc.)
"""

import hashlib
import hmac
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
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
                raise ImportError("stripe package not installed. Run: pip install stripe") from e
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


class UCPProvider(PaymentProviderBase):
    """Universal Commerce Protocol (UCP) payment provider.

    UCP is an open protocol for agentic commerce backed by Google, Shopify,
    Stripe, and others. See https://ucp.dev for details.

    UCP checkout sessions follow the spec at:
    https://ucp.dev/latest/specification/checkout-rest/
    """

    UCP_VERSION = "2026-01-23"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        webhook_secret: str | None = None,
        merchant_id: str | None = None,
    ):
        self.base_url = (base_url or settings.ucp_base_url).rstrip("/")
        self.api_key = api_key or settings.ucp_api_key
        self.webhook_secret = webhook_secret or settings.ucp_webhook_secret
        self.merchant_id = merchant_id or settings.ucp_merchant_id

    @property
    def provider_name(self) -> PaymentProvider:
        return PaymentProvider.UCP

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the UCP API."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "UCP-Agent": f'profile="{self.base_url}/.well-known/ucp"',
        }

        body = json.dumps(data).encode() if data else None
        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=30) as response:
                result: dict[str, Any] = json.loads(response.read().decode())
                return result
        except URLError as e:
            raise RuntimeError(f"UCP API request failed: {e}") from e

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
        """Create a UCP checkout session.

        Following the UCP Checkout REST spec:
        POST /checkout-sessions
        """
        # Amount in UCP is in smallest currency unit (cents)
        amount_cents = int(amount * 100)

        # Build UCP checkout session request
        request_data: dict[str, Any] = {
            "line_items": [
                {
                    "id": f"li_{payment_id}",
                    "item": {
                        "id": f"inv_{invoice_number}",
                        "title": f"Invoice {invoice_number}",
                        "price": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            "metadata": {
                "payment_id": str(payment_id),
                "invoice_number": invoice_number,
                "success_url": success_url,
                "cancel_url": cancel_url,
                **(metadata or {}),
            },
        }

        # Add buyer info if email available
        if customer_email:
            request_data["buyer"] = {"email": customer_email}

        # Make the API call
        response = self._make_request("POST", "/checkout-sessions", request_data)

        # Extract checkout session ID and build checkout URL
        checkout_id = response.get("id", f"ucp_{payment_id}")

        # UCP returns a permalink in the response, or we construct one
        checkout_url = response.get("permalink_url", "")
        if not checkout_url and self.base_url:
            checkout_url = f"{self.base_url}/checkout/{checkout_id}"

        # Calculate expiry (UCP sessions typically expire in 24 hours)
        expires_at = datetime.now(UTC) + timedelta(hours=24)

        return CheckoutSession(
            provider_checkout_id=checkout_id,
            checkout_url=checkout_url,
            expires_at=expires_at,
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify UCP webhook signature using HMAC-SHA256."""
        if not self.webhook_secret:
            return False

        # UCP uses HMAC-SHA256 for webhook signatures
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        # Support both raw hex and "sha256=" prefixed signatures
        if signature.startswith("sha256="):
            signature = signature[7:]

        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, payload: dict[str, Any]) -> WebhookResult:
        """Parse UCP webhook payload.

        UCP sends events for checkout status changes and order updates.
        See: https://ucp.dev/latest/specification/order/
        """
        event_type = payload.get("type", payload.get("event_type", "ucp.unknown"))

        # Extract checkout/order data
        data = payload.get("data", payload)
        checkout_id = data.get("checkout_id") or data.get("id")
        order_id = data.get("order_id") or data.get("id")
        status_raw = data.get("status", "")

        # Map UCP statuses to our internal statuses
        # UCP checkout statuses: incomplete, ready_for_complete, completed, canceled
        status_map = {
            "completed": "succeeded",
            "ready_for_complete": "pending",
            "incomplete": "pending",
            "canceled": "canceled",
            "failed": "failed",
            "refunded": "refunded",
        }
        status = status_map.get(status_raw)

        # Extract metadata
        meta = data.get("metadata", {})
        if not meta and "line_items" in data:
            # Try to extract from line items
            for item in data.get("line_items", []):
                if item.get("item", {}).get("id", "").startswith("inv_"):
                    meta["invoice_number"] = item["item"]["id"][4:]
                    break

        result = WebhookResult(
            event_type=event_type,
            provider_checkout_id=checkout_id,
            provider_payment_id=order_id if order_id != checkout_id else None,
            status=status,
            metadata=meta,
        )

        # Handle error messages for failed payments
        if status == "failed":
            messages = data.get("messages", [])
            for msg in messages:
                if msg.get("type") == "error":
                    result.failure_reason = msg.get("content", "Payment failed")
                    break
            if not result.failure_reason:
                result.failure_reason = "Payment failed"

        return result


def get_payment_provider(provider: PaymentProvider) -> PaymentProviderBase:
    """Factory function to get the appropriate payment provider."""
    providers: dict[PaymentProvider, type[PaymentProviderBase]] = {
        PaymentProvider.STRIPE: StripeProvider,
        PaymentProvider.MANUAL: ManualProvider,
        PaymentProvider.UCP: UCPProvider,
    }

    provider_class = providers.get(provider)
    if not provider_class:
        raise ValueError(f"Unsupported payment provider: {provider}")

    return provider_class()
