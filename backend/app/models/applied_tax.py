"""AppliedTax model for polymorphic tax associations."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func

from app.core.database import Base
from app.models.shared import UUIDType, generate_uuid


class AppliedTax(Base):
    """AppliedTax model for polymorphic tax associations to various entities."""

    __tablename__ = "applied_taxes"
    __table_args__ = (
        UniqueConstraint("tax_id", "taxable_type", "taxable_id", name="uq_applied_taxes_unique"),
        Index("ix_applied_taxes_taxable", "taxable_type", "taxable_id"),
    )

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    tax_id = Column(
        UUIDType, ForeignKey("taxes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    taxable_type = Column(String(50), nullable=False)
    taxable_id = Column(UUIDType, nullable=False)
    tax_rate = Column(Numeric(5, 4), nullable=True)
    tax_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
