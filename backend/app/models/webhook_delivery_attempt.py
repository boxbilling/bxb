"""WebhookDeliveryAttempt model for tracking individual delivery attempts."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, func

from app.core.database import Base
from app.models.shared import UUIDType, generate_uuid


class WebhookDeliveryAttempt(Base):
    """Records each individual delivery attempt for a webhook."""

    __tablename__ = "webhook_delivery_attempts"
    __table_args__ = (
        Index("ix_webhook_delivery_attempts_webhook_id", "webhook_id"),
    )

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    webhook_id = Column(
        UUIDType,
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number = Column(Integer, nullable=False)
    http_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(String(1000), nullable=True)
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())
