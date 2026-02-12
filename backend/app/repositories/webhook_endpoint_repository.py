"""WebhookEndpoint repository for data access."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.webhook_endpoint import WebhookEndpoint
from app.schemas.webhook import WebhookEndpointCreate, WebhookEndpointUpdate


class WebhookEndpointRepository:
    """Repository for WebhookEndpoint model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> list[WebhookEndpoint]:
        """Get all webhook endpoints."""
        return (
            self.db.query(WebhookEndpoint)
            .order_by(WebhookEndpoint.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id(self, endpoint_id: UUID) -> WebhookEndpoint | None:
        """Get a webhook endpoint by ID."""
        return self.db.query(WebhookEndpoint).filter(WebhookEndpoint.id == endpoint_id).first()

    def get_active(self) -> list[WebhookEndpoint]:
        """Get all active webhook endpoints."""
        return (
            self.db.query(WebhookEndpoint)
            .filter(WebhookEndpoint.status == "active")
            .order_by(WebhookEndpoint.created_at.desc())
            .all()
        )

    def create(self, data: WebhookEndpointCreate) -> WebhookEndpoint:
        """Create a new webhook endpoint."""
        endpoint = WebhookEndpoint(
            url=data.url,
            signature_algo=data.signature_algo,
        )
        self.db.add(endpoint)
        self.db.commit()
        self.db.refresh(endpoint)
        return endpoint

    def update(self, endpoint_id: UUID, data: WebhookEndpointUpdate) -> WebhookEndpoint | None:
        """Update a webhook endpoint by ID."""
        endpoint = self.get_by_id(endpoint_id)
        if not endpoint:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(endpoint, key, value)

        self.db.commit()
        self.db.refresh(endpoint)
        return endpoint

    def delete(self, endpoint_id: UUID) -> bool:
        """Delete a webhook endpoint by ID."""
        endpoint = self.get_by_id(endpoint_id)
        if not endpoint:
            return False

        self.db.delete(endpoint)
        self.db.commit()
        return True
