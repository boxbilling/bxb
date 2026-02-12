import uuid
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType


class AggregationType(str, Enum):
    COUNT = "count"
    SUM = "sum"
    MAX = "max"
    UNIQUE_COUNT = "unique_count"
    WEIGHTED_SUM = "weighted_sum"
    LATEST = "latest"
    CUSTOM = "custom"


class BillableMetric(Base):
    __tablename__ = "billable_metrics"

    id = Column(UUIDType, primary_key=True, default=lambda: uuid.uuid4())
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    code = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    aggregation_type = Column(String(20), nullable=False)
    field_name = Column(String(255), nullable=True)  # For SUM, MAX, UNIQUE_COUNT
    recurring = Column(Boolean, nullable=False, default=False)
    rounding_function = Column(String(10), nullable=True)  # "round", "ceil", "floor"
    rounding_precision = Column(Integer, nullable=True)
    expression = Column(Text, nullable=True)  # For CUSTOM aggregation type
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
