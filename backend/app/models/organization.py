import uuid

from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.database import Base
from app.models.customer import UUIDType


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    default_currency = Column(String(3), nullable=False, default="USD")
    timezone = Column(String(50), nullable=False, default="UTC")
    hmac_key = Column(String(255), nullable=True)
    document_number_prefix = Column(String(20), nullable=True)
    invoice_grace_period = Column(Integer, nullable=False, default=0)
    net_payment_term = Column(Integer, nullable=False, default=30)
    logo_url = Column(String(2048), nullable=True)
    email = Column(String(255), nullable=True)
    portal_accent_color = Column(String(7), nullable=True)
    portal_welcome_message = Column(String(500), nullable=True)
    legal_name = Column(String(255), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(255), nullable=True)
    state = Column(String(255), nullable=True)
    zipcode = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
