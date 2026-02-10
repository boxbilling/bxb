import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, String, Text, func

from app.core.database import Base
from app.models.customer import UUIDType


class AggregationType(str, Enum):
    COUNT = "count"
    SUM = "sum"
    MAX = "max"
    UNIQUE_COUNT = "unique_count"


class BillableMetric(Base):
    __tablename__ = "billable_metrics"

    id = Column(UUIDType, primary_key=True, default=lambda: uuid.uuid4())
    code = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    aggregation_type = Column(String(20), nullable=False)
    field_name = Column(String(255), nullable=True)  # For SUM, MAX, UNIQUE_COUNT
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
