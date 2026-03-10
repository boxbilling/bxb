from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MemberCreate(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = "member"


class MemberUpdate(BaseModel):
    role: str


class MemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    organization_id: UUID
    role: str
    user_email: str
    user_name: str
    invited_at: datetime | None
    joined_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
