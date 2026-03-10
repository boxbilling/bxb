import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.jwt import decode_access_token
from app.models.customer import DEFAULT_ORGANIZATION_ID
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.repositories.api_key_repository import ApiKeyRepository, hash_api_key
from app.repositories.member_repository import MemberRepository
from app.repositories.user_repository import UserRepository
from app.services.portal_service import PortalService


def require_admin_secret(request: Request) -> None:
    """Validate the X-Admin-Secret header against BXB_ADMIN_SECRET."""
    configured = settings.BXB_ADMIN_SECRET
    if not configured or len(configured) < 32:
        raise HTTPException(status_code=401, detail="Admin secret not configured")
    provided = request.headers.get("X-Admin-Secret", "")
    if not provided or not secrets.compare_digest(configured, provided):
        raise HTTPException(status_code=401, detail="Invalid admin secret")


def get_current_organization(
    request: Request,
    db: Session = Depends(get_db),
) -> UUID:
    """Extract organization_id from the API key in the Authorization header.

    If no Authorization header is provided, falls back to the default organization
    for backward compatibility during the transition period.
    """
    # Allow switching organizations via header (for the admin UI)
    org_id_header = request.headers.get("X-Organization-Id")
    if org_id_header:
        try:
            return UUID(org_id_header)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid X-Organization-Id header"
            ) from None

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return DEFAULT_ORGANIZATION_ID

    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    raw_key = auth_header[7:]
    if not raw_key:
        raise HTTPException(status_code=401, detail="API key is required")

    # API keys use the bxb_live_ prefix — route to API key flow
    if raw_key.startswith("bxb_live_"):
        key_hash = hash_api_key(raw_key)
        repo = ApiKeyRepository(db)
        api_key = repo.get_by_hash(key_hash)

        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

        if api_key.status == "revoked":
            raise HTTPException(status_code=401, detail="API key has been revoked")

        expires = api_key.expires_at
        if expires and expires.replace(tzinfo=None) < datetime.now(UTC).replace(tzinfo=None):
            raise HTTPException(status_code=401, detail="API key has expired")

        repo.update_last_used(api_key, datetime.now(UTC))

        return api_key.organization_id  # type: ignore[return-value]

    # Otherwise, try JWT decoding — extract org claim for dashboard users
    try:
        payload = decode_access_token(raw_key)
        return UUID(payload["org"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        # JWT decode failed — fall through to default org
        return DEFAULT_ORGANIZATION_ID


def get_portal_customer(token: str = Query(...)) -> tuple[UUID, UUID]:
    """Validate a portal JWT token and return (customer_id, organization_id)."""
    try:
        return PortalService.verify_portal_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Portal token has expired") from None
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid portal token") from None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> tuple[User, OrganizationMember]:
    """Authenticate a user via JWT Bearer token and return (user, membership)."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Token is required")

    # If token starts with bxb_live_ prefix, it's an API key, not a JWT
    if token.startswith("bxb_live_"):
        raise HTTPException(status_code=401, detail="API keys cannot be used for user auth")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token") from None

    try:
        user_id = UUID(payload["sub"])
        org_id = UUID(payload["org"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token claims") from None

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    member_repo = MemberRepository(db)
    membership = member_repo.get_by_org_and_user(org_id, user_id)
    if not membership:
        raise HTTPException(status_code=401, detail="Not a member of this organization")

    return (user, membership)


def require_role(
    *roles: str,
) -> Callable[..., tuple[User, OrganizationMember]]:
    """Dependency factory that checks the authenticated user has one of the allowed roles."""

    def _dependency(
        current: tuple[User, OrganizationMember] = Depends(get_current_user),
    ) -> tuple[User, OrganizationMember]:
        _user, membership = current
        if membership.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current

    return _dependency
