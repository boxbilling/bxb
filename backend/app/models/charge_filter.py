import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.customer import UUIDType


class ChargeFilter(Base):
    __tablename__ = "charge_filters"

    id = Column(UUIDType, primary_key=True, default=lambda: uuid.uuid4())
    charge_id = Column(
        UUIDType,
        ForeignKey("charges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    properties = Column(JSON, nullable=False, default=dict)
    invoice_display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
