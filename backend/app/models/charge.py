import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.customer import UUIDType


class ChargeModel(str, Enum):
    STANDARD = "standard"  # Fixed price per unit
    GRADUATED = "graduated"  # Tiered pricing
    VOLUME = "volume"  # Volume discounts
    PACKAGE = "package"  # Price per X units
    PERCENTAGE = "percentage"  # % of transaction
    GRADUATED_PERCENTAGE = "graduated_percentage"  # Tiered % of transaction


class Charge(Base):
    __tablename__ = "charges"

    id = Column(UUIDType, primary_key=True, default=lambda: uuid.uuid4())
    plan_id = Column(
        UUIDType, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    billable_metric_id = Column(
        UUIDType,
        ForeignKey("billable_metrics.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    charge_model = Column(String(30), nullable=False)
    properties = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
