"""Schema for subscription lifecycle timeline events."""

from datetime import datetime

from pydantic import BaseModel


class LifecycleEvent(BaseModel):
    """A single event in the subscription lifecycle timeline."""

    timestamp: datetime
    event_type: str  # subscription, invoice, payment, status_change
    title: str
    description: str | None = None
    status: str | None = None  # For color-coding (e.g., active, paid, failed)
    resource_id: str | None = None  # ID of related resource
    resource_type: str | None = None  # Type of related resource
    metadata: dict[str, str] | None = None  # Extra context


class SubscriptionLifecycleResponse(BaseModel):
    """Full lifecycle timeline for a subscription."""

    events: list[LifecycleEvent]
