from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class EventCreate(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=255)
    external_customer_id: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=255)
    timestamp: datetime
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> datetime:
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # Try ISO format first
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                pass
        raise ValueError("Invalid timestamp format. Use ISO 8601 format.")


class EventBatchCreate(BaseModel):
    events: list[EventCreate] = Field(..., min_length=1, max_length=100)


class EventResponse(BaseModel):
    id: UUID
    transaction_id: str
    external_customer_id: str
    code: str
    timestamp: datetime
    properties: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class EventBatchResponse(BaseModel):
    ingested: int
    duplicates: int
    events: list[EventResponse]


class EventVolumePoint(BaseModel):
    timestamp: str
    count: int


class EventVolumeResponse(BaseModel):
    data_points: list[EventVolumePoint]
