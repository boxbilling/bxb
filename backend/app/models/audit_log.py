"""AuditLog model for tracking all state changes to billing entities."""


from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class AuditLog(Base):
    """AuditLog model - records state changes to billing entities."""

    __tablename__ = "audit_logs"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(UUIDType, nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    changes = Column(JSON, nullable=False, default=dict)
    actor_type = Column(String(50), nullable=False)
    actor_id = Column(String(255), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
