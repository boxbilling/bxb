"""DataExport model for CSV data export tracking."""

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.schema import ForeignKey

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType


class ExportType(str, Enum):
    """Types of data that can be exported."""

    INVOICES = "invoices"
    CUSTOMERS = "customers"
    SUBSCRIPTIONS = "subscriptions"
    EVENTS = "events"
    FEES = "fees"
    CREDIT_NOTES = "credit_notes"


class ExportStatus(str, Enum):
    """Status of a data export."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class DataExport(Base):
    """DataExport model - tracks CSV data export jobs."""

    __tablename__ = "data_exports"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    export_type = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default=ExportStatus.PENDING.value)
    filters = Column(JSON, nullable=True)
    file_path = Column(String(2048), nullable=True)
    record_count = Column(Integer, nullable=True)
    progress = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
