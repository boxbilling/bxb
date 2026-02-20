from sqlalchemy import Column, DateTime, String, func

from app.core.database import Base
from app.models.shared import UUIDType, generate_uuid


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    default_currency = Column(String(3), nullable=False, default="USD")
    timezone = Column(String(50), nullable=False, default="UTC")
    hmac_key = Column(String(255), nullable=True)
    logo_url = Column(String(2048), nullable=True)
    portal_accent_color = Column(String(7), nullable=True)
    portal_welcome_message = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
