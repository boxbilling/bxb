from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func

from app.core.database import Base
from app.models.shared import UUIDType, generate_uuid


class UsageAlertTrigger(Base):
    __tablename__ = "usage_alert_triggers"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    usage_alert_id = Column(
        UUIDType,
        ForeignKey("usage_alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_usage = Column(Numeric(16, 4), nullable=False)
    threshold_value = Column(Numeric(12, 4), nullable=False)
    metric_code = Column(String(255), nullable=False)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
