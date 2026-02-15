"""Wallet schemas."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WalletStatus(str, Enum):
    ACTIVE = "active"
    TERMINATED = "terminated"


class WalletCreate(BaseModel):
    customer_id: UUID
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=255)
    rate_amount: Decimal = Field(default=Decimal("1"), gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    expiration_at: datetime | None = None
    priority: int = Field(default=1, ge=1, le=50)
    initial_granted_credits: Decimal | None = Field(default=None, ge=0)


class WalletUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    expiration_at: datetime | None = None
    priority: int | None = Field(default=None, ge=1, le=50)


class WalletTopUp(BaseModel):
    credits: Decimal = Field(gt=0)
    source: str = Field(default="manual", pattern="^(manual|interval|threshold)$")


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    name: str | None = None
    code: str | None = None
    status: str
    balance_cents: Decimal
    credits_balance: Decimal
    consumed_amount_cents: Decimal
    consumed_credits: Decimal
    rate_amount: Decimal
    currency: str
    expiration_at: datetime | None = None
    priority: int
    created_at: datetime
    updated_at: datetime


class BalanceTimelinePoint(BaseModel):
    date: str
    inbound: Decimal
    outbound: Decimal
    balance: Decimal


class BalanceTimelineResponse(BaseModel):
    wallet_id: UUID
    points: list[BalanceTimelinePoint]


class DepletionForecastResponse(BaseModel):
    wallet_id: UUID
    current_balance_cents: Decimal
    avg_daily_consumption: Decimal
    projected_depletion_date: datetime | None = None
    days_remaining: int | None = None


class WalletTransferRequest(BaseModel):
    source_wallet_id: UUID
    target_wallet_id: UUID
    credits: Decimal = Field(gt=0)


class WalletTransferResponse(BaseModel):
    source_wallet: WalletResponse
    target_wallet: WalletResponse
    credits_transferred: Decimal
