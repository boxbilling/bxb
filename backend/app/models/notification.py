"""Notification model for in-app notification system."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class Notification(Base):
    """Notification model - stores in-app notifications for admin users."""

    __tablename__ = "notifications"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    category = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(String(1000), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(UUIDType, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
