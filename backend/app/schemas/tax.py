"""Tax and AppliedTax schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaxCreate(BaseModel):
    code: str = Field(max_length=255)
    name: str = Field(max_length=255)
    rate: Decimal
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    applied_to_organization: bool = False


class TaxUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    rate: Decimal | None = None
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    applied_to_organization: bool | None = None


class TaxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    rate: Decimal
    description: str | None = None
    category: str | None = None
    applied_to_organization: bool
    created_at: datetime
    updated_at: datetime


class ApplyTaxRequest(BaseModel):
    tax_code: str
    taxable_type: str = Field(max_length=50)
    taxable_id: UUID


class AppliedTaxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tax_id: UUID
    taxable_type: str
    taxable_id: UUID
    tax_rate: Decimal | None = None
    tax_amount_cents: Decimal
    tax_name: str | None = None
    tax_code: str | None = None
    created_at: datetime


class TaxAppliedEntitiesResponse(BaseModel):
    """Response for listing entities a tax is applied to."""

    tax_id: UUID
    tax_code: str
    entities: list[dict[str, str | None]]


class TaxApplicationCountsResponse(BaseModel):
    """Response for tax application counts."""

    counts: dict[str, int]
