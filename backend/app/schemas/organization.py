from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    default_currency: str = Field(default="USD", min_length=3, max_length=3)
    timezone: str = Field(default="UTC", max_length=50)
    hmac_key: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=2048)
    portal_accent_color: str | None = Field(default=None, max_length=7)
    portal_welcome_message: str | None = Field(default=None, max_length=500)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone: str | None = Field(default=None, max_length=50)
    hmac_key: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=2048)
    portal_accent_color: str | None = Field(default=None, max_length=7)
    portal_welcome_message: str | None = Field(default=None, max_length=500)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    default_currency: str
    timezone: str
    hmac_key: str | None
    logo_url: str | None
    portal_accent_color: str | None
    portal_welcome_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PortalBrandingResponse(BaseModel):
    name: str
    logo_url: str | None
    accent_color: str | None
    welcome_message: str | None

    model_config = {"from_attributes": True}
