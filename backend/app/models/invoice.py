import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.sqlite import JSON

from app.core.database import Base
from app.models.customer import UUIDType


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    PAID = "paid"
    VOIDED = "voided"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUIDType, primary_key=True, default=lambda: uuid.uuid4())
    invoice_number = Column(String(50), unique=True, index=True, nullable=False)
    customer_id = Column(UUIDType, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False)
    subscription_id = Column(
        UUIDType, ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=True
    )
    status = Column(String(20), nullable=False, default=InvoiceStatus.DRAFT.value)

    # Billing period
    billing_period_start = Column(DateTime(timezone=True), nullable=False)
    billing_period_end = Column(DateTime(timezone=True), nullable=False)

    # Amounts (stored as Decimal with 4 decimal places for precision)
    subtotal = Column(Numeric(12, 4), nullable=False, default=0)
    tax_amount = Column(Numeric(12, 4), nullable=False, default=0)
    total = Column(Numeric(12, 4), nullable=False, default=0)
    prepaid_credit_amount = Column(Numeric(12, 4), nullable=False, default=0)
    coupons_amount_cents = Column(Numeric(12, 4), nullable=False, default=0)

    currency = Column(String(3), nullable=False, default="USD")

    # Line items stored as JSON array
    line_items = Column(JSON, nullable=False, default=list)

    # Dates
    due_date = Column(DateTime(timezone=True), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
