"""Data export schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.data_export import ExportType


class DataExportCreate(BaseModel):
    """Schema for creating a data export."""

    export_type: ExportType
    filters: dict[str, Any] | None = None


class DataExportEstimate(BaseModel):
    """Schema for data export size estimate response."""

    export_type: str
    record_count: int


class DataExportResponse(BaseModel):
    """Schema for data export response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    export_type: str
    status: str
    filters: dict[str, Any] | None = None
    file_path: str | None = None
    record_count: int | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
