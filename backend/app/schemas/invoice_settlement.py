"""Invoice settlement schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.invoice_settlement import SettlementType


class InvoiceSettlementCreate(BaseModel):
    """Schema for creating an invoice settlement."""

    invoice_id: UUID
    settlement_type: SettlementType
    source_id: UUID
    amount_cents: Decimal


class InvoiceSettlementResponse(BaseModel):
    """Schema for invoice settlement response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID
    settlement_type: str
    source_id: UUID
    amount_cents: Decimal
    created_at: datetime
