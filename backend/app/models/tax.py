"""Tax model for configurable tax rates."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Text, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class Tax(Base):
    """Tax model for configurable tax rates."""

    __tablename__ = "taxes"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    code = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    rate = Column(Numeric(5, 4), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    applied_to_organization = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
