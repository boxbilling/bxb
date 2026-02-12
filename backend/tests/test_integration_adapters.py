"""Tests for IntegrationAdapter base class, factory, and provider adapters."""

from uuid import uuid4

import pytest

from app.core.database import get_db
from app.repositories.integration_repository import IntegrationRepository
from app.schemas.integration import IntegrationCreate
from app.services.integrations.accounting_adapter import AccountingAdapter
from app.services.integrations.base import IntegrationSyncResult, get_integration_adapter
from app.services.integrations.crm_adapter import CrmAdapter
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def netsuite_integration(db_session):
    """Create a Netsuite accounting integration."""
    repo = IntegrationRepository(db_session)
    return repo.create(
        IntegrationCreate(
            integration_type="accounting",
            provider_type="netsuite",
            settings={"account_id": "NS_123", "token": "tok_abc"},
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def xero_integration(db_session):
    """Create a Xero accounting integration."""
    repo = IntegrationRepository(db_session)
    return repo.create(
        IntegrationCreate(
            integration_type="accounting",
            provider_type="xero",
            settings={"tenant_id": "xero_tenant"},
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def hubspot_integration(db_session):
    """Create a HubSpot CRM integration."""
    repo = IntegrationRepository(db_session)
    return repo.create(
        IntegrationCreate(
            integration_type="crm",
            provider_type="hubspot",
            settings={"api_key": "hs_key_123"},
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def salesforce_integration(db_session):
    """Create a Salesforce CRM integration."""
    repo = IntegrationRepository(db_session)
    return repo.create(
        IntegrationCreate(
            integration_type="crm",
            provider_type="salesforce",
            settings={"client_id": "sf_client", "client_secret": "sf_secret"},
        ),
        DEFAULT_ORG_ID,
    )


# ─────────────────────────────────────────────────────────────────────────────
# IntegrationSyncResult Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationSyncResult:
    """Tests for the IntegrationSyncResult dataclass."""

    def test_success_result(self):
        result = IntegrationSyncResult(success=True, external_id="ext_1")
        assert result.success is True
        assert result.external_id == "ext_1"
        assert result.external_data is None
        assert result.error is None
        assert result.details == {}

    def test_failure_result(self):
        result = IntegrationSyncResult(success=False, error="Connection timeout")
        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.external_id is None

    def test_full_result(self):
        result = IntegrationSyncResult(
            success=True,
            external_id="ext_123",
            external_data={"name": "Test"},
            details={"action": "sync"},
        )
        assert result.external_data == {"name": "Test"}
        assert result.details == {"action": "sync"}


# ─────────────────────────────────────────────────────────────────────────────
# Factory Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestGetIntegrationAdapter:
    """Tests for the get_integration_adapter factory function."""

    def test_netsuite_returns_accounting_adapter(self, netsuite_integration):
        adapter = get_integration_adapter(netsuite_integration)
        assert isinstance(adapter, AccountingAdapter)
        assert adapter.integration is netsuite_integration

    def test_xero_returns_accounting_adapter(self, xero_integration):
        adapter = get_integration_adapter(xero_integration)
        assert isinstance(adapter, AccountingAdapter)
        assert adapter.integration is xero_integration

    def test_hubspot_returns_crm_adapter(self, hubspot_integration):
        adapter = get_integration_adapter(hubspot_integration)
        assert isinstance(adapter, CrmAdapter)
        assert adapter.integration is hubspot_integration

    def test_salesforce_returns_crm_adapter(self, salesforce_integration):
        adapter = get_integration_adapter(salesforce_integration)
        assert isinstance(adapter, CrmAdapter)
        assert adapter.integration is salesforce_integration

    def test_unsupported_provider_raises(self, db_session):
        repo = IntegrationRepository(db_session)
        integration = repo.create(
            IntegrationCreate(
                integration_type="payment_provider",
                provider_type="stripe",
                settings={},
            ),
            DEFAULT_ORG_ID,
        )
        with pytest.raises(ValueError, match="No adapter registered"):
            get_integration_adapter(integration)


# ─────────────────────────────────────────────────────────────────────────────
# AccountingAdapter Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAccountingAdapter:
    """Tests for the AccountingAdapter placeholder implementation."""

    def test_sync_customer(self, netsuite_integration):
        adapter = AccountingAdapter(netsuite_integration)
        cid = uuid4()
        result = adapter.sync_customer(cid)
        assert result.success is True
        assert result.external_id == f"acct_cus_{cid}"
        assert result.details["action"] == "sync_customer"
        assert result.details["provider"] == "netsuite"

    def test_sync_invoice(self, netsuite_integration):
        adapter = AccountingAdapter(netsuite_integration)
        iid = uuid4()
        result = adapter.sync_invoice(iid)
        assert result.success is True
        assert result.external_id == f"acct_inv_{iid}"
        assert result.details["action"] == "sync_invoice"

    def test_sync_payment(self, xero_integration):
        adapter = AccountingAdapter(xero_integration)
        pid = uuid4()
        result = adapter.sync_payment(pid)
        assert result.success is True
        assert result.external_id == f"acct_pay_{pid}"
        assert result.details["provider"] == "xero"

    def test_sync_credit_note(self, netsuite_integration):
        adapter = AccountingAdapter(netsuite_integration)
        cnid = uuid4()
        result = adapter.sync_credit_note(cnid)
        assert result.success is True
        assert result.external_id == f"acct_cn_{cnid}"
        assert result.details["action"] == "sync_credit_note"

    def test_process_webhook(self, xero_integration):
        adapter = AccountingAdapter(xero_integration)
        result = adapter.process_webhook({"event": "invoice.created"})
        assert result.success is True
        assert result.details["action"] == "process_webhook"
        assert result.details["provider"] == "xero"

    def test_test_connection(self, netsuite_integration):
        adapter = AccountingAdapter(netsuite_integration)
        result = adapter.test_connection()
        assert result.success is True
        assert result.details["action"] == "test_connection"
        assert result.details["provider"] == "netsuite"


# ─────────────────────────────────────────────────────────────────────────────
# CrmAdapter Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCrmAdapter:
    """Tests for the CrmAdapter placeholder implementation."""

    def test_sync_customer(self, hubspot_integration):
        adapter = CrmAdapter(hubspot_integration)
        cid = uuid4()
        result = adapter.sync_customer(cid)
        assert result.success is True
        assert result.external_id == f"crm_cus_{cid}"
        assert result.details["action"] == "sync_customer"
        assert result.details["provider"] == "hubspot"

    def test_sync_invoice(self, salesforce_integration):
        adapter = CrmAdapter(salesforce_integration)
        iid = uuid4()
        result = adapter.sync_invoice(iid)
        assert result.success is True
        assert result.external_id == f"crm_inv_{iid}"
        assert result.details["provider"] == "salesforce"

    def test_sync_payment(self, hubspot_integration):
        adapter = CrmAdapter(hubspot_integration)
        pid = uuid4()
        result = adapter.sync_payment(pid)
        assert result.success is True
        assert result.external_id == f"crm_pay_{pid}"
        assert result.details["action"] == "sync_payment"

    def test_sync_subscription(self, salesforce_integration):
        adapter = CrmAdapter(salesforce_integration)
        sid = uuid4()
        result = adapter.sync_subscription(sid)
        assert result.success is True
        assert result.external_id == f"crm_sub_{sid}"
        assert result.details["action"] == "sync_subscription"

    def test_process_webhook(self, hubspot_integration):
        adapter = CrmAdapter(hubspot_integration)
        result = adapter.process_webhook({"event": "contact.updated"})
        assert result.success is True
        assert result.details["action"] == "process_webhook"
        assert result.details["provider"] == "hubspot"

    def test_test_connection(self, salesforce_integration):
        adapter = CrmAdapter(salesforce_integration)
        result = adapter.test_connection()
        assert result.success is True
        assert result.details["action"] == "test_connection"
        assert result.details["provider"] == "salesforce"


# ─────────────────────────────────────────────────────────────────────────────
# __init__.py Import Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIntegrationsPackageExports:
    """Verify public symbols exported from the integrations package."""

    def test_imports(self):
        import app.services.integrations as pkg

        assert pkg.IntegrationAdapter is not None
        assert pkg.IntegrationSyncResult is not None
        assert pkg.get_integration_adapter is not None
        assert pkg.AccountingAdapter is not None
        assert pkg.CrmAdapter is not None
