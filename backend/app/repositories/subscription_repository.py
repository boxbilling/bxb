from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate


class SubscriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Subscription]:
        return self.db.query(Subscription).offset(skip).limit(limit).all()

    def get_by_id(self, subscription_id: UUID) -> Subscription | None:
        return self.db.query(Subscription).filter(Subscription.id == subscription_id).first()

    def get_by_external_id(self, external_id: str) -> Subscription | None:
        return self.db.query(Subscription).filter(Subscription.external_id == external_id).first()

    def get_by_customer_id(self, customer_id: UUID) -> list[Subscription]:
        return self.db.query(Subscription).filter(Subscription.customer_id == customer_id).all()

    def create(self, data: SubscriptionCreate) -> Subscription:
        subscription = Subscription(
            external_id=data.external_id,
            customer_id=data.customer_id,
            plan_id=data.plan_id,
            status=SubscriptionStatus.PENDING.value,
            started_at=data.started_at,
            billing_time=data.billing_time.value,
            trial_period_days=data.trial_period_days,
            subscription_at=data.subscription_at,
            pay_in_advance=data.pay_in_advance,
            on_termination_action=data.on_termination_action.value,
        )
        # If started_at is provided and in the past or now, set status to ACTIVE
        if data.started_at is not None and data.started_at <= datetime.now(UTC):
            subscription.status = SubscriptionStatus.ACTIVE.value  # type: ignore[assignment]
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def update(self, subscription_id: UUID, data: SubscriptionUpdate) -> Subscription | None:
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None
        update_data = data.model_dump(exclude_unset=True)
        # Convert enum to string value if present, remove None status to avoid setting NULL
        if "status" in update_data:
            if update_data["status"] is not None:
                update_data["status"] = update_data["status"].value
            else:
                del update_data["status"]  # Don't try to set status to NULL
        # Convert billing_time enum to string value if present
        if "billing_time" in update_data:
            if update_data["billing_time"] is not None:
                update_data["billing_time"] = update_data["billing_time"].value
            else:
                del update_data["billing_time"]
        # Convert on_termination_action enum to string value if present
        if "on_termination_action" in update_data:
            if update_data["on_termination_action"] is not None:
                update_data["on_termination_action"] = update_data["on_termination_action"].value
            else:
                del update_data["on_termination_action"]
        for key, value in update_data.items():
            setattr(subscription, key, value)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def delete(self, subscription_id: UUID) -> bool:
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return False
        self.db.delete(subscription)
        self.db.commit()
        return True

    def terminate(self, subscription_id: UUID) -> Subscription | None:
        """Terminate a subscription."""
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None
        subscription.status = SubscriptionStatus.TERMINATED.value  # type: ignore[assignment]
        subscription.ending_at = datetime.now(UTC)  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def cancel(self, subscription_id: UUID) -> Subscription | None:
        """Cancel a subscription."""
        subscription = self.get_by_id(subscription_id)
        if not subscription:
            return None
        subscription.status = SubscriptionStatus.CANCELED.value  # type: ignore[assignment]
        subscription.canceled_at = datetime.now(UTC)  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def external_id_exists(self, external_id: str) -> bool:
        """Check if a subscription with the given external_id already exists."""
        query = self.db.query(Subscription).filter(Subscription.external_id == external_id)
        return query.first() is not None
