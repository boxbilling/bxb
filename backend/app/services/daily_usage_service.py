"""Daily usage service for pre-aggregating daily usage data."""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.charge import Charge
from app.models.customer import Customer
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.daily_usage_repository import DailyUsageRepository
from app.schemas.daily_usage import DailyUsageCreate
from app.services.usage_aggregation import UsageAggregationService

logger = logging.getLogger(__name__)


class DailyUsageService:
    """Service for aggregating and querying daily usage data."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = DailyUsageRepository(db)
        self.usage_service = UsageAggregationService(db)

    def aggregate_daily_usage(self, target_date: date | None = None) -> int:
        """Aggregate usage for all active subscriptions for a given date.

        Args:
            target_date: The date to aggregate for. Defaults to yesterday.

        Returns:
            Number of daily usage records upserted.
        """
        if target_date is None:
            target_date = (datetime.now(UTC) - timedelta(days=1)).date()

        # Convert date to datetime range for aggregation
        from_ts = datetime(target_date.year, target_date.month, target_date.day)
        to_ts = from_ts + timedelta(days=1)

        # Find all active subscriptions
        subscriptions = (
            self.db.query(Subscription)
            .filter(Subscription.status == SubscriptionStatus.ACTIVE.value)
            .all()
        )

        count = 0
        for subscription in subscriptions:
            count += self._aggregate_for_subscription(subscription, target_date, from_ts, to_ts)

        if count > 0:
            logger.info("Aggregated %d daily usage records for %s", count, target_date)
        return count

    def _aggregate_for_subscription(
        self,
        subscription: Subscription,
        target_date: date,
        from_ts: datetime,
        to_ts: datetime,
    ) -> int:
        """Aggregate usage for a single subscription's charges.

        Returns:
            Number of records upserted.
        """
        # Get the customer's external_id
        customer = (
            self.db.query(Customer)
            .filter(Customer.id == subscription.customer_id)
            .first()
        )
        if not customer:
            return 0

        external_customer_id = str(customer.external_id)

        # Get charges for the subscription's plan
        charges = (
            self.db.query(Charge)
            .filter(Charge.plan_id == subscription.plan_id)
            .all()
        )

        count = 0
        for charge in charges:
            metric_id = UUID(str(charge.billable_metric_id))
            # Look up the billable metric to get its code
            from app.models.billable_metric import BillableMetric

            metric = (
                self.db.query(BillableMetric)
                .filter(BillableMetric.id == metric_id)
                .first()
            )
            if not metric:
                continue

            try:
                result = self.usage_service.aggregate_usage_with_count(
                    external_customer_id=external_customer_id,
                    code=str(metric.code),
                    from_timestamp=from_ts,
                    to_timestamp=to_ts,
                )
            except ValueError:
                logger.warning(
                    "Failed to aggregate usage for subscription %s, metric %s",
                    subscription.id,
                    metric.code,
                )
                continue

            self.repo.upsert(
                DailyUsageCreate(
                    subscription_id=UUID(str(subscription.id)),
                    billable_metric_id=metric_id,
                    external_customer_id=external_customer_id,
                    usage_date=target_date,
                    usage_value=result.value,
                    events_count=result.events_count,
                )
            )
            count += 1

        return count

    def get_usage_for_period(
        self,
        subscription_id: UUID,
        billable_metric_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        """Get summed usage for a subscription/metric over a date range.

        This is faster than re-aggregating events because it uses
        pre-computed daily values.

        Args:
            subscription_id: The subscription to query.
            billable_metric_id: The billable metric to query.
            start_date: Start of the date range (inclusive).
            end_date: End of the date range (inclusive).

        Returns:
            Summed usage value for the period.
        """
        return self.repo.sum_for_period(
            subscription_id, billable_metric_id, start_date, end_date
        )
