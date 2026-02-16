"""Webhook repository for data access."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.webhook import Webhook
from app.models.webhook_delivery_attempt import WebhookDeliveryAttempt


class WebhookRepository:
    """Repository for Webhook model."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        webhook_endpoint_id: UUID,
        webhook_type: str,
        payload: dict[str, Any],
        object_type: str | None = None,
        object_id: UUID | None = None,
    ) -> Webhook:
        """Create a new webhook record."""
        webhook = Webhook(
            webhook_endpoint_id=webhook_endpoint_id,
            webhook_type=webhook_type,
            object_type=object_type,
            object_id=object_id,
            payload=payload,
        )
        self.db.add(webhook)
        self.db.commit()
        self.db.refresh(webhook)
        return webhook

    def get_by_id(self, webhook_id: UUID) -> Webhook | None:
        """Get a webhook by ID."""
        return self.db.query(Webhook).filter(Webhook.id == webhook_id).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        webhook_type: str | None = None,
        status: str | None = None,
        order_by: str | None = None,
    ) -> list[Webhook]:
        """Get all webhooks with optional filters."""
        query = self.db.query(Webhook)
        if webhook_type:
            query = query.filter(Webhook.webhook_type == webhook_type)
        if status:
            query = query.filter(Webhook.status == status)
        query = apply_order_by(query, Webhook, order_by)
        return query.offset(skip).limit(limit).all()

    def count(self) -> int:
        """Count all webhooks."""
        return self.db.query(func.count(Webhook.id)).scalar() or 0

    def get_pending(self) -> list[Webhook]:
        """Get all pending webhooks."""
        return (
            self.db.query(Webhook)
            .filter(Webhook.status == "pending")
            .order_by(Webhook.created_at.asc())
            .all()
        )

    def get_failed_for_retry(self) -> list[Webhook]:
        """Get failed webhooks eligible for retry (retries < max_retries)."""
        return (
            self.db.query(Webhook)
            .filter(
                Webhook.status == "failed",
                Webhook.retries < Webhook.max_retries,
            )
            .order_by(Webhook.created_at.asc())
            .all()
        )

    def mark_succeeded(self, webhook_id: UUID, http_status: int) -> Webhook | None:
        """Mark a webhook as succeeded."""
        webhook = self.get_by_id(webhook_id)
        if not webhook:
            return None

        webhook.status = "succeeded"  # type: ignore[assignment]
        webhook.http_status = http_status  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(webhook)
        return webhook

    def mark_failed(
        self,
        webhook_id: UUID,
        http_status: int | None = None,
        response: str | None = None,
    ) -> Webhook | None:
        """Mark a webhook as failed."""
        webhook = self.get_by_id(webhook_id)
        if not webhook:
            return None

        webhook.status = "failed"  # type: ignore[assignment]
        webhook.http_status = http_status  # type: ignore[assignment]
        webhook.response = response  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(webhook)
        return webhook

    def delivery_stats_by_endpoint(self) -> list[dict[str, Any]]:
        """Get delivery stats (total, succeeded, failed) grouped by endpoint."""
        rows = (
            self.db.query(
                Webhook.webhook_endpoint_id,
                func.count(Webhook.id).label("total"),
                func.sum(
                    case((Webhook.status == "succeeded", 1), else_=0)
                ).label("succeeded"),
                func.sum(
                    case((Webhook.status == "failed", 1), else_=0)
                ).label("failed"),
            )
            .group_by(Webhook.webhook_endpoint_id)
            .all()
        )
        return [
            {
                "endpoint_id": str(row.webhook_endpoint_id),
                "total": row.total,
                "succeeded": int(row.succeeded or 0),
                "failed": int(row.failed or 0),
            }
            for row in rows
        ]

    def increment_retry(self, webhook_id: UUID) -> Webhook | None:
        """Increment the retry count and update last_retried_at."""
        webhook = self.get_by_id(webhook_id)
        if not webhook:
            return None

        webhook.retries = webhook.retries + 1  # type: ignore[assignment]
        webhook.last_retried_at = datetime.now()  # type: ignore[assignment]
        webhook.status = "pending"  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(webhook)
        return webhook

    def create_delivery_attempt(
        self,
        webhook_id: UUID,
        attempt_number: int,
        success: bool,
        http_status: int | None = None,
        response_body: str | None = None,
        error_message: str | None = None,
    ) -> WebhookDeliveryAttempt:
        """Record a delivery attempt for a webhook."""
        attempt = WebhookDeliveryAttempt(
            webhook_id=webhook_id,
            attempt_number=attempt_number,
            http_status=http_status,
            response_body=response_body,
            success=success,
            error_message=error_message,
        )
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    def get_delivery_attempts(self, webhook_id: UUID) -> list[WebhookDeliveryAttempt]:
        """Get all delivery attempts for a webhook, ordered by attempt number."""
        return (
            self.db.query(WebhookDeliveryAttempt)
            .filter(WebhookDeliveryAttempt.webhook_id == webhook_id)
            .order_by(WebhookDeliveryAttempt.attempt_number.asc())
            .all()
        )
