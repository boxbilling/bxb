"""Integration adapter base class and factory.

Defines the abstract IntegrationAdapter interface that all provider adapters
implement, plus the factory function that returns the right adapter for a
given Integration record.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models.integration import Integration, IntegrationProviderType, IntegrationType

logger = logging.getLogger(__name__)


@dataclass
class IntegrationSyncResult:
    """Result of a sync operation."""

    success: bool
    external_id: str | None = None
    external_data: dict[str, Any] | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class IntegrationAdapter(ABC):
    """Abstract base class for integration adapters.

    Each external provider (Stripe, GoCardless, Netsuite, etc.) implements
    this interface.  The adapter is stateless — provider-specific config
    is read from the Integration.settings column.
    """

    def __init__(self, integration: Integration) -> None:
        self.integration = integration

    @abstractmethod
    def sync_customer(self, customer_id: UUID) -> IntegrationSyncResult:
        """Sync a customer to the external system."""
        ...  # pragma: no cover

    @abstractmethod
    def sync_invoice(self, invoice_id: UUID) -> IntegrationSyncResult:
        """Sync an invoice to the external system."""
        ...  # pragma: no cover

    @abstractmethod
    def sync_payment(self, payment_id: UUID) -> IntegrationSyncResult:
        """Sync a payment to the external system."""
        ...  # pragma: no cover

    @abstractmethod
    def process_webhook(self, payload: dict[str, Any]) -> IntegrationSyncResult:
        """Handle an incoming webhook from the provider."""
        ...  # pragma: no cover

    @abstractmethod
    def test_connection(self) -> IntegrationSyncResult:
        """Verify integration credentials work."""
        ...  # pragma: no cover


def get_integration_adapter(integration: Integration) -> IntegrationAdapter:
    """Factory: return the appropriate adapter for *integration*.

    Raises ``ValueError`` if the provider type is not (yet) supported.
    """
    from app.services.integrations.accounting_adapter import AccountingAdapter
    from app.services.integrations.crm_adapter import CrmAdapter

    # Map (integration_type, provider_type) → adapter class
    accounting_providers = {
        IntegrationProviderType.NETSUITE.value,
        IntegrationProviderType.XERO.value,
    }
    crm_providers = {
        IntegrationProviderType.HUBSPOT.value,
        IntegrationProviderType.SALESFORCE.value,
    }

    provider = str(integration.provider_type)
    integration_type = str(integration.integration_type)

    if integration_type == IntegrationType.ACCOUNTING.value or provider in accounting_providers:
        return AccountingAdapter(integration)

    if integration_type == IntegrationType.CRM.value or provider in crm_providers:
        return CrmAdapter(integration)

    raise ValueError(
        f"No adapter registered for integration_type={integration_type}, provider_type={provider}"
    )
