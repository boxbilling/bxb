"""AddOn model for one-time charges."""

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text, func

from app.core.database import Base
from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class AddOn(Base):
    """AddOn model for one-time charges outside the subscription cycle."""

    __tablename__ = "add_ons"

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
    description = Column(Text, nullable=True)

    amount_cents = Column(Numeric(12, 4), nullable=False)
    amount_currency = Column(String(3), nullable=False, default="USD")

    invoice_display_name = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
