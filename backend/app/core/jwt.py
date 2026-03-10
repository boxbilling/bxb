from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

from app.core.config import settings


def create_access_token(
    user_id: UUID, org_id: UUID, role: str, expires_minutes: int = 60
) -> str:
    """Create a JWT access token with user/org/role claims."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.BXB_JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token. Returns the payload dict.

    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    result: dict[str, Any] = jwt.decode(token, settings.BXB_JWT_SECRET, algorithms=["HS256"])
    return result
