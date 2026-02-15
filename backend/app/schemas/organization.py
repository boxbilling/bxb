from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    default_currency: str = Field(default="USD", min_length=3, max_length=3)
    timezone: str = Field(default="UTC", max_length=50)
    hmac_key: str | None = Field(default=None, max_length=255)
    document_number_prefix: str | None = Field(default=None, max_length=20)
    invoice_grace_period: int = Field(default=0, ge=0)
    net_payment_term: int = Field(default=30, ge=0)
    logo_url: str | None = Field(default=None, max_length=2048)
    email: str | None = Field(default=None, max_length=255)
    portal_accent_color: str | None = Field(default=None, max_length=7)
    portal_welcome_message: str | None = Field(default=None, max_length=500)
    legal_name: str | None = Field(default=None, max_length=255)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, max_length=255)
    zipcode: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=255)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone: str | None = Field(default=None, max_length=50)
    hmac_key: str | None = Field(default=None, max_length=255)
    document_number_prefix: str | None = Field(default=None, max_length=20)
    invoice_grace_period: int | None = Field(default=None, ge=0)
    net_payment_term: int | None = Field(default=None, ge=0)
    logo_url: str | None = Field(default=None, max_length=2048)
    email: str | None = Field(default=None, max_length=255)
    portal_accent_color: str | None = Field(default=None, max_length=7)
    portal_welcome_message: str | None = Field(default=None, max_length=500)
    legal_name: str | None = Field(default=None, max_length=255)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, max_length=255)
    zipcode: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=255)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    default_currency: str
    timezone: str
    hmac_key: str | None
    document_number_prefix: str | None
    invoice_grace_period: int
    net_payment_term: int
    logo_url: str | None
    email: str | None
    portal_accent_color: str | None
    portal_welcome_message: str | None
    legal_name: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    zipcode: str | None
    country: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PortalBrandingResponse(BaseModel):
    name: str
    logo_url: str | None
    accent_color: str | None
    welcome_message: str | None

    model_config = {"from_attributes": True}
