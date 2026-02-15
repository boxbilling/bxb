"""Entitlement service for checking subscription entitlements."""

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.repositories.entitlement_repository import EntitlementRepository
from app.repositories.feature_repository import FeatureRepository
from app.repositories.subscription_repository import SubscriptionRepository


class EntitlementCheckResult(BaseModel):
    feature_code: str
    has_access: bool
    value: str | None


class EntitlementService:
    """Service for checking entitlements against subscriptions."""

    def __init__(self, db: Session):
        self.db = db
        self.subscription_repo = SubscriptionRepository(db)
        self.entitlement_repo = EntitlementRepository(db)
        self.feature_repo = FeatureRepository(db)

    def check_entitlement(
        self, subscription_id: UUID, feature_code: str
    ) -> EntitlementCheckResult:
        """Check whether a subscription has access to a feature.

        Looks up the subscription's plan, finds the entitlement for the
        feature, and returns the access result.

        Raises:
            ValueError: If subscription or feature not found.
        """
        subscription = self.subscription_repo.get_by_id(subscription_id)
        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        organization_id = UUID(str(subscription.organization_id))
        feature = self.feature_repo.get_by_code(feature_code, organization_id)
        if not feature:
            raise ValueError(f"Feature '{feature_code}' not found")

        plan_id = UUID(str(subscription.plan_id))
        entitlements = self.entitlement_repo.get_by_plan_id(
            plan_id, organization_id
        )

        feature_id = UUID(str(feature.id))
        for ent in entitlements:
            if ent.feature_id == feature_id:
                return EntitlementCheckResult(
                    feature_code=feature_code,
                    has_access=True,
                    value=str(ent.value),
                )

        return EntitlementCheckResult(
            feature_code=feature_code,
            has_access=False,
            value=None,
        )
