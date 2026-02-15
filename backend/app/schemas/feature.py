from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.feature import FeatureType


class FeatureCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    feature_type: FeatureType


class FeatureUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class FeatureResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    feature_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
