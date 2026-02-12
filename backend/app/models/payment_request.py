"""PaymentRequest model for batched payment collection."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class PaymentRequest(Base):
    """PaymentRequest model - groups outstanding invoices for batch payment processing."""

    __tablename__ = "payment_requests"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    customer_id = Column(
        UUIDType,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    dunning_campaign_id = Column(
        UUIDType,
        ForeignKey("dunning_campaigns.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount_cents = Column(Numeric(12, 4), nullable=False)
    amount_currency = Column(String(3), nullable=False)
    payment_status = Column(String(20), nullable=False, default="pending")
    payment_attempts = Column(Integer, nullable=False, default=0)
    ready_for_payment_processing = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
