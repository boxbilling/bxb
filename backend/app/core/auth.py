from datetime import UTC, datetime
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import DEFAULT_ORGANIZATION_ID
from app.repositories.api_key_repository import ApiKeyRepository, hash_api_key
from app.services.portal_service import PortalService


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

    key_hash = hash_api_key(raw_key)
    repo = ApiKeyRepository(db)
    api_key = repo.get_by_hash(key_hash)

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if api_key.status == "revoked":
        raise HTTPException(status_code=401, detail="API key has been revoked")

    if api_key.expires_at and api_key.expires_at.replace(tzinfo=None) < datetime.now(UTC).replace(
        tzinfo=None
    ):
        raise HTTPException(status_code=401, detail="API key has expired")

    repo.update_last_used(api_key, datetime.now(UTC))

    return api_key.organization_id  # type: ignore[return-value]


def get_portal_customer(token: str = Query(...)) -> tuple[UUID, UUID]:
    """Validate a portal JWT token and return (customer_id, organization_id)."""
    try:
        return PortalService.verify_portal_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Portal token has expired") from None
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid portal token") from None
