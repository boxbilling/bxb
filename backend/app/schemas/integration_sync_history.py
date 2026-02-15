from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntegrationSyncHistoryCreate(BaseModel):
    integration_id: UUID
    resource_type: str = Field(..., min_length=1, max_length=50)
    resource_id: UUID | None = None
    external_id: str | None = Field(default=None, max_length=255)
    action: str = Field(..., min_length=1, max_length=50)
    status: str = Field(..., min_length=1, max_length=20)
    error_message: str | None = Field(default=None, max_length=1000)
    details: dict[str, Any] | None = None
    completed_at: datetime | None = None


class IntegrationSyncHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    integration_id: UUID
    resource_type: str
    resource_id: UUID | None = None
    external_id: str | None = None
    action: str
    status: str
    error_message: str | None = None
    details: dict[str, Any] | None = None
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
