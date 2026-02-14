"""Pydantic schemas for PaymentMethod."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentMethodCreate(BaseModel):
    customer_id: UUID
    provider: str = Field(..., min_length=1, max_length=50)
    provider_payment_method_id: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=50)
    is_default: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class PaymentMethodUpdate(BaseModel):
    provider: str | None = Field(default=None, min_length=1, max_length=50)
    provider_payment_method_id: str | None = Field(default=None, min_length=1, max_length=255)
    type: str | None = Field(default=None, min_length=1, max_length=50)
    is_default: bool | None = None
    details: dict[str, Any] | None = None


class PaymentMethodResponse(BaseModel):
    id: UUID
    organization_id: UUID
    customer_id: UUID
    provider: str
    provider_payment_method_id: str
    type: str
    is_default: bool
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
