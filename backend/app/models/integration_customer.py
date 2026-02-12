"""IntegrationCustomer model for linking customers to external system customers."""

import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, UniqueConstraint, func

from app.core.database import Base
from app.models.customer import UUIDType


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class IntegrationCustomer(Base):
    """Links a bxb customer to their representation in an external system."""

    __tablename__ = "integration_customers"
    __table_args__ = (
        UniqueConstraint(
            "integration_id", "customer_id",
            name="uq_integration_customers_integration_customer",
        ),
    )

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    integration_id = Column(
        UUIDType,
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id = Column(
        UUIDType,
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_customer_id = Column(String(255), nullable=False)
    settings = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
