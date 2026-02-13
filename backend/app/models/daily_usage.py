"""DailyUsage model for pre-aggregated daily usage data."""

import uuid

from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.schema import ForeignKey, Index

from app.core.database import Base
from app.models.customer import UUIDType


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class DailyUsage(Base):
    """DailyUsage model — pre-aggregated usage data per subscription/metric/day."""

    __tablename__ = "daily_usages"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    subscription_id = Column(
        UUIDType,
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    billable_metric_id = Column(
        UUIDType,
        ForeignKey("billable_metrics.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    external_customer_id = Column(String(255), nullable=False)
    usage_date = Column(Date, nullable=False)
    usage_value = Column(Numeric(12, 4), nullable=False, default=0)
    events_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "billable_metric_id",
            "usage_date",
            name="uq_daily_usage_sub_metric_date",
        ),
        Index(
            "ix_daily_usages_sub_metric_date",
            "subscription_id",
            "billable_metric_id",
            "usage_date",
        ),
    )
