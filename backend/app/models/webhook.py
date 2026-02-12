"""Webhook model for tracking webhook delivery attempts."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.customer import UUIDType


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class Webhook(Base):
    """Webhook model for tracking webhook delivery attempts."""

    __tablename__ = "webhooks"
    __table_args__ = (
        Index("ix_webhooks_webhook_endpoint_id", "webhook_endpoint_id"),
        Index("ix_webhooks_webhook_type", "webhook_type"),
        Index("ix_webhooks_status", "status"),
    )

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    webhook_endpoint_id = Column(
        UUIDType,
        ForeignKey("webhook_endpoints.id", ondelete="RESTRICT"),
        nullable=False,
    )
    webhook_type = Column(String(100), nullable=False)
    object_type = Column(String(50), nullable=True)
    object_id = Column(UUIDType, nullable=True)
    payload = Column(JSON, nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    retries = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=5)
    last_retried_at = Column(DateTime(timezone=True), nullable=True)
    http_status = Column(Integer, nullable=True)
    response = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
