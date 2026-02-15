"""DunningCampaign schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DunningCampaignPerformanceStats(BaseModel):
    """Performance statistics for dunning campaigns."""

    total_campaigns: int
    active_campaigns: int
    total_payment_requests: int
    succeeded_requests: int
    failed_requests: int
    pending_requests: int
    recovery_rate: float
    total_recovered_amount_cents: Decimal
    total_outstanding_amount_cents: Decimal


class DunningCampaignThresholdCreate(BaseModel):
    """Schema for creating a dunning campaign threshold."""

    currency: str = Field(..., min_length=3, max_length=3)
    amount_cents: Decimal = Field(..., ge=0)


class DunningCampaignThresholdResponse(BaseModel):
    """Schema for dunning campaign threshold response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dunning_campaign_id: UUID
    currency: str
    amount_cents: Decimal
    created_at: datetime
    updated_at: datetime


class DunningCampaignCreate(BaseModel):
    """Schema for creating a dunning campaign."""

    code: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    max_attempts: int = Field(default=3, ge=1)
    days_between_attempts: int = Field(default=3, ge=1)
    bcc_emails: list[str] = Field(default_factory=list)
    status: str = Field(default="active", pattern=r"^(active|inactive)$")
    thresholds: list[DunningCampaignThresholdCreate] = Field(default_factory=list)


class DunningCampaignUpdate(BaseModel):
    """Schema for updating a dunning campaign."""

    code: str | None = Field(default=None, min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    max_attempts: int | None = Field(default=None, ge=1)
    days_between_attempts: int | None = Field(default=None, ge=1)
    bcc_emails: list[str] | None = None
    status: str | None = Field(default=None, pattern=r"^(active|inactive)$")
    thresholds: list[DunningCampaignThresholdCreate] | None = None


class DunningCampaignResponse(BaseModel):
    """Schema for dunning campaign response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    code: str
    name: str
    description: str | None = None
    max_attempts: int
    days_between_attempts: int
    bcc_emails: list[str]
    status: str
    thresholds: list[DunningCampaignThresholdResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
