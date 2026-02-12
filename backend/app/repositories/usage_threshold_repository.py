from uuid import UUID

from sqlalchemy.orm import Session

from app.models.usage_threshold import UsageThreshold
from app.schemas.usage_threshold import UsageThresholdCreate


class UsageThresholdRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[UsageThreshold]:
        return (
            self.db.query(UsageThreshold)
            .filter(UsageThreshold.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id(
        self, threshold_id: UUID, organization_id: UUID | None = None
    ) -> UsageThreshold | None:
        query = self.db.query(UsageThreshold).filter(UsageThreshold.id == threshold_id)
        if organization_id is not None:
            query = query.filter(UsageThreshold.organization_id == organization_id)
        return query.first()

    def get_by_plan_id(self, plan_id: UUID) -> list[UsageThreshold]:
        return self.db.query(UsageThreshold).filter(UsageThreshold.plan_id == plan_id).all()

    def get_by_subscription_id(self, subscription_id: UUID) -> list[UsageThreshold]:
        return (
            self.db.query(UsageThreshold)
            .filter(UsageThreshold.subscription_id == subscription_id)
            .all()
        )

    def create(self, data: UsageThresholdCreate, organization_id: UUID) -> UsageThreshold:
        threshold = UsageThreshold(
            plan_id=data.plan_id,
            subscription_id=data.subscription_id,
            amount_cents=data.amount_cents,
            currency=data.currency,
            recurring=data.recurring,
            threshold_display_name=data.threshold_display_name,
            organization_id=organization_id,
        )
        self.db.add(threshold)
        self.db.commit()
        self.db.refresh(threshold)
        return threshold

    def delete(self, threshold_id: UUID, organization_id: UUID) -> bool:
        threshold = self.get_by_id(threshold_id, organization_id)
        if not threshold:
            return False
        self.db.delete(threshold)
        self.db.commit()
        return True
