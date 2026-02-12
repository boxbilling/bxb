from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommitmentCreate(BaseModel):
    plan_id: UUID
    commitment_type: str = Field(default="minimum_commitment", max_length=50)
    amount_cents: Decimal = Field(..., ge=0)
    invoice_display_name: str | None = Field(default=None, max_length=255)


class CommitmentUpdate(BaseModel):
    commitment_type: str | None = Field(default=None, max_length=50)
    amount_cents: Decimal | None = Field(default=None, ge=0)
    invoice_display_name: str | None = Field(default=None, max_length=255)


class CommitmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan_id: UUID
    commitment_type: str
    amount_cents: Decimal
    invoice_display_name: str | None = None
    created_at: datetime
    updated_at: datetime
