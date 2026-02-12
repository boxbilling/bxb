"""Accounting adapter (Netsuite / Xero).

Placeholder implementations that log and return success.  Actual provider
API calls will be added when the concrete providers are built.
"""

import logging
from typing import Any
from uuid import UUID

from app.models.integration import Integration
from app.services.integrations.base import IntegrationAdapter, IntegrationSyncResult

logger = logging.getLogger(__name__)


class AccountingAdapter(IntegrationAdapter):
    """Base accounting adapter for Netsuite / Xero integrations."""

    def __init__(self, integration: Integration) -> None:
        super().__init__(integration)

    def sync_customer(self, customer_id: UUID) -> IntegrationSyncResult:
        """Sync customer to accounting system (placeholder)."""
        logger.info(
            "AccountingAdapter.sync_customer: provider=%s customer_id=%s",
            self.integration.provider_type,
            customer_id,
        )
        return IntegrationSyncResult(
            success=True,
            external_id=f"acct_cus_{customer_id}",
            details={"action": "sync_customer", "provider": str(self.integration.provider_type)},
        )

    def sync_invoice(self, invoice_id: UUID) -> IntegrationSyncResult:
        """Sync invoice to accounting system (placeholder)."""
        logger.info(
            "AccountingAdapter.sync_invoice: provider=%s invoice_id=%s",
            self.integration.provider_type,
            invoice_id,
        )
        return IntegrationSyncResult(
            success=True,
            external_id=f"acct_inv_{invoice_id}",
            details={"action": "sync_invoice", "provider": str(self.integration.provider_type)},
        )

    def sync_payment(self, payment_id: UUID) -> IntegrationSyncResult:
        """Sync payment to accounting system (placeholder)."""
        logger.info(
            "AccountingAdapter.sync_payment: provider=%s payment_id=%s",
            self.integration.provider_type,
            payment_id,
        )
        return IntegrationSyncResult(
            success=True,
            external_id=f"acct_pay_{payment_id}",
            details={"action": "sync_payment", "provider": str(self.integration.provider_type)},
        )

    def sync_credit_note(self, credit_note_id: UUID) -> IntegrationSyncResult:
        """Sync credit note to accounting system (placeholder)."""
        logger.info(
            "AccountingAdapter.sync_credit_note: provider=%s credit_note_id=%s",
            self.integration.provider_type,
            credit_note_id,
        )
        return IntegrationSyncResult(
            success=True,
            external_id=f"acct_cn_{credit_note_id}",
            details={"action": "sync_credit_note", "provider": str(self.integration.provider_type)},
        )

    def process_webhook(self, payload: dict[str, Any]) -> IntegrationSyncResult:
        """Handle incoming webhook from accounting provider (placeholder)."""
        logger.info(
            "AccountingAdapter.process_webhook: provider=%s",
            self.integration.provider_type,
        )
        return IntegrationSyncResult(
            success=True,
            details={"action": "process_webhook", "provider": str(self.integration.provider_type)},
        )

    def test_connection(self) -> IntegrationSyncResult:
        """Verify accounting integration credentials (placeholder)."""
        logger.info(
            "AccountingAdapter.test_connection: provider=%s",
            self.integration.provider_type,
        )
        return IntegrationSyncResult(
            success=True,
            details={"action": "test_connection", "provider": str(self.integration.provider_type)},
        )
