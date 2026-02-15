"""Service for checking usage monitoring alerts."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.usage_alert import UsageAlert
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.usage_alert_repository import UsageAlertRepository
from app.services.usage_aggregation import UsageAggregationService
from app.services.webhook_service import WebhookService


class UsageAlertService:
    """Service for checking usage alerts and triggering webhook notifications."""

    def __init__(self, db: Session):
        self.db = db
        self.alert_repo = UsageAlertRepository(db)
        self.metric_repo = BillableMetricRepository(db)
        self.usage_service = UsageAggregationService(db)
        self.webhook_service = WebhookService(db)

    def check_alerts(
        self,
        subscription_id: UUID,
        external_customer_id: str,
        billing_period_start: datetime,
        billing_period_end: datetime,
    ) -> list[UsageAlert]:
        """Check if any usage alerts should fire for a subscription.

        For each alert on the subscription, aggregates current usage for the
        alert's metric, compares to threshold. For recurring alerts, checks if
        usage / threshold > number of times already triggered.

        Args:
            subscription_id: The subscription to check alerts for.
            external_customer_id: The external customer ID for usage lookup.
            billing_period_start: Start of the current billing period.
            billing_period_end: End of the current billing period.

        Returns:
            List of UsageAlert records that were triggered.
        """
        alerts = self.alert_repo.get_by_subscription_id(subscription_id)
        if not alerts:
            return []

        triggered: list[UsageAlert] = []
        now = datetime.now(UTC)

        for alert in alerts:
            metric_id = UUID(str(alert.billable_metric_id))
            metric = self.metric_repo.get_by_id(metric_id)
            if not metric:
                continue

            metric_code = str(metric.code)
            current_usage = self.usage_service.aggregate_usage(
                external_customer_id=external_customer_id,
                code=metric_code,
                from_timestamp=billing_period_start,
                to_timestamp=billing_period_end,
            )

            threshold = Decimal(str(alert.threshold_value))
            times_triggered = int(alert.times_triggered or 0)

            if alert.recurring:
                # For recurring: fire every time usage crosses another multiple
                expected_triggers = int(current_usage // threshold) if threshold > 0 else 0
                if expected_triggers > times_triggered:
                    alert.times_triggered = expected_triggers  # type: ignore[assignment]
                    alert.triggered_at = now  # type: ignore[assignment]
                    self.db.commit()
                    self.db.refresh(alert)
                    triggered.append(alert)

                    self._send_alert_webhook(
                        alert=alert,
                        metric_code=metric_code,
                        current_usage=current_usage,
                        subscription_id=subscription_id,
                    )
            else:
                # Non-recurring: fire once when usage crosses threshold
                if times_triggered == 0 and current_usage >= threshold:
                    alert.times_triggered = 1  # type: ignore[assignment]
                    alert.triggered_at = now  # type: ignore[assignment]
                    self.db.commit()
                    self.db.refresh(alert)
                    triggered.append(alert)

                    self._send_alert_webhook(
                        alert=alert,
                        metric_code=metric_code,
                        current_usage=current_usage,
                        subscription_id=subscription_id,
                    )

        return triggered

    def _send_alert_webhook(
        self,
        alert: UsageAlert,
        metric_code: str,
        current_usage: Decimal,
        subscription_id: UUID,
    ) -> None:
        """Send a webhook notification for a triggered alert."""
        self.webhook_service.send_webhook(
            webhook_type="usage_alert.triggered",
            object_type="usage_alert",
            object_id=UUID(str(alert.id)),
            payload={
                "usage_alert_id": str(alert.id),
                "subscription_id": str(subscription_id),
                "billable_metric_code": metric_code,
                "threshold_value": str(alert.threshold_value),
                "current_usage": str(current_usage),
                "recurring": alert.recurring,
                "triggered_at": str(alert.triggered_at),
            },
        )
