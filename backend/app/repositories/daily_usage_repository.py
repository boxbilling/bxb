"""Daily usage repository for data access."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.daily_usage import DailyUsage
from app.schemas.daily_usage import DailyUsageCreate


class DailyUsageRepository:
    """Repository for DailyUsage model."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, daily_usage_id: UUID) -> DailyUsage | None:
        """Get a daily usage record by ID."""
        return self.db.query(DailyUsage).filter(DailyUsage.id == daily_usage_id).first()

    def get_by_subscription_and_metric(
        self,
        subscription_id: UUID,
        billable_metric_id: UUID,
        usage_date: date,
    ) -> DailyUsage | None:
        """Get a daily usage record by subscription, metric, and date."""
        return (
            self.db.query(DailyUsage)
            .filter(
                DailyUsage.subscription_id == subscription_id,
                DailyUsage.billable_metric_id == billable_metric_id,
                DailyUsage.usage_date == usage_date,
            )
            .first()
        )

    def get_for_period(
        self,
        subscription_id: UUID,
        billable_metric_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[DailyUsage]:
        """Get daily usage records for a subscription/metric within a date range."""
        return (
            self.db.query(DailyUsage)
            .filter(
                DailyUsage.subscription_id == subscription_id,
                DailyUsage.billable_metric_id == billable_metric_id,
                DailyUsage.usage_date >= start_date,
                DailyUsage.usage_date <= end_date,
            )
            .order_by(DailyUsage.usage_date)
            .all()
        )

    def sum_for_period(
        self,
        subscription_id: UUID,
        billable_metric_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Decimal:
        """Sum daily usage values for a subscription/metric within a date range."""
        records = self.get_for_period(
            subscription_id, billable_metric_id, start_date, end_date
        )
        return sum((Decimal(str(r.usage_value)) for r in records), Decimal("0"))

    def upsert(self, data: DailyUsageCreate) -> DailyUsage:
        """Create or update a daily usage record.

        If a record already exists for the same subscription/metric/date,
        update it. Otherwise, create a new one.
        """
        existing = self.get_by_subscription_and_metric(
            data.subscription_id,
            data.billable_metric_id,
            data.usage_date,
        )
        if existing:
            existing.usage_value = data.usage_value  # type: ignore[assignment]
            existing.events_count = data.events_count  # type: ignore[assignment]
            existing.external_customer_id = data.external_customer_id  # type: ignore[assignment]
            self.db.commit()
            self.db.refresh(existing)
            return existing

        record = DailyUsage(
            subscription_id=data.subscription_id,
            billable_metric_id=data.billable_metric_id,
            external_customer_id=data.external_customer_id,
            usage_date=data.usage_date,
            usage_value=data.usage_value,
            events_count=data.events_count,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete(self, daily_usage_id: UUID) -> bool:
        """Delete a daily usage record."""
        record = self.get_by_id(daily_usage_id)
        if not record:
            return False
        self.db.delete(record)
        self.db.commit()
        return True
