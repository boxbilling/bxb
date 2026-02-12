import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.customer import UUIDType


class BillableMetricFilter(Base):
    __tablename__ = "billable_metric_filters"

    id = Column(UUIDType, primary_key=True, default=lambda: uuid.uuid4())
    billable_metric_id = Column(
        UUIDType,
        ForeignKey("billable_metrics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key = Column(String(255), nullable=False)
    values = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("billable_metric_id", "key", name="uq_billable_metric_filter_metric_key"),
        Index("ix_billable_metric_filters_metric_key", "billable_metric_id", "key"),
    )
