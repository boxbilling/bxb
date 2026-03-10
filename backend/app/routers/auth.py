"""User authentication and session management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.jwt import create_access_token
from app.core.security import verify_password
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.repositories.member_repository import MemberRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in with email and password",
    responses={
        401: {"description": "Invalid credentials"},
        404: {"description": "Organization not found"},
    },
)
async def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Authenticate a user and return a JWT access token."""
    member_repo = MemberRepository(db)

    # Resolve organization
    if data.org_slug:
        org = member_repo.get_org_by_slug(data.org_slug)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
    else:
        org = member_repo.get_first_org()
        if not org:
            raise HTTPException(status_code=404, detail="No organizations configured")

    # Look up user by email
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(data.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not user.password_hash or not verify_password(data.password, str(user.password_hash)):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check active status
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")

    # Check membership
    membership = member_repo.get_by_org_and_user(org.id, user.id)  # type: ignore[arg-type]
    if not membership:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create token
    token = create_access_token(user.id, org.id, membership.role)  # type: ignore[arg-type]

    # Audit log
    audit_service = AuditService(db)
    audit_service.log_create(
        resource_type="session",
        resource_id=user.id,  # type: ignore[arg-type]
        organization_id=org.id,  # type: ignore[arg-type]
        actor_type="user",
        data={"email": user.email},
    )

    return LoginResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "name": user.name},  # type: ignore[arg-type]
        organization={"id": org.id, "name": org.name, "slug": org.slug},  # type: ignore[arg-type]
        role=membership.role,  # type: ignore[arg-type]
    )


@router.post(
    "/logout",
    summary="Log out (discard token client-side)",
    responses={401: {"description": "Unauthorized"}},
)
async def logout(
    current: tuple[User, OrganizationMember] = Depends(get_current_user),
) -> dict[str, str]:
    """Log out the current user. JWT is stateless — client discards the token."""
    return {"message": "Logged out"}


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Get current authenticated user",
    responses={401: {"description": "Unauthorized"}},
)
async def me(
    db: Session = Depends(get_db),
    current: tuple[User, OrganizationMember] = Depends(get_current_user),
) -> MeResponse:
    """Return the authenticated user's info, organization, and role."""
    user, membership = current

    org_repo = OrganizationRepository(db)
    org = org_repo.get_by_id(membership.organization_id)  # type: ignore[arg-type]
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return MeResponse(
        user={  # type: ignore[arg-type]
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_active": user.is_active,
        },
        organization={  # type: ignore[arg-type]
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
        },
        role=membership.role,  # type: ignore[arg-type]
    )
