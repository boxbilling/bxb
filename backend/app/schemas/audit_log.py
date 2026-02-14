"""Pydantic schemas for AuditLog."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    organization_id: UUID
    resource_type: str
    resource_id: UUID
    action: str
    changes: dict[str, Any]
    actor_type: str
    actor_id: str | None
    metadata_: dict[str, Any] | None

    model_config = {"from_attributes": True}

    created_at: datetime
