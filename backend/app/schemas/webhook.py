"""Webhook and WebhookEndpoint schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WebhookEndpointCreate(BaseModel):
    url: str = Field(max_length=2048)
    signature_algo: str = Field(default="hmac", max_length=50)


class WebhookEndpointUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=2048)
    signature_algo: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, max_length=50)


class WebhookEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    signature_algo: str
    status: str
    created_at: datetime
    updated_at: datetime


class WebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    webhook_endpoint_id: UUID
    webhook_type: str
    object_type: str | None = None
    object_id: UUID | None = None
    payload: dict[str, Any]
    status: str
    retries: int
    max_retries: int
    last_retried_at: datetime | None = None
    http_status: int | None = None
    response: str | None = None
    created_at: datetime
    updated_at: datetime


class WebhookEventPayload(BaseModel):
    webhook_type: str = Field(max_length=100)
    object_type: str | None = Field(default=None, max_length=50)
    object_id: UUID | None = None
    payload: dict[str, Any]
