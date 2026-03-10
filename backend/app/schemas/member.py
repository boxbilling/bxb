from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MemberCreate(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="member", pattern=r"^(owner|admin|member)$")


class MemberUpdate(BaseModel):
    role: str = Field(..., pattern=r"^(owner|admin|member)$")


class MemberResponse(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: str
    email: str | None = None
    name: str | None = None
    invited_by: UUID | None = None
    invited_at: datetime | None = None
    joined_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
