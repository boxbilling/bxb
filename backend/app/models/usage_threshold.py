from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Numeric, String, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class UsageThreshold(Base):
    __tablename__ = "usage_thresholds"
    __table_args__ = (
        CheckConstraint(
            "(plan_id IS NOT NULL AND subscription_id IS NULL) OR "
            "(plan_id IS NULL AND subscription_id IS NOT NULL)",
            name="ck_usage_thresholds_exactly_one_parent",
        ),
    )

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    plan_id = Column(
        UUIDType, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    subscription_id = Column(
        UUIDType,
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    amount_cents = Column(Numeric(12, 4), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    recurring = Column(Boolean, nullable=False, default=False)
    threshold_display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
