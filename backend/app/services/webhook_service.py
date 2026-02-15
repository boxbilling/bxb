"""Webhook delivery service for sending and managing webhooks."""

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.webhook import Webhook
from app.repositories.webhook_endpoint_repository import WebhookEndpointRepository
from app.repositories.webhook_repository import WebhookRepository

logger = logging.getLogger(__name__)

# Supported webhook event types
WEBHOOK_EVENT_TYPES = [
    "invoice.created",
    "invoice.finalized",
    "invoice.paid",
    "invoice.voided",
    "payment.created",
    "payment.succeeded",
    "payment.failed",
    "subscription.created",
    "subscription.terminated",
    "subscription.canceled",
    "subscription.started",
    "subscription.paused",
    "subscription.resumed",
    "subscription.plan_changed",
    "subscription.trial_ended",
    "customer.created",
    "customer.updated",
    "credit_note.created",
    "credit_note.finalized",
    "credit_note.refund.succeeded",
    "credit_note.refund.failed",
    "wallet.created",
    "wallet.terminated",
    "wallet.transaction.created",
    "usage_threshold.crossed",
    "usage_alert.triggered",
]


def generate_hmac_signature(payload_bytes: bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for a webhook payload.

    Args:
        payload_bytes: The raw payload bytes to sign.
        secret: The secret key for HMAC generation.

    Returns:
        Hex-encoded HMAC-SHA256 signature.
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


class WebhookService:
    """Service for webhook delivery and management."""

    def __init__(self, db: Session):
        self.db = db
        self.endpoint_repo = WebhookEndpointRepository(db)
        self.webhook_repo = WebhookRepository(db)

    def send_webhook(
        self,
        webhook_type: str,
        object_type: str | None = None,
        object_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> list[Webhook]:
        """Create webhook records for all active endpoints.

        Args:
            webhook_type: Event type (e.g., "invoice.created").
            object_type: Type of the resource that triggered the event.
            object_id: ID of the resource that triggered the event.
            payload: Full event payload to deliver.

        Returns:
            List of created Webhook records.
        """
        if payload is None:
            payload = {}

        active_endpoints = self.endpoint_repo.get_active()
        webhooks: list[Webhook] = []

        for endpoint in active_endpoints:
            webhook = self.webhook_repo.create(
                webhook_endpoint_id=endpoint.id,  # type: ignore[arg-type]
                webhook_type=webhook_type,
                object_type=object_type,
                object_id=object_id,
                payload=payload,
            )
            webhooks.append(webhook)

        return webhooks

    def deliver_webhook(self, webhook_id: UUID) -> bool:
        """Deliver a webhook to its endpoint.

        Loads the webhook and endpoint, generates a signature, POSTs the
        payload, and updates the webhook status based on the response.
        Records each delivery attempt in the delivery_attempts table.

        Args:
            webhook_id: ID of the webhook to deliver.

        Returns:
            True if delivery succeeded, False otherwise.
        """
        webhook = self.webhook_repo.get_by_id(webhook_id)
        if not webhook:
            logger.error("Webhook %s not found", webhook_id)
            return False

        attempt_number = int(webhook.retries)

        endpoint = self.endpoint_repo.get_by_id(webhook.webhook_endpoint_id)  # type: ignore[arg-type]
        if not endpoint:
            logger.error(
                "Endpoint %s not found for webhook %s",
                webhook.webhook_endpoint_id,
                webhook_id,
            )
            self.webhook_repo.mark_failed(webhook_id, response="Endpoint not found")
            self.webhook_repo.create_delivery_attempt(
                webhook_id=webhook_id,
                attempt_number=attempt_number,
                success=False,
                error_message="Endpoint not found",
            )
            return False

        payload_bytes = json.dumps(webhook.payload, default=str).encode("utf-8")
        signature = generate_hmac_signature(payload_bytes, settings.webhook_secret)

        headers = {
            "Content-Type": "application/json",
            "X-Bxb-Signature": signature,
            "X-Bxb-Signature-Algorithm": endpoint.signature_algo,
            "X-Bxb-Webhook-Id": str(webhook.id),
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    str(endpoint.url),
                    content=payload_bytes,
                    headers={str(k): str(v) for k, v in headers.items()},
                )

            if 200 <= resp.status_code < 300:
                self.webhook_repo.mark_succeeded(webhook_id, resp.status_code)
                self.webhook_repo.create_delivery_attempt(
                    webhook_id=webhook_id,
                    attempt_number=attempt_number,
                    success=True,
                    http_status=resp.status_code,
                    response_body=resp.text[:1000] if resp.text else None,
                )
                return True
            else:
                response_text = resp.text[:1000] if resp.text else None
                self.webhook_repo.mark_failed(
                    webhook_id,
                    http_status=resp.status_code,
                    response=response_text,
                )
                self.webhook_repo.create_delivery_attempt(
                    webhook_id=webhook_id,
                    attempt_number=attempt_number,
                    success=False,
                    http_status=resp.status_code,
                    response_body=response_text,
                )
                return False

        except httpx.HTTPError as exc:
            logger.warning("Webhook delivery failed for %s: %s", webhook_id, exc)
            error_msg = str(exc)[:1000]
            self.webhook_repo.mark_failed(
                webhook_id,
                response=error_msg,
            )
            self.webhook_repo.create_delivery_attempt(
                webhook_id=webhook_id,
                attempt_number=attempt_number,
                success=False,
                error_message=error_msg,
            )
            return False

    def retry_failed_webhooks(self) -> int:
        """Retry failed webhooks with exponential backoff.

        Finds all failed webhooks eligible for retry (retries < max_retries)
        and re-delivers those whose backoff period has elapsed.
        Backoff: 2^retries minutes.

        Returns:
            Number of webhooks retried.
        """
        failed_webhooks = self.webhook_repo.get_failed_for_retry()
        retried_count = 0
        now = datetime.now(UTC)

        for webhook in failed_webhooks:
            backoff_minutes = 2 ** int(webhook.retries)
            if webhook.last_retried_at:
                next_retry_at = webhook.last_retried_at.replace(tzinfo=UTC) + timedelta(
                    minutes=backoff_minutes
                )
                if now < next_retry_at:
                    continue

            self.webhook_repo.increment_retry(webhook.id)  # type: ignore[arg-type]
            self.deliver_webhook(webhook.id)  # type: ignore[arg-type]
            retried_count += 1

        return retried_count
