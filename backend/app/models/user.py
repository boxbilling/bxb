from sqlalchemy import Boolean, Column, DateTime, String, func

from app.core.database import Base
from app.models.shared import UUIDType, generate_uuid


class User(Base):
    __tablename__ = "users"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
