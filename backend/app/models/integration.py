"""Integration model for external system connections."""

from enum import Enum

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, UniqueConstraint, func

from app.core.database import Base
from app.models.shared import DEFAULT_ORGANIZATION_ID, UUIDType, generate_uuid


class IntegrationType(str, Enum):
    """Types of integrations."""

    PAYMENT_PROVIDER = "payment_provider"
    ACCOUNTING = "accounting"
    CRM = "crm"
    TAX = "tax"


class IntegrationProviderType(str, Enum):
    """Supported integration providers."""

    STRIPE = "stripe"
    GOCARDLESS = "gocardless"
    ADYEN = "adyen"
    NETSUITE = "netsuite"
    XERO = "xero"
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    ANROK = "anrok"
    AVALARA = "avalara"


class IntegrationStatus(str, Enum):
    """Integration connection status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class Integration(Base):
    """Integration model — represents a connection to an external system."""

    __tablename__ = "integrations"
    __table_args__ = (
        UniqueConstraint("organization_id", "provider_type", name="uq_integrations_org_provider"),
    )

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=DEFAULT_ORGANIZATION_ID,
    )
    integration_type = Column(String(30), nullable=False)
    provider_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default=IntegrationStatus.ACTIVE.value)
    settings = Column(JSON, nullable=False, default=dict)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    error_details = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
