from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


class OrganizationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[Organization]:
        query = self.db.query(Organization)
        query = apply_order_by(query, Organization, order_by)
        return query.offset(skip).limit(limit).all()

    def get_by_id(self, org_id: UUID) -> Organization | None:
        return self.db.query(Organization).filter(Organization.id == org_id).first()

    def create(self, data: OrganizationCreate) -> Organization:
        org = Organization(**data.model_dump())
        self.db.add(org)
        self.db.commit()
        self.db.refresh(org)
        return org

    def update(self, org_id: UUID, data: OrganizationUpdate) -> Organization | None:
        org = self.get_by_id(org_id)
        if not org:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(org, key, value)
        self.db.commit()
        self.db.refresh(org)
        return org

    def delete(self, org_id: UUID) -> bool:
        org = self.get_by_id(org_id)
        if not org:
            return False
        self.db.delete(org)
        self.db.commit()
        return True
