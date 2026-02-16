from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.billing_entity import BillingEntity
from app.models.customer import Customer
from app.schemas.billing_entity import BillingEntityCreate, BillingEntityUpdate


class BillingEntityRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[BillingEntity]:
        query = (
            self.db.query(BillingEntity)
            .filter(BillingEntity.organization_id == organization_id)
        )
        query = apply_order_by(query, BillingEntity, order_by)
        return query.offset(skip).limit(limit).all()

    def count(self, organization_id: UUID) -> int:
        return (
            self.db.query(func.count(BillingEntity.id))
            .filter(BillingEntity.organization_id == organization_id)
            .scalar()
            or 0
        )

    def get_by_id(
        self, entity_id: UUID, organization_id: UUID | None = None
    ) -> BillingEntity | None:
        query = self.db.query(BillingEntity).filter(
            BillingEntity.id == entity_id
        )
        if organization_id is not None:
            query = query.filter(
                BillingEntity.organization_id == organization_id
            )
        return query.first()

    def get_by_code(
        self, code: str, organization_id: UUID
    ) -> BillingEntity | None:
        return (
            self.db.query(BillingEntity)
            .filter(
                BillingEntity.code == code,
                BillingEntity.organization_id == organization_id,
            )
            .first()
        )

    def get_default(self, organization_id: UUID) -> BillingEntity | None:
        return (
            self.db.query(BillingEntity)
            .filter(
                BillingEntity.organization_id == organization_id,
                BillingEntity.is_default.is_(True),
            )
            .first()
        )

    def create(
        self, data: BillingEntityCreate, organization_id: UUID
    ) -> BillingEntity:
        entity = BillingEntity(
            **data.model_dump(), organization_id=organization_id
        )
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(
        self,
        entity_id: UUID,
        data: BillingEntityUpdate,
        organization_id: UUID,
    ) -> BillingEntity | None:
        entity = self.get_by_id(entity_id, organization_id)
        if not entity:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(entity, key, value)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity_id: UUID, organization_id: UUID) -> bool:
        entity = self.get_by_id(entity_id, organization_id)
        if not entity:
            return False
        self.db.delete(entity)
        self.db.commit()
        return True

    def code_exists(self, code: str, organization_id: UUID) -> bool:
        return self.get_by_code(code, organization_id) is not None

    def customer_counts(self, organization_id: UUID) -> dict[str, int]:
        """Return a mapping of billing_entity_id -> customer count."""
        rows = (
            self.db.query(
                Customer.billing_entity_id,
                func.count(Customer.id),
            )
            .filter(
                Customer.organization_id == organization_id,
                Customer.billing_entity_id.isnot(None),
            )
            .group_by(Customer.billing_entity_id)
            .all()
        )
        return {str(entity_id): cnt for entity_id, cnt in rows}
