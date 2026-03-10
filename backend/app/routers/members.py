"""Organization member management endpoints."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.database import get_db
from app.core.security import hash_password
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.repositories.member_repository import MemberRepository
from app.repositories.user_repository import UserRepository
from app.schemas.member import MemberCreate, MemberResponse, MemberUpdate
from app.schemas.user import UserCreate
from app.services.audit_service import AuditService

router = APIRouter()


def _member_to_response(member: OrganizationMember, db: Session) -> dict[str, Any]:
    """Convert a member to a response dict, enriching with user email/name."""
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(member.user_id)  # type: ignore[arg-type]
    data = MemberResponse.model_validate(member).model_dump()
    if user:
        data["email"] = user.email
        data["name"] = user.name
    return data


@router.get(
    "/",
    response_model=list[MemberResponse],
    summary="List organization members",
)
async def list_members(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current: tuple[User, OrganizationMember] = Depends(require_role("admin", "owner")),
) -> list[dict[str, Any]]:
    """List members of the current organization."""
    _user, membership = current
    org_id = membership.organization_id

    member_repo = MemberRepository(db)
    response.headers["X-Total-Count"] = str(member_repo.count_by_org(org_id))  # type: ignore[arg-type]
    members = member_repo.list_by_org(org_id, skip=skip, limit=limit)  # type: ignore[arg-type]
    return [_member_to_response(m, db) for m in members]


@router.post(
    "/",
    response_model=MemberResponse,
    status_code=201,
    summary="Invite a new member",
)
async def create_member(
    data: MemberCreate,
    db: Session = Depends(get_db),
    current: tuple[User, OrganizationMember] = Depends(require_role("admin", "owner")),
) -> dict[str, Any]:
    """Add a new member to the current organization."""
    current_user, membership = current
    org_id = membership.organization_id

    user_repo = UserRepository(db)
    member_repo = MemberRepository(db)

    # Check if user already exists
    existing_user = user_repo.get_by_email(data.email)
    if existing_user:
        # Check if already a member
        existing_member = member_repo.get_by_org_and_user(org_id, existing_user.id)  # type: ignore[arg-type]
        if existing_member:
            raise HTTPException(status_code=409, detail="User is already a member")
        user = existing_user
    else:
        # Create the user
        pw_hash = hash_password(data.password)
        user = user_repo.create(
            UserCreate(email=data.email, name=data.name, password=data.password),
            password_hash=pw_hash,
        )

    now = datetime.now(UTC)
    member = member_repo.create(
        org_id=org_id,  # type: ignore[arg-type]
        user_id=user.id,  # type: ignore[arg-type]
        role=data.role,
        invited_by=current_user.id,  # type: ignore[arg-type]
    )
    # Set invited_at and joined_at
    member.invited_at = now  # type: ignore[assignment]
    member.joined_at = now  # type: ignore[assignment]
    db.commit()
    db.refresh(member)

    audit_service = AuditService(db)
    audit_service.log_create(
        resource_type="organization_member",
        resource_id=member.id,  # type: ignore[arg-type]
        organization_id=org_id,  # type: ignore[arg-type]
        actor_type="user",
        actor_id=str(current_user.id),
        data={"email": data.email, "role": data.role},
    )

    return _member_to_response(member, db)


@router.patch(
    "/{member_id}",
    response_model=MemberResponse,
    summary="Update member role",
)
async def update_member(
    member_id: UUID,
    data: MemberUpdate,
    db: Session = Depends(get_db),
    current: tuple[User, OrganizationMember] = Depends(require_role("admin", "owner")),
) -> dict[str, Any]:
    """Update a member's role in the current organization."""
    current_user, membership = current
    org_id = membership.organization_id

    member_repo = MemberRepository(db)

    # Cannot change own role
    existing = member_repo.get_by_org_and_user(org_id, current_user.id)  # type: ignore[arg-type]
    if existing and str(existing.id) == str(member_id):
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    # Cannot promote to owner unless current user is owner
    if data.role == "owner" and membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can promote to owner")

    updated = member_repo.update_role(member_id, org_id, data.role)  # type: ignore[arg-type]
    if not updated:
        raise HTTPException(status_code=404, detail="Member not found")

    audit_service = AuditService(db)
    audit_service.log_update(
        resource_type="organization_member",
        resource_id=member_id,
        organization_id=org_id,  # type: ignore[arg-type]
        actor_type="user",
        actor_id=str(current_user.id),
        new_data={"role": data.role},
    )

    return _member_to_response(updated, db)


@router.delete(
    "/{member_id}",
    status_code=204,
    summary="Remove a member",
)
async def delete_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current: tuple[User, OrganizationMember] = Depends(require_role("owner")),
) -> None:
    """Remove a member from the current organization. Owner only."""
    current_user, membership = current
    org_id = membership.organization_id

    # Cannot delete yourself
    member_repo = MemberRepository(db)
    own_member = member_repo.get_by_org_and_user(org_id, current_user.id)  # type: ignore[arg-type]
    if own_member and str(own_member.id) == str(member_id):
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    if not member_repo.delete(member_id, org_id):  # type: ignore[arg-type]
        raise HTTPException(status_code=404, detail="Member not found")

    audit_service = AuditService(db)
    audit_service.log_delete(
        resource_type="organization_member",
        resource_id=member_id,
        organization_id=org_id,  # type: ignore[arg-type]
        actor_type="user",
        actor_id=str(current_user.id),
        data={"member_id": str(member_id)},
    )
