"""DunningCampaignThreshold model for minimum outstanding amounts to trigger dunning."""

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func

from app.core.database import Base
from app.models.shared import UUIDType, generate_uuid


class DunningCampaignThreshold(Base):
    """Threshold model - minimum outstanding amount per currency to trigger dunning."""

    __tablename__ = "dunning_campaign_thresholds"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    dunning_campaign_id = Column(
        UUIDType,
        ForeignKey("dunning_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    currency = Column(String(3), nullable=False)
    amount_cents = Column(Numeric(12, 4), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
