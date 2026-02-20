"""PaymentMethod model for storing customer payment methods."""


from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, func

from app.core.database import Base
from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class PaymentMethod(Base):
    """PaymentMethod model - stores saved payment methods for customers."""

    __tablename__ = "payment_methods"

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

    # Provider info
    provider = Column(String(50), nullable=False)  # stripe / gocardless / adyen
    provider_payment_method_id = Column(String(255), nullable=False)

    # Payment method type
    type = Column(String(50), nullable=False)  # card / bank_account / direct_debit

    # Default flag
    is_default = Column(Boolean, nullable=False, default=False)

    # Extra details (last4, brand, exp_month, exp_year, etc.)
    details = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
