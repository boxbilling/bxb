"""IntegrationSyncHistory model for tracking sync operations."""

import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, func

from app.core.database import Base
from app.models.customer import UUIDType


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class IntegrationSyncHistory(Base):
    """Records individual sync operations for an integration."""

    __tablename__ = "integration_sync_history"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    integration_id = Column(
        UUIDType,
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUIDType, nullable=True)
    external_id = Column(String(255), nullable=True)
    action = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    error_message = Column(String(1000), nullable=True)
    details = Column(JSON, nullable=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
