from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EntitlementCreate(BaseModel):
    plan_id: UUID
    feature_id: UUID
    value: str = Field(..., min_length=1)


class EntitlementUpdate(BaseModel):
    value: str | None = Field(default=None, min_length=1)


class EntitlementResponse(BaseModel):
    id: UUID
    plan_id: UUID
    feature_id: UUID
    value: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
