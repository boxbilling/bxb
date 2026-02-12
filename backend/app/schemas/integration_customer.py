from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntegrationCustomerCreate(BaseModel):
    integration_id: UUID
    customer_id: UUID
    external_customer_id: str = Field(..., min_length=1, max_length=255)
    settings: dict[str, Any] | None = None


class IntegrationCustomerUpdate(BaseModel):
    external_customer_id: str | None = Field(default=None, min_length=1, max_length=255)
    settings: dict[str, Any] | None = None


class IntegrationCustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    integration_id: UUID
    customer_id: UUID
    external_customer_id: str
    settings: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
