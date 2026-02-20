from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, func

from app.core.database import Base
from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class UsageAlert(Base):
    __tablename__ = "usage_alerts"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    subscription_id = Column(
        UUIDType,
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    billable_metric_id = Column(
        UUIDType,
        ForeignKey("billable_metrics.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    threshold_value = Column(Numeric(12, 4), nullable=False)
    recurring = Column(Boolean, nullable=False, default=False)
    name = Column(String(255), nullable=True)
    times_triggered = Column(Integer, nullable=False, default=0)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
