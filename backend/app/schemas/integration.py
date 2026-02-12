from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntegrationCreate(BaseModel):
    integration_type: str = Field(..., min_length=1, max_length=30)
    provider_type: str = Field(..., min_length=1, max_length=50)
    status: str = Field(default="active", max_length=20)
    settings: dict[str, Any] = Field(default_factory=dict)


class IntegrationUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=20)
    settings: dict[str, Any] | None = None
    error_details: dict[str, Any] | None = None


class IntegrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    integration_type: str
    provider_type: str
    status: str
    settings: dict[str, Any]
    last_sync_at: datetime | None = None
    error_details: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
