import uuid
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base
from app.models.customer import DEFAULT_ORGANIZATION_ID, UUIDType


class SubscriptionStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CANCELED = "canceled"
    TERMINATED = "terminated"


class BillingTime(str, Enum):
    CALENDAR = "calendar"
    ANNIVERSARY = "anniversary"


class TerminationAction(str, Enum):
    GENERATE_INVOICE = "generate_invoice"
    GENERATE_CREDIT_NOTE = "generate_credit_note"
    SKIP = "skip"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUIDType, primary_key=True, default=lambda: uuid.uuid4())
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
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
    status = Column(
        String(20), nullable=False, default=SubscriptionStatus.PENDING.value, index=True
    )
    billing_time = Column(String(20), nullable=False, default=BillingTime.CALENDAR.value)
    trial_period_days = Column(Integer, nullable=False, default=0)
    trial_ended_at = Column(DateTime(timezone=True), nullable=True)
    subscription_at = Column(DateTime(timezone=True), nullable=True)
    pay_in_advance = Column(Boolean, nullable=False, default=False)
    previous_plan_id = Column(
        UUIDType,
        ForeignKey("plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    downgraded_at = Column(DateTime(timezone=True), nullable=True)
    billing_entity_id = Column(
        UUIDType,
        ForeignKey("billing_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    on_termination_action = Column(
        String(30), nullable=False, default=TerminationAction.GENERATE_INVOICE.value
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    ending_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
