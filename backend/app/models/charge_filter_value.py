import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint, func

from app.core.database import Base
from app.models.customer import UUIDType


class ChargeFilterValue(Base):
    __tablename__ = "charge_filter_values"

    id = Column(UUIDType, primary_key=True, default=lambda: uuid.uuid4())
    charge_filter_id = Column(
        UUIDType,
        ForeignKey("charge_filters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    billable_metric_filter_id = Column(
        UUIDType,
        ForeignKey("billable_metric_filters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "charge_filter_id",
            "billable_metric_filter_id",
            name="uq_charge_filter_value_filter_metric",
        ),
    )
