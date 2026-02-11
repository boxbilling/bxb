"""Payment model for tracking invoice payments."""

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Numeric, String, Text, func

from app.core.database import Base
from app.models.customer import UUIDType


class PaymentStatus(str, Enum):
    """Payment status enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELED = "canceled"


class PaymentProvider(str, Enum):
    """Supported payment providers."""

    STRIPE = "stripe"
    MANUAL = "manual"  # For manual/offline payments
    UCP = "ucp"  # Universal Commerce Protocol (https://ucp.dev)


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(UTC)


class Payment(Base):
    """Payment model - tracks payment attempts for invoices."""

    __tablename__ = "payments"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    invoice_id = Column(
        UUIDType, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id = Column(
        UUIDType, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Payment details
    amount = Column(Numeric(12, 4), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    status = Column(String(20), nullable=False, default=PaymentStatus.PENDING.value)

    # Provider info
    provider = Column(String(50), nullable=False, default=PaymentProvider.STRIPE.value)
    provider_payment_id = Column(String(255), nullable=True, index=True)
    provider_checkout_id = Column(String(255), nullable=True)
    provider_checkout_url = Column(Text, nullable=True)

    # Extra data
    failure_reason = Column(Text, nullable=True)
    payment_metadata = Column(JSON, nullable=True, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
