from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.organization import Organization
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


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

    def _generate_unique_slug(self, name: str) -> str:
        """Generate a unique slug from the organization name."""
        base_slug = _slugify(name)
        if not base_slug:
            base_slug = "org"
        slug = base_slug
        counter = 1
        while (
            self.db.query(Organization)
            .filter(Organization.slug == slug)
            .first()
            is not None
        ):
            slug = f"{base_slug}-{counter}"
            counter += 1
        return slug

    def create(self, data: OrganizationCreate) -> Organization:
        dump = data.model_dump()
        dump["slug"] = self._generate_unique_slug(data.name)
        org = Organization(**dump)
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
