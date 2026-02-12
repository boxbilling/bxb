"""DunningCampaign model for automated payment recovery campaigns."""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class DunningCampaign(Base):
    """DunningCampaign model - configurable retry campaigns for failed payments."""

    __tablename__ = "dunning_campaigns"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    code = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    max_attempts = Column(Integer, nullable=False, default=3)
    days_between_attempts = Column(Integer, nullable=False, default=3)
    bcc_emails = Column(JSON, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="active")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
