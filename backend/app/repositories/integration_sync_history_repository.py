"""IntegrationSyncHistory repository for data access."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.integration_sync_history import IntegrationSyncHistory
from app.schemas.integration_sync_history import IntegrationSyncHistoryCreate


class IntegrationSyncHistoryRepository:
    """Repository for IntegrationSyncHistory model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        integration_id: UUID,
        status: str | None = None,
        resource_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[IntegrationSyncHistory]:
        """Get sync history for an integration with optional filters."""
        query = self.db.query(IntegrationSyncHistory).filter(
            IntegrationSyncHistory.integration_id == integration_id
        )
        if status is not None:
            query = query.filter(IntegrationSyncHistory.status == status)
        if resource_type is not None:
            query = query.filter(IntegrationSyncHistory.resource_type == resource_type)
        return (
            query.order_by(IntegrationSyncHistory.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id(self, sync_id: UUID) -> IntegrationSyncHistory | None:
        """Get a sync history entry by ID."""
        return (
            self.db.query(IntegrationSyncHistory)
            .filter(IntegrationSyncHistory.id == sync_id)
            .first()
        )

    def create(self, data: IntegrationSyncHistoryCreate) -> IntegrationSyncHistory:
        """Create a new sync history entry."""
        entry = IntegrationSyncHistory(
            integration_id=data.integration_id,
            resource_type=data.resource_type,
            resource_id=data.resource_id,
            external_id=data.external_id,
            action=data.action,
            status=data.status,
            error_message=data.error_message,
            details=data.details,
            completed_at=data.completed_at,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry
