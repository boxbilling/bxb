from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class FeatureType(str, Enum):
    BOOLEAN = "boolean"
    QUANTITY = "quantity"
    CUSTOM = "custom"


class Feature(Base):
    __tablename__ = "features"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_features_org_code"),
    )

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
    description = Column(String, nullable=True)
    feature_type = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
