"""Adyen payment provider implementation.

Adyen uses a session-based checkout flow:
1. Create a payment session via the /sessions endpoint
2. Customer completes payment on Adyen-hosted page
3. Adyen sends notification webhooks for payment lifecycle events
"""

import base64
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


class AdyenProvider(PaymentProviderBase):
    """Adyen payment provider.

    Adyen uses sessions for payment initiation and HMAC-SHA256 for
    webhook signature verification.
    """

    def __init__(
        self,
        api_key: str | None = None,
        merchant_account: str | None = None,
        webhook_hmac_key: str | None = None,
        environment: str | None = None,
        live_url_prefix: str | None = None,
    ):
        self.api_key = api_key or settings.adyen_api_key
        self.merchant_account = merchant_account or settings.adyen_merchant_account
        self.webhook_hmac_key = webhook_hmac_key or settings.adyen_webhook_hmac_key
        self.environment = environment or settings.adyen_environment
        self.live_url_prefix = live_url_prefix or settings.adyen_live_url_prefix

        if self.environment == "live" and self.live_url_prefix:
            self._base_url = (
                f"https://{self.live_url_prefix}-checkout-live.adyenpayments.com/checkout/v71"
            )
        else:
            self._base_url = "https://checkout-test.adyen.com/v71"

    @property
    def provider_name(self) -> PaymentProvider:
        return PaymentProvider.ADYEN

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to the Adyen API."""
        url = f"{self._base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": self.api_key,
        }

        body = json.dumps(data).encode() if data else None
        request = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(request, timeout=30) as response:
                result: dict[str, Any] = json.loads(response.read().decode())
                return result
        except URLError as e:
            raise RuntimeError(f"Adyen API request failed: {e}") from e

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
        """Create an Adyen payment session.

        Uses the Adyen Sessions API to create a payment session.
        """
        amount_minor = int(amount * 100)

        request_data: dict[str, Any] = {
            "merchantAccount": self.merchant_account,
            "amount": {
                "value": amount_minor,
                "currency": currency.upper(),
            },
            "reference": str(payment_id),
            "returnUrl": success_url,
            "metadata": {
                "payment_id": str(payment_id),
                "invoice_number": invoice_number,
                **(metadata or {}),
            },
        }

        if customer_email:
            request_data["shopperEmail"] = customer_email

        response = self._make_request("POST", "/sessions", request_data)

        session_id = response.get("id", f"adyen_{payment_id}")
        session_url = response.get("url", "")
        if not session_url:
            session_url = response.get("redirectUrl", "")

        return CheckoutSession(
            provider_checkout_id=session_id,
            checkout_url=session_url,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Adyen webhook HMAC signature.

        Adyen uses HMAC-SHA256 with a base64-encoded key. The signature
        is base64-encoded and sent in the request payload or header.
        """
        if not self.webhook_hmac_key:
            return False

        try:
            key_bytes = bytes.fromhex(self.webhook_hmac_key)
        except ValueError:
            key_bytes = self.webhook_hmac_key.encode()

        expected = base64.b64encode(hmac.new(key_bytes, payload, hashlib.sha256).digest()).decode()

        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, payload: dict[str, Any]) -> WebhookResult:
        """Parse Adyen webhook notification.

        Adyen sends notifications with notificationItems containing
        eventCode and success fields.
        """
        items = payload.get("notificationItems", [])
        if not items:
            return WebhookResult(event_type="adyen.no_items")

        item = items[0].get("NotificationRequestItem", {})
        event_code = item.get("eventCode", "")
        success = item.get("success", "false") == "true"
        psp_reference = item.get("pspReference")
        merchant_reference = item.get("merchantReference")

        # Build metadata from additional data
        additional_data = item.get("additionalData", {})
        meta: dict[str, Any] = {}
        if merchant_reference:
            meta["payment_id"] = merchant_reference
        if additional_data:
            meta["additional_data"] = additional_data

        result = WebhookResult(
            event_type=f"adyen.{event_code}",
            provider_payment_id=psp_reference,
            provider_checkout_id=merchant_reference,
            metadata=meta,
        )

        # Map Adyen event codes to our statuses
        if event_code == "AUTHORISATION":
            result.status = "succeeded" if success else "failed"
            if not success:
                result.failure_reason = item.get("reason", "Payment authorization failed")

        elif event_code == "CANCELLATION":
            result.status = "canceled"

        elif event_code == "REFUND":
            result.status = "refunded" if success else None

        elif event_code == "CAPTURE":
            result.status = "succeeded" if success else "failed"
            if not success:
                result.failure_reason = item.get("reason", "Payment capture failed")

        return result
