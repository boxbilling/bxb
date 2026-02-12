from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import DEFAULT_ORGANIZATION_ID
from app.repositories.api_key_repository import ApiKeyRepository, hash_api_key


def get_current_organization(
    request: Request,
    db: Session = Depends(get_db),
) -> UUID:
    """Extract organization_id from the API key in the Authorization header.

    If no Authorization header is provided, falls back to the default organization
    for backward compatibility during the transition period.
    """
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
