"""AppliedAddOn model for tracking add-on applications to customers."""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func

from app.core.database import Base
from app.models.customer import UUIDType


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class AppliedAddOn(Base):
    """AppliedAddOn model for tracking add-on applications to customers."""

    __tablename__ = "applied_add_ons"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    add_on_id = Column(
        UUIDType, ForeignKey("add_ons.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id = Column(
        UUIDType, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    amount_cents = Column(Numeric(12, 4), nullable=False)
    amount_currency = Column(String(3), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
