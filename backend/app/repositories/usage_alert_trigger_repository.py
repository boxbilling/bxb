from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.usage_alert_trigger import UsageAlertTrigger


class UsageAlertTriggerRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        usage_alert_id: UUID,
        current_usage: Decimal,
        threshold_value: Decimal,
        metric_code: str,
        triggered_at: datetime,
    ) -> UsageAlertTrigger:
        trigger = UsageAlertTrigger(
            usage_alert_id=usage_alert_id,
            current_usage=current_usage,
            threshold_value=threshold_value,
            metric_code=metric_code,
            triggered_at=triggered_at,
        )
        self.db.add(trigger)
        self.db.commit()
        self.db.refresh(trigger)
        return trigger

    def get_by_alert_id(
        self,
        usage_alert_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[UsageAlertTrigger]:
        return (
            self.db.query(UsageAlertTrigger)
            .filter(UsageAlertTrigger.usage_alert_id == usage_alert_id)
            .order_by(UsageAlertTrigger.triggered_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_alert_id(self, usage_alert_id: UUID) -> int:
        return (
            self.db.query(func.count(UsageAlertTrigger.id))
            .filter(UsageAlertTrigger.usage_alert_id == usage_alert_id)
            .scalar()
            or 0
        )
