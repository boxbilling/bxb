"""AddOn and AppliedAddOn schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AddOnCreate(BaseModel):
    code: str = Field(max_length=255)
    name: str = Field(max_length=255)
    description: str | None = None
    amount_cents: Decimal
    amount_currency: str = Field(default="USD", min_length=3, max_length=3)
    invoice_display_name: str | None = Field(default=None, max_length=255)


class AddOnUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    amount_cents: Decimal | None = None
    amount_currency: str | None = Field(default=None, min_length=3, max_length=3)
    invoice_display_name: str | None = Field(default=None, max_length=255)


class AddOnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None = None
    amount_cents: Decimal
    amount_currency: str
    invoice_display_name: str | None = None
    created_at: datetime
    updated_at: datetime


class ApplyAddOnRequest(BaseModel):
    add_on_code: str
    customer_id: UUID
    amount_cents: Decimal | None = None
    amount_currency: str | None = Field(default=None, min_length=3, max_length=3)


class AppliedAddOnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    add_on_id: UUID
    customer_id: UUID
    amount_cents: Decimal
    amount_currency: str
    created_at: datetime


class AppliedAddOnDetailResponse(BaseModel):
    """Applied add-on with customer name for display."""

    id: UUID
    add_on_id: UUID
    customer_id: UUID
    customer_name: str
    amount_cents: Decimal
    amount_currency: str
    created_at: datetime


class PortalAddOnResponse(BaseModel):
    """Add-on available for purchase in the customer portal."""

    id: UUID
    code: str
    name: str
    description: str | None = None
    amount_cents: Decimal
    amount_currency: str


class PortalPurchasedAddOnResponse(BaseModel):
    """An add-on the customer has already purchased."""

    id: UUID
    add_on_id: UUID
    add_on_name: str
    add_on_code: str
    amount_cents: Decimal
    amount_currency: str
    created_at: datetime


class PortalPurchaseAddOnResponse(BaseModel):
    """Response after purchasing an add-on."""

    applied_add_on_id: UUID
    invoice_id: UUID
    add_on_name: str
    amount_cents: Decimal
    amount_currency: str
