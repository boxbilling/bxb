"""Data export repository for data access."""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.data_export import DataExport
from app.schemas.data_export import DataExportCreate


class DataExportRepository:
    """Repository for DataExport model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DataExport]:
        """List all data exports for an organization."""
        return (
            self.db.query(DataExport)
            .filter(DataExport.organization_id == organization_id)
            .order_by(DataExport.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, organization_id: UUID) -> int:
        """Count data exports for an organization."""
        return (
            self.db.query(func.count(DataExport.id))
            .filter(DataExport.organization_id == organization_id)
            .scalar()
            or 0
        )

    def get_by_id(self, export_id: UUID, organization_id: UUID | None = None) -> DataExport | None:
        """Get a data export by ID."""
        query = self.db.query(DataExport).filter(DataExport.id == export_id)
        if organization_id is not None:
            query = query.filter(DataExport.organization_id == organization_id)
        return query.first()

    def create(self, data: DataExportCreate, organization_id: UUID) -> DataExport:
        """Create a new data export record."""
        export = DataExport(
            organization_id=organization_id,
            export_type=data.export_type.value,
            filters=data.filters,
        )
        self.db.add(export)
        self.db.commit()
        self.db.refresh(export)
        return export

    def update_status(
        self,
        export_id: UUID,
        **kwargs: object,
    ) -> DataExport | None:
        """Update a data export's status and related fields."""
        export = self.db.query(DataExport).filter(DataExport.id == export_id).first()
        if not export:
            return None
        for key, value in kwargs.items():
            setattr(export, key, value)
        self.db.commit()
        self.db.refresh(export)
        return export
