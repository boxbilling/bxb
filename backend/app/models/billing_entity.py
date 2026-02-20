
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base
from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class BillingEntity(Base):
    __tablename__ = "billing_entities"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    code = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    legal_name = Column(String(255), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(255), nullable=True)
    state = Column(String(255), nullable=True)
    country = Column(String(2), nullable=True)
    zip_code = Column(String(20), nullable=True)
    tax_id = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    currency = Column(String(3), nullable=False, default="USD")
    timezone = Column(String(50), nullable=False, default="UTC")
    document_locale = Column(String(10), nullable=False, default="en")
    invoice_prefix = Column(String(20), nullable=True)
    next_invoice_number = Column(Integer, nullable=False, default=1)
    invoice_grace_period = Column(Integer, nullable=False, default=0)
    net_payment_term = Column(Integer, nullable=False, default=30)
    invoice_footer = Column(String(1024), nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
