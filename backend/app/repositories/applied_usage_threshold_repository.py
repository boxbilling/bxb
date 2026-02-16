from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.applied_usage_threshold import AppliedUsageThreshold


class AppliedUsageThresholdRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[AppliedUsageThreshold]:
        query = (
            self.db.query(AppliedUsageThreshold)
            .filter(AppliedUsageThreshold.organization_id == organization_id)
        )
        query = apply_order_by(query, AppliedUsageThreshold, order_by)
        return query.offset(skip).limit(limit).all()

    def get_by_id(
        self, record_id: UUID, organization_id: UUID | None = None
    ) -> AppliedUsageThreshold | None:
        query = self.db.query(AppliedUsageThreshold).filter(AppliedUsageThreshold.id == record_id)
        if organization_id is not None:
            query = query.filter(AppliedUsageThreshold.organization_id == organization_id)
        return query.first()

    def get_by_subscription_id(self, subscription_id: UUID) -> list[AppliedUsageThreshold]:
        return (
            self.db.query(AppliedUsageThreshold)
            .filter(AppliedUsageThreshold.subscription_id == subscription_id)
            .all()
        )

    def has_been_crossed(
        self,
        threshold_id: UUID,
        subscription_id: UUID,
        period_start: datetime,
    ) -> bool:
        return (
            self.db.query(AppliedUsageThreshold)
            .filter(
                AppliedUsageThreshold.usage_threshold_id == threshold_id,
                AppliedUsageThreshold.subscription_id == subscription_id,
                AppliedUsageThreshold.crossed_at >= period_start,
            )
            .first()
            is not None
        )

    def create(
        self,
        usage_threshold_id: UUID,
        subscription_id: UUID,
        crossed_at: datetime,
        organization_id: UUID,
        invoice_id: UUID | None = None,
        lifetime_usage_amount_cents: Decimal | None = None,
    ) -> AppliedUsageThreshold:
        record = AppliedUsageThreshold(
            usage_threshold_id=usage_threshold_id,
            subscription_id=subscription_id,
            crossed_at=crossed_at,
            invoice_id=invoice_id,
            lifetime_usage_amount_cents=lifetime_usage_amount_cents,
            organization_id=organization_id,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
