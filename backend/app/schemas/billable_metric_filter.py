from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BillableMetricFilterCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    values: list[Any] = Field(default_factory=list)


class BillableMetricFilterResponse(BaseModel):
    id: UUID
    billable_metric_id: UUID
    key: str
    values: list[Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
