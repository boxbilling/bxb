"""Fee model for tracking invoice line items as first-class entities."""

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.sqlite import JSON

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType


class FeeType(str, Enum):
    """Fee type enum."""

    CHARGE = "charge"
    SUBSCRIPTION = "subscription"
    ADD_ON = "add_on"
    CREDIT = "credit"
    COMMITMENT = "commitment"


class FeePaymentStatus(str, Enum):
    """Fee payment status enum."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class Fee(Base):
    """Fee model - first-class invoice line item entity."""

    __tablename__ = "fees"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    invoice_id = Column(
        UUIDType, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    charge_id = Column(
        UUIDType, ForeignKey("charges.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    subscription_id = Column(
        UUIDType, ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    customer_id = Column(
        UUIDType, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    commitment_id = Column(
        UUIDType, ForeignKey("commitments.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    # Fee classification
    fee_type = Column(String(20), nullable=False, default=FeeType.CHARGE.value, index=True)

    # Amounts (stored as Decimal with 4 decimal places for precision)
    amount_cents = Column(Numeric(12, 4), nullable=False, default=0)
    taxes_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)
    total_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)

    # Usage details
    units = Column(Numeric(12, 4), nullable=False, default=0)
    events_count = Column(Integer, nullable=False, default=0)
    unit_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)

    # Payment tracking
    payment_status = Column(
        String(20), nullable=False, default=FeePaymentStatus.PENDING.value, index=True
    )

    # Descriptive fields
    description = Column(String(500), nullable=True)
    metric_code = Column(String(255), nullable=True)

    # Charge model properties snapshot
    properties = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
