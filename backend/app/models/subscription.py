import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, String, func

from app.core.database import Base
from app.models.customer import UUIDType


class SubscriptionStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CANCELED = "canceled"
    TERMINATED = "terminated"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUIDType, primary_key=True, default=lambda: uuid.uuid4())
    external_id = Column(String(255), unique=True, index=True, nullable=False)
    customer_id = Column(
        UUIDType,
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    plan_id = Column(
        UUIDType,
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = Column(String(20), nullable=False, default=SubscriptionStatus.PENDING.value)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ending_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
