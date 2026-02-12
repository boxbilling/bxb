"""PaymentRequestInvoice join table linking payment requests to invoices."""

from sqlalchemy import Column, DateTime, ForeignKey, func

from app.core.database import Base
from app.models.customer import UUIDType, generate_uuid


class PaymentRequestInvoice(Base):
    """Join table linking PaymentRequests to Invoices."""

    __tablename__ = "payment_request_invoices"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    payment_request_id = Column(
        UUIDType,
        ForeignKey("payment_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        UUIDType,
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
