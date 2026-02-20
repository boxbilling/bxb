"""IdempotencyRecord model for API request-level idempotency."""

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func

from app.core.database import Base
from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class IdempotencyRecord(Base):
    """Stores cached responses for idempotent API requests."""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_org_idempotency_key"),
    )

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    idempotency_key = Column(String(255), nullable=False, index=True)
    request_method = Column(String(10), nullable=False)
    request_path = Column(String(500), nullable=False)
    response_status = Column(Integer, nullable=True)
    response_body = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
