from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntegrationMappingCreate(BaseModel):
    integration_id: UUID
    mappable_type: str = Field(..., min_length=1, max_length=50)
    mappable_id: UUID
    external_id: str = Field(..., min_length=1, max_length=255)
    external_data: dict[str, Any] | None = None


class IntegrationMappingUpdate(BaseModel):
    external_id: str | None = Field(default=None, min_length=1, max_length=255)
    external_data: dict[str, Any] | None = None
    last_synced_at: datetime | None = None


class IntegrationMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    integration_id: UUID
    mappable_type: str
    mappable_id: UUID
    external_id: str
    external_data: dict[str, Any] | None = None
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
