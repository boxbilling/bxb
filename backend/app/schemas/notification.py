"""Pydantic schemas for Notification."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    category: str
    title: str
    message: str
    resource_type: str | None
    resource_id: UUID | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationCountResponse(BaseModel):
    unread_count: int
