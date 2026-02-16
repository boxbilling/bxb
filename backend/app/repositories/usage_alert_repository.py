from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.usage_alert import UsageAlert
from app.schemas.usage_alert import UsageAlertCreate, UsageAlertUpdate


class UsageAlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        subscription_id: UUID | None = None,
        order_by: str | None = None,
    ) -> list[UsageAlert]:
        query = self.db.query(UsageAlert).filter(
            UsageAlert.organization_id == organization_id
        )
        if subscription_id is not None:
            query = query.filter(UsageAlert.subscription_id == subscription_id)
        query = apply_order_by(query, UsageAlert, order_by)
        return query.offset(skip).limit(limit).all()

    def count(
        self, organization_id: UUID, subscription_id: UUID | None = None
    ) -> int:
        query = self.db.query(func.count(UsageAlert.id)).filter(
            UsageAlert.organization_id == organization_id
        )
        if subscription_id is not None:
            query = query.filter(UsageAlert.subscription_id == subscription_id)
        return query.scalar() or 0

    def get_by_id(
        self, alert_id: UUID, organization_id: UUID | None = None
    ) -> UsageAlert | None:
        query = self.db.query(UsageAlert).filter(UsageAlert.id == alert_id)
        if organization_id is not None:
            query = query.filter(UsageAlert.organization_id == organization_id)
        return query.first()

    def get_by_subscription_id(self, subscription_id: UUID) -> list[UsageAlert]:
        return (
            self.db.query(UsageAlert)
            .filter(UsageAlert.subscription_id == subscription_id)
            .all()
        )

    def create(self, data: UsageAlertCreate, organization_id: UUID) -> UsageAlert:
        alert = UsageAlert(
            subscription_id=data.subscription_id,
            billable_metric_id=data.billable_metric_id,
            threshold_value=data.threshold_value,
            recurring=data.recurring,
            name=data.name,
            organization_id=organization_id,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def update(
        self, alert_id: UUID, data: UsageAlertUpdate, organization_id: UUID
    ) -> UsageAlert | None:
        alert = self.get_by_id(alert_id, organization_id)
        if not alert:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(alert, key, value)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def delete(self, alert_id: UUID, organization_id: UUID) -> bool:
        alert = self.get_by_id(alert_id, organization_id)
        if not alert:
            return False
        self.db.delete(alert)
        self.db.commit()
        return True
