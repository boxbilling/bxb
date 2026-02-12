"""Integration repository for data access."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.integration import Integration
from app.schemas.integration import IntegrationCreate, IntegrationUpdate


class IntegrationRepository:
    """Repository for Integration model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Integration]:
        """Get all integrations for an organization."""
        return (
            self.db.query(Integration)
            .filter(Integration.organization_id == organization_id)
            .order_by(Integration.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id(
        self,
        integration_id: UUID,
        organization_id: UUID | None = None,
    ) -> Integration | None:
        """Get an integration by ID."""
        query = self.db.query(Integration).filter(Integration.id == integration_id)
        if organization_id is not None:
            query = query.filter(Integration.organization_id == organization_id)
        return query.first()

    def get_by_provider(
        self,
        organization_id: UUID,
        provider_type: str,
    ) -> Integration | None:
        """Get an integration by provider type for an organization."""
        return (
            self.db.query(Integration)
            .filter(
                Integration.organization_id == organization_id,
                Integration.provider_type == provider_type,
            )
            .first()
        )

    def create(self, data: IntegrationCreate, organization_id: UUID) -> Integration:
        """Create a new integration."""
        integration = Integration(
            organization_id=organization_id,
            integration_type=data.integration_type,
            provider_type=data.provider_type,
            status=data.status,
            settings=data.settings,
        )
        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)
        return integration

    def update(
        self,
        integration_id: UUID,
        data: IntegrationUpdate,
        organization_id: UUID,
    ) -> Integration | None:
        """Update an integration."""
        integration = self.get_by_id(integration_id, organization_id)
        if not integration:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(integration, key, value)
        self.db.commit()
        self.db.refresh(integration)
        return integration

    def delete(self, integration_id: UUID, organization_id: UUID) -> bool:
        """Delete an integration."""
        integration = self.get_by_id(integration_id, organization_id)
        if not integration:
            return False
        self.db.delete(integration)
        self.db.commit()
        return True
