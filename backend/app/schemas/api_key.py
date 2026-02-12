from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: UUID
    organization_id: UUID
    key_prefix: str
    name: str | None
    last_used_at: datetime | None
    expires_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(ApiKeyResponse):
    """Returned only on creation — includes the raw API key."""

    raw_key: str


class ApiKeyListResponse(BaseModel):
    id: UUID
    key_prefix: str
    name: str | None
    last_used_at: datetime | None
    expires_at: datetime | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
