from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.user import User


class MemberRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_org_and_user(self, org_id: UUID, user_id: UUID) -> OrganizationMember | None:
        return (
            self.db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
            .first()
        )

    def list_by_org(
        self, org_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[OrganizationMember]:
        return (
            self.db.query(OrganizationMember)
            .join(User, OrganizationMember.user_id == User.id)
            .filter(OrganizationMember.organization_id == org_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_org(self, org_id: UUID) -> int:
        return (
            self.db.query(OrganizationMember)
            .filter(OrganizationMember.organization_id == org_id)
            .count()
        )

    def create(
        self,
        org_id: UUID,
        user_id: UUID,
        role: str,
        invited_by: UUID | None = None,
    ) -> OrganizationMember:
        member = OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            role=role,
            invited_by=invited_by,
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member

    def update_role(
        self, member_id: UUID, org_id: UUID, role: str
    ) -> OrganizationMember | None:
        member = (
            self.db.query(OrganizationMember)
            .filter(
                OrganizationMember.id == member_id,
                OrganizationMember.organization_id == org_id,
            )
            .first()
        )
        if not member:
            return None
        member.role = role  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(member)
        return member

    def delete(self, member_id: UUID, org_id: UUID) -> bool:
        member = (
            self.db.query(OrganizationMember)
            .filter(
                OrganizationMember.id == member_id,
                OrganizationMember.organization_id == org_id,
            )
            .first()
        )
        if not member:
            return False
        self.db.delete(member)
        self.db.commit()
        return True

    def get_first_org(self) -> Organization | None:
        return self.db.query(Organization).order_by(Organization.created_at).first()

    def get_org_by_slug(self, slug: str) -> Organization | None:
        return self.db.query(Organization).filter(Organization.slug == slug).first()
