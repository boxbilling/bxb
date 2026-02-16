"""IntegrationMapping repository for data access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.integration_mapping import IntegrationMapping
from app.schemas.integration_mapping import IntegrationMappingCreate, IntegrationMappingUpdate


class IntegrationMappingRepository:
    """Repository for IntegrationMapping model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        integration_id: UUID,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[IntegrationMapping]:
        """Get all mappings for an integration."""
        query = (
            self.db.query(IntegrationMapping)
            .filter(IntegrationMapping.integration_id == integration_id)
        )
        query = apply_order_by(query, IntegrationMapping, order_by)
        return query.offset(skip).limit(limit).all()

    def get_by_id(self, mapping_id: UUID) -> IntegrationMapping | None:
        """Get a mapping by ID."""
        return self.db.query(IntegrationMapping).filter(IntegrationMapping.id == mapping_id).first()

    def get_by_mappable(
        self,
        integration_id: UUID,
        mappable_type: str,
        mappable_id: UUID,
    ) -> IntegrationMapping | None:
        """Get a mapping by integration, type, and resource ID."""
        return (
            self.db.query(IntegrationMapping)
            .filter(
                IntegrationMapping.integration_id == integration_id,
                IntegrationMapping.mappable_type == mappable_type,
                IntegrationMapping.mappable_id == mappable_id,
            )
            .first()
        )

    def get_by_external_id(
        self,
        integration_id: UUID,
        external_id: str,
    ) -> list[IntegrationMapping]:
        """Get mappings by external ID."""
        return (
            self.db.query(IntegrationMapping)
            .filter(
                IntegrationMapping.integration_id == integration_id,
                IntegrationMapping.external_id == external_id,
            )
            .all()
        )

    def create(self, data: IntegrationMappingCreate) -> IntegrationMapping:
        """Create a new integration mapping."""
        mapping = IntegrationMapping(
            integration_id=data.integration_id,
            mappable_type=data.mappable_type,
            mappable_id=data.mappable_id,
            external_id=data.external_id,
            external_data=data.external_data,
        )
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def update(self, mapping_id: UUID, data: IntegrationMappingUpdate) -> IntegrationMapping | None:
        """Update a mapping."""
        mapping = self.get_by_id(mapping_id)
        if not mapping:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(mapping, key, value)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def delete(self, mapping_id: UUID) -> bool:
        """Delete a mapping."""
        mapping = self.get_by_id(mapping_id)
        if not mapping:
            return False
        self.db.delete(mapping)
        self.db.commit()
        return True
