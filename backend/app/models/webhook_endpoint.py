"""WebhookEndpoint model for configuring webhook delivery targets."""

from sqlalchemy import Column, DateTime, ForeignKey, String, func

from app.core.database import Base
from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class WebhookEndpoint(Base):
    """WebhookEndpoint model for webhook delivery targets."""

    __tablename__ = "webhook_endpoints"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    url = Column(String(2048), nullable=False)
    signature_algo = Column(String(50), nullable=False, default="hmac")
    status = Column(String(50), nullable=False, default="active")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
