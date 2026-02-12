"""Multi-tenancy data isolation tests.

Verifies that data belonging to one organization is never visible to another.
Creates two organizations, populates each with data, and asserts strict isolation
across customers, plans, invoices, dunning campaigns, and payment requests.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.organization import Organization
from app.repositories.api_key_repository import ApiKeyRepository
from app.schemas.api_key import ApiKeyCreate
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def db_session():
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def org_a_id() -> uuid.UUID:
    """Use the default org as Org A."""
    return DEFAULT_ORG_ID


@pytest.fixture
def org_b(db_session: Session) -> Organization:
    """Create a second organization (Org B)."""
    org = Organization(id=uuid.uuid4(), name="Organization B")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def client_a(db_session: Session, org_a_id: uuid.UUID) -> TestClient:
    """Test client authenticated as Org A."""
    repo = ApiKeyRepository(db_session)
    _, raw_key = repo.create(org_a_id, ApiKeyCreate(name="Org A Key"))
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {raw_key}"
    return client


@pytest.fixture
def client_b(db_session: Session, org_b: Organization) -> TestClient:
    """Test client authenticated as Org B."""
    repo = ApiKeyRepository(db_session)
    _, raw_key = repo.create(org_b.id, ApiKeyCreate(name="Org B Key"))
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {raw_key}"
    return client


# --------------------------------------------------------------------------- #
#  Test data helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def customer_a(db_session: Session, org_a_id: uuid.UUID) -> Customer:
    c = Customer(
        organization_id=org_a_id,
        external_id="org-a-cust-001",
        name="Customer A",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def customer_b(db_session: Session, org_b: Organization) -> Customer:
    c = Customer(
        organization_id=org_b.id,
        external_id="org-b-cust-001",
        name="Customer B",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def invoice_a(
    db_session: Session, org_a_id: uuid.UUID, customer_a: Customer,
) -> Invoice:
    inv = Invoice(
        organization_id=org_a_id,
        invoice_number="INV-A-0001",
        customer_id=customer_a.id,
        status="finalized",
        billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
        billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
        subtotal=Decimal("100"),
        tax_amount=Decimal("0"),
        total=Decimal("100"),
        currency="USD",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


@pytest.fixture
def invoice_b(
    db_session: Session, org_b: Organization, customer_b: Customer,
) -> Invoice:
    inv = Invoice(
        organization_id=org_b.id,
        invoice_number="INV-B-0001",
        customer_id=customer_b.id,
        status="finalized",
        billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
        billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
        subtotal=Decimal("200"),
        tax_amount=Decimal("0"),
        total=Decimal("200"),
        currency="USD",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


# --------------------------------------------------------------------------- #
#  Customer isolation
# --------------------------------------------------------------------------- #


class TestCustomerIsolation:
    """Verify customers from Org A are not visible to Org B and vice-versa."""

    def test_list_customers_isolated(
        self,
        client_a: TestClient,
        client_b: TestClient,
        customer_a: Customer,
        customer_b: Customer,
    ) -> None:
        resp_a = client_a.get("/v1/customers/")
        resp_b = client_b.get("/v1/customers/")
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

        ids_a = {c["id"] for c in resp_a.json()}
        ids_b = {c["id"] for c in resp_b.json()}

        assert str(customer_a.id) in ids_a
        assert str(customer_b.id) not in ids_a
        assert str(customer_b.id) in ids_b
        assert str(customer_a.id) not in ids_b

    def test_get_customer_cross_org_returns_404(
        self,
        client_a: TestClient,
        client_b: TestClient,
        customer_a: Customer,
        customer_b: Customer,
    ) -> None:
        resp = client_a.get(f"/v1/customers/{customer_b.id}")
        assert resp.status_code == 404

        resp = client_b.get(f"/v1/customers/{customer_a.id}")
        assert resp.status_code == 404

    def test_create_customer_scoped_to_org(
        self, client_a: TestClient, client_b: TestClient,
    ) -> None:
        resp = client_a.post(
            "/v1/customers/",
            json={"external_id": "new-a-cust", "name": "New A"},
        )
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        # Should be visible to Org A
        assert client_a.get(f"/v1/customers/{new_id}").status_code == 200
        # Not visible to Org B
        assert client_b.get(f"/v1/customers/{new_id}").status_code == 404


# --------------------------------------------------------------------------- #
#  Invoice isolation
# --------------------------------------------------------------------------- #


class TestInvoiceIsolation:
    """Verify invoices from Org A are not visible to Org B."""

    def test_list_invoices_isolated(
        self,
        client_a: TestClient,
        client_b: TestClient,
        invoice_a: Invoice,
        invoice_b: Invoice,
    ) -> None:
        resp_a = client_a.get("/v1/invoices/")
        resp_b = client_b.get("/v1/invoices/")
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

        ids_a = {inv["id"] for inv in resp_a.json()}
        ids_b = {inv["id"] for inv in resp_b.json()}

        assert str(invoice_a.id) in ids_a
        assert str(invoice_b.id) not in ids_a
        assert str(invoice_b.id) in ids_b
        assert str(invoice_a.id) not in ids_b

    def test_get_invoice_cross_org_returns_404(
        self,
        client_a: TestClient,
        client_b: TestClient,
        invoice_a: Invoice,
        invoice_b: Invoice,
    ) -> None:
        assert client_a.get(f"/v1/invoices/{invoice_b.id}").status_code == 404
        assert client_b.get(f"/v1/invoices/{invoice_a.id}").status_code == 404


# --------------------------------------------------------------------------- #
#  Dunning campaign isolation
# --------------------------------------------------------------------------- #


class TestDunningCampaignIsolation:
    """Verify dunning campaigns are scoped per-organization."""

    def test_list_dunning_campaigns_isolated(
        self,
        client_a: TestClient,
        client_b: TestClient,
    ) -> None:
        # Create campaign in Org A
        resp_a = client_a.post(
            "/v1/dunning_campaigns/",
            json={"code": "dc-a", "name": "Org A Campaign"},
        )
        assert resp_a.status_code == 201
        campaign_a_id = resp_a.json()["id"]

        # Create campaign in Org B
        resp_b = client_b.post(
            "/v1/dunning_campaigns/",
            json={"code": "dc-b", "name": "Org B Campaign"},
        )
        assert resp_b.status_code == 201
        campaign_b_id = resp_b.json()["id"]

        # List from each org
        list_a = client_a.get("/v1/dunning_campaigns/")
        list_b = client_b.get("/v1/dunning_campaigns/")
        assert list_a.status_code == 200
        assert list_b.status_code == 200

        ids_a = {c["id"] for c in list_a.json()}
        ids_b = {c["id"] for c in list_b.json()}

        assert campaign_a_id in ids_a
        assert campaign_b_id not in ids_a
        assert campaign_b_id in ids_b
        assert campaign_a_id not in ids_b

    def test_get_dunning_campaign_cross_org_returns_404(
        self,
        client_a: TestClient,
        client_b: TestClient,
    ) -> None:
        resp = client_a.post(
            "/v1/dunning_campaigns/",
            json={"code": "dc-cross-a", "name": "Cross Org A"},
        )
        assert resp.status_code == 201
        campaign_a_id = resp.json()["id"]

        # Org B cannot see Org A's campaign
        assert client_b.get(f"/v1/dunning_campaigns/{campaign_a_id}").status_code == 404

    def test_update_dunning_campaign_cross_org_returns_404(
        self,
        client_a: TestClient,
        client_b: TestClient,
    ) -> None:
        resp = client_a.post(
            "/v1/dunning_campaigns/",
            json={"code": "dc-upd-cross", "name": "Update Cross"},
        )
        assert resp.status_code == 201
        campaign_a_id = resp.json()["id"]

        # Org B cannot update Org A's campaign
        upd = client_b.put(
            f"/v1/dunning_campaigns/{campaign_a_id}",
            json={"name": "Hacked"},
        )
        assert upd.status_code == 404

    def test_delete_dunning_campaign_cross_org_returns_404(
        self,
        client_a: TestClient,
        client_b: TestClient,
    ) -> None:
        resp = client_a.post(
            "/v1/dunning_campaigns/",
            json={"code": "dc-del-cross", "name": "Delete Cross"},
        )
        assert resp.status_code == 201
        campaign_a_id = resp.json()["id"]

        # Org B cannot delete Org A's campaign
        assert client_b.delete(f"/v1/dunning_campaigns/{campaign_a_id}").status_code == 404

    def test_duplicate_code_allowed_across_orgs(
        self,
        client_a: TestClient,
        client_b: TestClient,
    ) -> None:
        """Same campaign code can exist in different organizations."""
        resp_a = client_a.post(
            "/v1/dunning_campaigns/",
            json={"code": "shared-code", "name": "Org A"},
        )
        assert resp_a.status_code == 201

        resp_b = client_b.post(
            "/v1/dunning_campaigns/",
            json={"code": "shared-code", "name": "Org B"},
        )
        assert resp_b.status_code == 201


# --------------------------------------------------------------------------- #
#  Payment request isolation
# --------------------------------------------------------------------------- #


class TestPaymentRequestIsolation:
    """Verify payment requests are scoped per-organization."""

    def test_list_payment_requests_isolated(
        self,
        client_a: TestClient,
        client_b: TestClient,
        db_session: Session,
        customer_a: Customer,
        customer_b: Customer,
        invoice_a: Invoice,
        invoice_b: Invoice,
    ) -> None:
        # Create payment request in Org A
        resp_a = client_a.post(
            "/v1/payment_requests/",
            json={
                "customer_id": str(customer_a.id),
                "invoice_ids": [str(invoice_a.id)],
            },
        )
        assert resp_a.status_code == 201
        pr_a_id = resp_a.json()["id"]

        # Create payment request in Org B
        resp_b = client_b.post(
            "/v1/payment_requests/",
            json={
                "customer_id": str(customer_b.id),
                "invoice_ids": [str(invoice_b.id)],
            },
        )
        assert resp_b.status_code == 201
        pr_b_id = resp_b.json()["id"]

        # List from each org
        list_a = client_a.get("/v1/payment_requests/")
        list_b = client_b.get("/v1/payment_requests/")
        assert list_a.status_code == 200
        assert list_b.status_code == 200

        ids_a = {pr["id"] for pr in list_a.json()}
        ids_b = {pr["id"] for pr in list_b.json()}

        assert pr_a_id in ids_a
        assert pr_b_id not in ids_a
        assert pr_b_id in ids_b
        assert pr_a_id not in ids_b

    def test_get_payment_request_cross_org_returns_404(
        self,
        client_a: TestClient,
        client_b: TestClient,
        customer_a: Customer,
        invoice_a: Invoice,
    ) -> None:
        resp = client_a.post(
            "/v1/payment_requests/",
            json={
                "customer_id": str(customer_a.id),
                "invoice_ids": [str(invoice_a.id)],
            },
        )
        assert resp.status_code == 201
        pr_a_id = resp.json()["id"]

        # Org B cannot see Org A's payment request
        assert client_b.get(f"/v1/payment_requests/{pr_a_id}").status_code == 404


# --------------------------------------------------------------------------- #
#  Organization API isolation
# --------------------------------------------------------------------------- #


class TestOrganizationApiIsolation:
    """Verify that /current endpoints return the correct org per API key."""

    def test_current_org_returns_correct_org(
        self,
        client_a: TestClient,
        client_b: TestClient,
        org_a_id: uuid.UUID,
        org_b: Organization,
    ) -> None:
        resp_a = client_a.get("/v1/organizations/current")
        resp_b = client_b.get("/v1/organizations/current")

        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

        assert resp_a.json()["id"] == str(org_a_id)
        assert resp_b.json()["id"] == str(org_b.id)

    def test_update_current_org_does_not_affect_other(
        self,
        client_a: TestClient,
        client_b: TestClient,
        org_b: Organization,
    ) -> None:
        # Update Org A's name
        client_a.put(
            "/v1/organizations/current",
            json={"name": "Updated Org A"},
        )

        # Org B should be unaffected
        resp_b = client_b.get("/v1/organizations/current")
        assert resp_b.status_code == 200
        assert resp_b.json()["name"] == "Organization B"


# --------------------------------------------------------------------------- #
#  API key isolation
# --------------------------------------------------------------------------- #


class TestApiKeyIsolation:
    """Verify API keys are scoped to their organization."""

    def test_api_keys_isolated_between_orgs(
        self,
        client_a: TestClient,
        client_b: TestClient,
    ) -> None:
        # Create API key in Org A
        resp_a = client_a.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Extra Key A"},
        )
        assert resp_a.status_code == 201

        # Create API key in Org B
        resp_b = client_b.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Extra Key B"},
        )
        assert resp_b.status_code == 201

        # List keys from each org
        keys_a = client_a.get("/v1/organizations/current/api_keys").json()
        keys_b = client_b.get("/v1/organizations/current/api_keys").json()

        names_a = {k["name"] for k in keys_a}
        names_b = {k["name"] for k in keys_b}

        assert "Extra Key A" in names_a
        assert "Extra Key B" not in names_a
        assert "Extra Key B" in names_b
        assert "Extra Key A" not in names_b

    def test_revoke_api_key_cross_org_returns_404(
        self,
        client_a: TestClient,
        client_b: TestClient,
    ) -> None:
        resp = client_a.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Protected Key"},
        )
        assert resp.status_code == 201
        key_id = resp.json()["id"]

        # Org B cannot revoke Org A's key
        assert client_b.delete(
            f"/v1/organizations/current/api_keys/{key_id}",
        ).status_code == 404
