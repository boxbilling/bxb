import uuid

from sqlalchemy import Column, DateTime, Index, String, func
from sqlalchemy.dialects.sqlite import JSON

from app.core.database import Base
from app.models.customer import UUIDType


class Event(Base):
    __tablename__ = "events"

    id = Column(UUIDType, primary_key=True, default=lambda: uuid.uuid4())
    transaction_id = Column(String(255), unique=True, index=True, nullable=False)
    external_customer_id = Column(String(255), nullable=False)
    code = Column(String(255), nullable=False)  # billable metric code
    timestamp = Column(DateTime(timezone=True), nullable=False)
    properties = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_events_external_customer_id", "external_customer_id"),
        Index("ix_events_code", "code"),
        Index("ix_events_timestamp", "timestamp"),
        Index(
            "ix_events_customer_code_timestamp",
            "external_customer_id",
            "code",
            "timestamp",
        ),
    )
