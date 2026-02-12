"""GoCardless payment provider implementation.

GoCardless uses a mandate-based flow:
1. Create a redirect flow (mandate setup) — customer authorizes bank debit
2. Complete the redirect flow to get the mandate
3. Create payments against the mandate

This differs from Stripe's checkout→charge model.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import UUID

from app.core.config import settings
from app.models.payment import PaymentProvider
from app.services.payment_provider import CheckoutSession, PaymentProviderBase, WebhookResult


class GoCardlessProvider(PaymentProviderBase):
    """GoCardless payment provider.

    GoCardless uses Direct Debit via bank mandates. The checkout session
    creates a redirect flow for mandate setup. Once the mandate is active,
    payments can be collected against it.
    """

    def __init__(
        self,
        access_token: str | None = None,
        webhook_secret: str | None = None,
        environment: str | None = None,
    ):
        self.access_token = access_token or settings.gocardless_access_token
        self.webhook_secret = webhook_secret or settings.gocardless_webhook_secret
        self.environment = environment or settings.gocardless_environment
        self._base_url = (
            "https://api.gocardless.com"
            if self.environment == "live"
            else "https://api-sandbox.gocardless.com"
        )

    @property
    def provider_name(self) -> PaymentProvider:
        return PaymentProvider.GOCARDLESS

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the GoCardless API."""
        url = f"{self._base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "GoCardless-Version": "2015-07-06",
        }

        body = json.dumps(data).encode() if data else None
        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=30) as response:
                result: dict[str, Any] = json.loads(response.read().decode())
                return result
        except URLError as e:
            raise RuntimeError(f"GoCardless API request failed: {e}") from e

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
        """Create a GoCardless redirect flow for mandate setup.

        GoCardless uses redirect flows to set up Direct Debit mandates.
        The customer is redirected to GoCardless-hosted pages to authorize
        bank account access.
        """
        request_data: dict[str, Any] = {
            "redirect_flows": {
                "description": f"Invoice {invoice_number}",
                "session_token": str(payment_id),
                "success_redirect_url": success_url,
                "scheme": "bacs" if currency.upper() == "GBP" else "sepa_core",
                "metadata": {
                    "payment_id": str(payment_id),
                    "invoice_number": invoice_number,
                    **(metadata or {}),
                },
            }
        }

        if customer_email:
            request_data["redirect_flows"]["prefilled_customer"] = {
                "email": customer_email,
            }

        response = self._make_request("POST", "/redirect_flows", request_data)

        redirect_flow = response.get("redirect_flows", {})
        flow_id = redirect_flow.get("id", f"gc_rf_{payment_id}")
        redirect_url = redirect_flow.get("redirect_url", "")

        return CheckoutSession(
            provider_checkout_id=flow_id,
            checkout_url=redirect_url,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GoCardless webhook signature.

        GoCardless signs webhooks with HMAC-SHA256 using the webhook secret.
        The signature is sent in the Webhook-Signature header.
        """
        if not self.webhook_secret:
            return False

        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, payload: dict[str, Any]) -> WebhookResult:
        """Parse GoCardless webhook payload.

        GoCardless sends events with resource_type and action fields.
        Events cover mandates and payments:
        - mandates: created, submitted, active, failed, cancelled
        - payments: created, submitted, confirmed, paid_out, failed, cancelled
        """
        events = payload.get("events", [])
        if not events:
            return WebhookResult(event_type="gocardless.no_events")

        # Process the first event (GoCardless can batch events)
        event = events[0]
        resource_type = event.get("resource_type", "")
        action = event.get("action", "")
        event_type = f"{resource_type}.{action}"

        links = event.get("links", {})
        metadata = event.get("metadata", {})

        result = WebhookResult(
            event_type=event_type,
            metadata=metadata,
        )

        if resource_type == "payments":
            result.provider_payment_id = links.get("payment")
            result.provider_checkout_id = links.get("mandate")

            # Map GoCardless payment actions to our statuses
            status_map = {
                "confirmed": "succeeded",
                "paid_out": "succeeded",
                "failed": "failed",
                "cancelled": "canceled",
                "created": "pending",
                "submitted": "pending",
            }
            result.status = status_map.get(action)

            if action == "failed":
                detail = event.get("details", {})
                result.failure_reason = detail.get(
                    "description", detail.get("message", "Payment failed")
                )

        elif resource_type == "mandates":
            result.provider_checkout_id = links.get("mandate")

            mandate_status_map = {
                "active": "succeeded",
                "failed": "failed",
                "cancelled": "canceled",
                "created": "pending",
                "submitted": "pending",
            }
            result.status = mandate_status_map.get(action)

            if action == "failed":
                detail = event.get("details", {})
                result.failure_reason = detail.get(
                    "description", detail.get("message", "Mandate setup failed")
                )

        return result
