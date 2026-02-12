"""IntegrationMapping model for mapping bxb resources to external system IDs."""

import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, UniqueConstraint, func

from app.core.database import Base
from app.models.customer import UUIDType


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class IntegrationMapping(Base):
    """Maps bxb resources (customer, invoice, etc.) to their external system IDs."""

    __tablename__ = "integration_mappings"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "mappable_type",
            "mappable_id",
            name="uq_integration_mappings_integration_type_id",
        ),
    )

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    integration_id = Column(
        UUIDType,
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mappable_type = Column(String(50), nullable=False)
    mappable_id = Column(UUIDType, nullable=False)
    external_id = Column(String(255), nullable=False)
    external_data = Column(JSON, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
