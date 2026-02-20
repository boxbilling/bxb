from sqlalchemy import Column, DateTime, ForeignKey, Numeric, func

from app.core.database import Base
from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class AppliedUsageThreshold(Base):
    __tablename__ = "applied_usage_thresholds"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    usage_threshold_id = Column(
        UUIDType,
        ForeignKey("usage_thresholds.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subscription_id = Column(
        UUIDType,
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        UUIDType,
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    crossed_at = Column(DateTime(timezone=True), nullable=False)
    lifetime_usage_amount_cents = Column(Numeric(12, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
