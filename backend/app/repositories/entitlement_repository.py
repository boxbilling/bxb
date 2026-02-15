from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entitlement import Entitlement
from app.schemas.entitlement import EntitlementCreate, EntitlementUpdate


class EntitlementRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[Entitlement]:
        return (
            self.db.query(Entitlement)
            .filter(Entitlement.organization_id == organization_id)
            .order_by(Entitlement.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(
        self, organization_id: UUID, plan_id: UUID | None = None
    ) -> int:
        query = self.db.query(func.count(Entitlement.id)).filter(
            Entitlement.organization_id == organization_id
        )
        if plan_id is not None:
            query = query.filter(Entitlement.plan_id == plan_id)
        return query.scalar() or 0

    def get_by_id(
        self, entitlement_id: UUID, organization_id: UUID | None = None
    ) -> Entitlement | None:
        query = self.db.query(Entitlement).filter(
            Entitlement.id == entitlement_id
        )
        if organization_id is not None:
            query = query.filter(
                Entitlement.organization_id == organization_id
            )
        return query.first()

    def get_by_plan_id(
        self, plan_id: UUID, organization_id: UUID
    ) -> list[Entitlement]:
        return (
            self.db.query(Entitlement)
            .filter(
                Entitlement.plan_id == plan_id,
                Entitlement.organization_id == organization_id,
            )
            .all()
        )

    def get_by_feature_id(
        self, feature_id: UUID, organization_id: UUID
    ) -> list[Entitlement]:
        return (
            self.db.query(Entitlement)
            .filter(
                Entitlement.feature_id == feature_id,
                Entitlement.organization_id == organization_id,
            )
            .all()
        )

    def create(
        self, data: EntitlementCreate, organization_id: UUID
    ) -> Entitlement:
        entitlement = Entitlement(
            plan_id=data.plan_id,
            feature_id=data.feature_id,
            value=data.value,
            organization_id=organization_id,
        )
        self.db.add(entitlement)
        self.db.commit()
        self.db.refresh(entitlement)
        return entitlement

    def update(
        self,
        entitlement_id: UUID,
        data: EntitlementUpdate,
        organization_id: UUID,
    ) -> Entitlement | None:
        entitlement = self.get_by_id(entitlement_id, organization_id)
        if not entitlement:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(entitlement, key, value)
        self.db.commit()
        self.db.refresh(entitlement)
        return entitlement

    def delete(self, entitlement_id: UUID, organization_id: UUID) -> bool:
        entitlement = self.get_by_id(entitlement_id, organization_id)
        if not entitlement:
            return False
        self.db.delete(entitlement)
        self.db.commit()
        return True
