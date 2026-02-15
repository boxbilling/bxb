from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entitlement import Entitlement
from app.models.feature import Feature
from app.schemas.feature import FeatureCreate, FeatureUpdate


class FeatureRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Feature]:
        return (
            self.db.query(Feature)
            .filter(Feature.organization_id == organization_id)
            .order_by(Feature.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, organization_id: UUID) -> int:
        return (
            self.db.query(func.count(Feature.id))
            .filter(Feature.organization_id == organization_id)
            .scalar()
            or 0
        )

    def get_by_id(
        self, feature_id: UUID, organization_id: UUID | None = None
    ) -> Feature | None:
        query = self.db.query(Feature).filter(Feature.id == feature_id)
        if organization_id is not None:
            query = query.filter(Feature.organization_id == organization_id)
        return query.first()

    def get_by_code(
        self, code: str, organization_id: UUID
    ) -> Feature | None:
        return (
            self.db.query(Feature)
            .filter(
                Feature.code == code,
                Feature.organization_id == organization_id,
            )
            .first()
        )

    def create(
        self, data: FeatureCreate, organization_id: UUID
    ) -> Feature:
        feature = Feature(
            code=data.code,
            name=data.name,
            description=data.description,
            feature_type=data.feature_type.value,
            organization_id=organization_id,
        )
        self.db.add(feature)
        self.db.commit()
        self.db.refresh(feature)
        return feature

    def update(
        self,
        feature_id: UUID,
        data: FeatureUpdate,
        organization_id: UUID,
    ) -> Feature | None:
        feature = self.get_by_id(feature_id, organization_id)
        if not feature:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(feature, key, value)
        self.db.commit()
        self.db.refresh(feature)
        return feature

    def delete(self, feature_id: UUID, organization_id: UUID) -> bool:
        feature = self.get_by_id(feature_id, organization_id)
        if not feature:
            return False
        self.db.delete(feature)
        self.db.commit()
        return True

    def code_exists(self, code: str, organization_id: UUID) -> bool:
        return self.get_by_code(code, organization_id) is not None

    def plan_counts(self, organization_id: UUID) -> dict[str, int]:
        """Return a mapping of feature_id -> count of distinct plans with entitlements."""
        rows = (
            self.db.query(
                Entitlement.feature_id,
                func.count(func.distinct(Entitlement.plan_id)),
            )
            .filter(Entitlement.organization_id == organization_id)
            .group_by(Entitlement.feature_id)
            .all()
        )
        return {str(feature_id): int(cnt) for feature_id, cnt in rows}
