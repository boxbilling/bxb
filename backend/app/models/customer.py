from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base
from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid, utc_now

__all__ = ["DEFAULT_ORGANIZATION_ID", "UUIDType", "generate_uuid", "utc_now", "Customer"]


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    external_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    timezone = Column(String(50), nullable=False, default="UTC")
    billing_metadata = Column(JSON, nullable=False, default=dict)
    invoice_grace_period = Column(Integer, nullable=False, default=0)
    net_payment_term = Column(Integer, nullable=False, default=30)
    billing_entity_id = Column(
        UUIDType,
        ForeignKey("billing_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
