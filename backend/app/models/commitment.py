from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class Commitment(Base):
    __tablename__ = "commitments"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    plan_id = Column(
        UUIDType, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    commitment_type = Column(String(50), nullable=False, default="minimum_commitment")
    amount_cents = Column(Numeric(12, 4), nullable=False)
    invoice_display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
