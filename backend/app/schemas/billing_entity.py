from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class BillingEntityCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    zip_code: str | None = None
    tax_id: str | None = None
    email: EmailStr | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    timezone: str = Field(default="UTC", max_length=50)
    document_locale: str = Field(default="en", max_length=10)
    invoice_prefix: str | None = Field(default=None, max_length=20)
    next_invoice_number: int = Field(default=1, ge=1)
    is_default: bool = False


class BillingEntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    zip_code: str | None = None
    tax_id: str | None = None
    email: EmailStr | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone: str | None = Field(default=None, max_length=50)
    document_locale: str | None = Field(default=None, max_length=10)
    invoice_prefix: str | None = Field(default=None, max_length=20)
    next_invoice_number: int | None = Field(default=None, ge=1)
    is_default: bool | None = None


class BillingEntityResponse(BaseModel):
    id: UUID
    code: str
    name: str
    legal_name: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    country: str | None
    zip_code: str | None
    tax_id: str | None
    email: str | None
    currency: str
    timezone: str
    document_locale: str
    invoice_prefix: str | None
    next_invoice_number: int
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
