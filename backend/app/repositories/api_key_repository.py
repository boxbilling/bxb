import hashlib
import secrets
from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate


def generate_api_key() -> str:
    """Generate a random API key with 'bxb_' prefix."""
    return "bxb_" + secrets.token_hex(32)


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of the raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKeyRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, organization_id: UUID, data: ApiKeyCreate) -> tuple[ApiKey, str]:
        """Create a new API key. Returns (api_key_model, raw_key)."""
        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key)
        key_prefix = raw_key[:12]

        api_key = ApiKey(
            organization_id=organization_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=data.name,
            expires_at=data.expires_at,
        )
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key, raw_key

    def get_by_hash(self, key_hash: str) -> ApiKey | None:
        return self.db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()

    def get_by_id(self, api_key_id: UUID, organization_id: UUID) -> ApiKey | None:
        return (
            self.db.query(ApiKey)
            .filter(ApiKey.id == api_key_id, ApiKey.organization_id == organization_id)
            .first()
        )

    def list_by_org(self, organization_id: UUID, skip: int = 0, limit: int = 100) -> list[ApiKey]:
        return (
            self.db.query(ApiKey)
            .filter(ApiKey.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, organization_id: UUID) -> int:
        """Count API keys for an organization."""
        return (
            self.db.query(func.count(ApiKey.id))
            .filter(ApiKey.organization_id == organization_id)
            .scalar()
            or 0
        )

    def revoke(self, api_key_id: UUID, organization_id: UUID) -> ApiKey | None:
        api_key = self.get_by_id(api_key_id, organization_id)
        if not api_key:
            return None
        api_key.status = "revoked"  # type: ignore[assignment]
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def rotate(self, api_key_id: UUID, organization_id: UUID) -> tuple[ApiKey, str] | None:
        """Rotate an API key: revoke the old one and create a new one with the same config."""
        old_key = self.get_by_id(api_key_id, organization_id)
        if not old_key or old_key.status != "active":
            return None

        old_key.status = "revoked"  # type: ignore[assignment]

        new_data = ApiKeyCreate(
            name=old_key.name,  # type: ignore[arg-type]
            expires_at=old_key.expires_at,  # type: ignore[arg-type]
        )
        new_key, raw_key = self.create(organization_id, new_data)
        return new_key, raw_key

    def update_last_used(self, api_key: ApiKey, now: datetime) -> None:
        api_key.last_used_at = now  # type: ignore[assignment]
        self.db.commit()
