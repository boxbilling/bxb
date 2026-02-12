"""WalletTransaction schemas."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransactionType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"


class TransactionTransactionStatus(str, Enum):
    PURCHASED = "purchased"
    GRANTED = "granted"
    VOIDED = "voided"
    INVOICED = "invoiced"


class TransactionSource(str, Enum):
    MANUAL = "manual"
    INTERVAL = "interval"
    THRESHOLD = "threshold"


class WalletTransactionCreate(BaseModel):
    wallet_id: UUID
    customer_id: UUID
    transaction_type: TransactionType
    transaction_status: TransactionTransactionStatus = TransactionTransactionStatus.GRANTED
    source: TransactionSource = TransactionSource.MANUAL
    status: TransactionStatus = TransactionStatus.PENDING
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    credit_amount: Decimal = Field(default=Decimal("0"), ge=0)
    invoice_id: UUID | None = None


class WalletTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wallet_id: UUID
    customer_id: UUID
    transaction_type: str
    transaction_status: str
    source: str
    status: str
    amount: Decimal
    credit_amount: Decimal
    invoice_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
