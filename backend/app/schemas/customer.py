from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CustomerCreate(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    timezone: str = Field(default="UTC", max_length=50)
    billing_metadata: dict[str, Any] = Field(default_factory=dict)
    invoice_grace_period: int = Field(default=0, ge=0)
    net_payment_term: int = Field(default=30, ge=0)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone: str | None = Field(default=None, max_length=50)
    billing_metadata: dict[str, Any] | None = None
    invoice_grace_period: int | None = Field(default=None, ge=0)
    net_payment_term: int | None = Field(default=None, ge=0)


class PortalProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    timezone: str | None = Field(default=None, max_length=50)


class CustomerResponse(BaseModel):
    id: UUID
    external_id: str
    name: str
    email: str | None
    currency: str
    timezone: str
    billing_metadata: dict[str, Any]
    invoice_grace_period: int
    net_payment_term: int
    billing_entity_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerIntegrationMappingResponse(BaseModel):
    id: UUID
    integration_id: UUID
    integration_name: str
    integration_provider: str
    external_customer_id: str
    settings: dict[str, Any] | None = None
    created_at: datetime


class CustomerHealthStatus(str, Enum):
    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"


class CustomerHealthResponse(BaseModel):
    status: CustomerHealthStatus
    total_invoices: int
    paid_invoices: int
    overdue_invoices: int
    total_payments: int
    failed_payments: int
    overdue_amount: float
