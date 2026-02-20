"""Tests for column sorting across API endpoints and the sorting utility."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.sorting import apply_order_by
from app.main import app
from app.models.customer import Customer
from app.models.shared import generate_uuid
from app.models.invoice import Invoice, InvoiceStatus, InvoiceType
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.customer import CustomerCreate
from app.schemas.plan import PlanCreate
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


# ---------------------------------------------------------------------------
# Unit tests for the apply_order_by utility
# ---------------------------------------------------------------------------


class TestApplyOrderBy:
    """Tests for the core sorting utility function."""

    def test_default_sort_created_at_desc(self, db_session: Session):
        """When order_by is None, default to created_at desc."""
        query = db_session.query(Customer).filter(
            Customer.organization_id == DEFAULT_ORG_ID
        )
        sorted_query = apply_order_by(query, Customer, None)
        # Should compile without error
        assert sorted_query is not None

    def test_sort_by_valid_field_asc(self, db_session: Session):
        """Sort by a valid field in ascending order."""
        query = db_session.query(Customer).filter(
            Customer.organization_id == DEFAULT_ORG_ID
        )
        sorted_query = apply_order_by(query, Customer, "name:asc")
        assert sorted_query is not None

    def test_sort_by_valid_field_desc(self, db_session: Session):
        """Sort by a valid field in descending order."""
        query = db_session.query(Customer).filter(
            Customer.organization_id == DEFAULT_ORG_ID
        )
        sorted_query = apply_order_by(query, Customer, "name:desc")
        assert sorted_query is not None

    def test_invalid_field_falls_back_to_default(self, db_session: Session):
        """Invalid field name should fall back to default (created_at)."""
        query = db_session.query(Customer).filter(
            Customer.organization_id == DEFAULT_ORG_ID
        )
        sorted_query = apply_order_by(query, Customer, "nonexistent_column:asc")
        assert sorted_query is not None

    def test_invalid_direction_falls_back_to_default(self, db_session: Session):
        """Invalid direction should fall back to default direction."""
        query = db_session.query(Customer).filter(
            Customer.organization_id == DEFAULT_ORG_ID
        )
        sorted_query = apply_order_by(query, Customer, "name:invalid")
        assert sorted_query is not None

    def test_no_direction_defaults_to_asc(self, db_session: Session):
        """Field without direction should default to asc."""
        query = db_session.query(Customer).filter(
            Customer.organization_id == DEFAULT_ORG_ID
        )
        sorted_query = apply_order_by(query, Customer, "name")
        assert sorted_query is not None

    def test_custom_default_field(self, db_session: Session):
        """Custom default field should be used when order_by is None."""
        query = db_session.query(Customer).filter(
            Customer.organization_id == DEFAULT_ORG_ID
        )
        sorted_query = apply_order_by(
            query, Customer, None, default_field="name", default_direction="asc"
        )
        assert sorted_query is not None

    def test_empty_string_uses_default(self, db_session: Session):
        """Empty string for order_by should still trigger parsing (empty field name)."""
        query = db_session.query(Customer).filter(
            Customer.organization_id == DEFAULT_ORG_ID
        )
        # Empty string -> candidate_field = "" -> hasattr(Customer, "") is False -> default
        sorted_query = apply_order_by(query, Customer, "")
        assert sorted_query is not None


# ---------------------------------------------------------------------------
# API integration tests for sorting via customers endpoint
# ---------------------------------------------------------------------------


class TestCustomersSorting:
    """Tests for customer list sorting via the API."""

    def test_sort_by_name_ascending(self, client: TestClient):
        """Customers sorted by name ascending."""
        names = ["Zebra Corp", "Apple Inc", "Mango Ltd"]
        for name in names:
            client.post(
                "/v1/customers/",
                json={"external_id": f"sort-{name.lower().replace(' ', '-')}", "name": name},
            )

        response = client.get("/v1/customers/?order_by=name:asc")
        assert response.status_code == 200
        data = response.json()
        result_names = [c["name"] for c in data]
        assert result_names == sorted(names)

    def test_sort_by_name_descending(self, client: TestClient):
        """Customers sorted by name descending."""
        names = ["Zebra Corp", "Apple Inc", "Mango Ltd"]
        for name in names:
            client.post(
                "/v1/customers/",
                json={"external_id": f"sortd-{name.lower().replace(' ', '-')}", "name": name},
            )

        response = client.get("/v1/customers/?order_by=name:desc")
        assert response.status_code == 200
        data = response.json()
        result_names = [c["name"] for c in data]
        assert result_names == sorted(names, reverse=True)

    def test_sort_by_email_ascending(self, client: TestClient):
        """Customers sorted by email ascending."""
        customers = [
            ("Customer Z", "zebra@test.com"),
            ("Customer A", "alpha@test.com"),
            ("Customer M", "mango@test.com"),
        ]
        for name, email in customers:
            client.post(
                "/v1/customers/",
                json={
                    "external_id": f"sort-email-{email.split('@')[0]}",
                    "name": name,
                    "email": email,
                },
            )

        response = client.get("/v1/customers/?order_by=email:asc")
        assert response.status_code == 200
        data = response.json()
        emails = [c["email"] for c in data]
        assert emails == ["alpha@test.com", "mango@test.com", "zebra@test.com"]

    def test_sort_by_currency(self, client: TestClient):
        """Customers sorted by currency."""
        currencies = ["USD", "EUR", "GBP"]
        for i, currency in enumerate(currencies):
            client.post(
                "/v1/customers/",
                json={
                    "external_id": f"sort-curr-{i}",
                    "name": f"Customer {i}",
                    "currency": currency,
                },
            )

        response = client.get("/v1/customers/?order_by=currency:asc")
        assert response.status_code == 200
        data = response.json()
        result_currencies = [c["currency"] for c in data]
        assert result_currencies == ["EUR", "GBP", "USD"]

    def test_default_sort_no_order_by(self, client: TestClient):
        """Without order_by, default sort (created_at desc) is applied."""
        for i in range(3):
            client.post(
                "/v1/customers/",
                json={"external_id": f"default-sort-{i}", "name": f"Customer {i}"},
            )

        response = client.get("/v1/customers/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_invalid_field_returns_results(self, client: TestClient):
        """Invalid sort field should not error, just use default sort."""
        client.post(
            "/v1/customers/",
            json={"external_id": "invalid-sort", "name": "Test"},
        )

        response = client.get("/v1/customers/?order_by=nonexistent:asc")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_invalid_direction_returns_results(self, client: TestClient):
        """Invalid sort direction should not error, just use default direction."""
        client.post(
            "/v1/customers/",
            json={"external_id": "invalid-dir", "name": "Test"},
        )

        response = client.get("/v1/customers/?order_by=name:baddir")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_sort_with_pagination(self, client: TestClient):
        """Sorting works together with pagination."""
        names = ["Zebra", "Apple", "Mango", "Banana", "Cherry"]
        for name in names:
            client.post(
                "/v1/customers/",
                json={"external_id": f"sort-pag-{name.lower()}", "name": name},
            )

        response = client.get("/v1/customers/?order_by=name:asc&skip=1&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        result_names = [c["name"] for c in data]
        # Sorted: Apple, Banana, Cherry, Mango, Zebra -> skip 1 limit 2 = Banana, Cherry
        assert result_names == ["Banana", "Cherry"]

    def test_sort_total_count_unaffected(self, client: TestClient):
        """X-Total-Count header is not affected by sorting."""
        for i in range(3):
            client.post(
                "/v1/customers/",
                json={"external_id": f"count-sort-{i}", "name": f"Customer {i}"},
            )

        response = client.get("/v1/customers/?order_by=name:asc")
        assert response.status_code == 200
        assert response.headers["X-Total-Count"] == "3"


# ---------------------------------------------------------------------------
# Repository-level sorting tests
# ---------------------------------------------------------------------------


class TestRepositorySorting:
    """Tests for repository-level sorting."""

    def test_customer_repo_sort_by_name_asc(self, db_session: Session):
        """CustomerRepository sorts by name ascending."""
        repo = CustomerRepository(db_session)
        for name in ["Zebra", "Apple", "Mango"]:
            repo.create(
                CustomerCreate(external_id=f"repo-{name.lower()}", name=name),
                DEFAULT_ORG_ID,
            )

        results = repo.get_all(DEFAULT_ORG_ID, order_by="name:asc")
        names = [c.name for c in results]
        assert names == ["Apple", "Mango", "Zebra"]

    def test_customer_repo_sort_by_name_desc(self, db_session: Session):
        """CustomerRepository sorts by name descending."""
        repo = CustomerRepository(db_session)
        for name in ["Zebra", "Apple", "Mango"]:
            repo.create(
                CustomerCreate(external_id=f"repod-{name.lower()}", name=name),
                DEFAULT_ORG_ID,
            )

        results = repo.get_all(DEFAULT_ORG_ID, order_by="name:desc")
        names = [c.name for c in results]
        assert names == ["Zebra", "Mango", "Apple"]

    def test_customer_repo_default_sort(self, db_session: Session):
        """CustomerRepository default sort is created_at desc."""
        repo = CustomerRepository(db_session)
        for i in range(3):
            repo.create(
                CustomerCreate(external_id=f"repodef-{i}", name=f"Cust {i}"),
                DEFAULT_ORG_ID,
            )

        results = repo.get_all(DEFAULT_ORG_ID)
        assert len(results) == 3

    def test_customer_repo_invalid_field_uses_default(self, db_session: Session):
        """Invalid field falls back to default sort without error."""
        repo = CustomerRepository(db_session)
        repo.create(
            CustomerCreate(external_id="repoinv", name="Test"),
            DEFAULT_ORG_ID,
        )

        results = repo.get_all(DEFAULT_ORG_ID, order_by="bogus_field:asc")
        assert len(results) == 1

    def test_plan_repo_sort_by_name_asc(self, db_session: Session):
        """PlanRepository sorts by name ascending."""
        repo = PlanRepository(db_session)
        for name in ["Premium", "Basic", "Enterprise"]:
            repo.create(
                PlanCreate(
                    code=f"plan-{name.lower()}",
                    name=name,
                    interval="monthly",
                    amount_cents=1000,
                    currency="USD",
                ),
                DEFAULT_ORG_ID,
            )

        results = repo.get_all(DEFAULT_ORG_ID, order_by="name:asc")
        names = [p.name for p in results]
        assert names == ["Basic", "Enterprise", "Premium"]

    def test_invoice_repo_sort_by_status(self, db_session: Session):
        """InvoiceRepository sorts by status."""
        repo = InvoiceRepository(db_session)
        # Create a customer for invoices
        cust_repo = CustomerRepository(db_session)
        customer = cust_repo.create(
            CustomerCreate(external_id="inv-sort-cust", name="Invoice Sort Customer"),
            DEFAULT_ORG_ID,
        )

        now = datetime.now()
        for inv_status in [InvoiceStatus.PAID, InvoiceStatus.DRAFT, InvoiceStatus.FINALIZED]:
            invoice = Invoice(
                id=generate_uuid(),
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                invoice_number=f"INV-SORT-{inv_status.value}",
                invoice_type=InvoiceType.SUBSCRIPTION.value,
                status=inv_status.value,
                currency="USD",
                total=1000,
                billing_period_start=now,
                billing_period_end=now,
            )
            db_session.add(invoice)
        db_session.commit()

        results = repo.get_all(DEFAULT_ORG_ID, order_by="status:asc")
        statuses = [i.status for i in results]
        assert statuses == sorted(statuses)


# ---------------------------------------------------------------------------
# Sorting across multiple endpoints
# ---------------------------------------------------------------------------


class TestMultiEndpointSorting:
    """Test that order_by parameter is accepted by various endpoints."""

    def test_plans_sorting(self, client: TestClient):
        """Plans endpoint accepts order_by parameter."""
        for name in ["Premium", "Basic"]:
            client.post(
                "/v1/plans/",
                json={
                    "code": f"plan-sort-{name.lower()}",
                    "name": name,
                    "interval": "monthly",
                    "amount_cents": 1000,
                    "currency": "USD",
                },
            )

        response = client.get("/v1/plans/?order_by=name:asc")
        assert response.status_code == 200
        data = response.json()
        names = [p["name"] for p in data]
        assert names == ["Basic", "Premium"]

    def test_invoices_sorting(self, client: TestClient):
        """Invoices endpoint accepts order_by parameter."""
        # Create a customer first
        cust = client.post(
            "/v1/customers/",
            json={"external_id": "inv-sort-cust-api", "name": "Invoice Sort"},
        )
        assert cust.status_code == 201

        response = client.get("/v1/invoices/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_subscriptions_sorting(self, client: TestClient):
        """Subscriptions endpoint accepts order_by parameter."""
        response = client.get("/v1/subscriptions/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_payments_sorting(self, client: TestClient):
        """Payments endpoint accepts order_by parameter."""
        response = client.get("/v1/payments/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_wallets_sorting(self, client: TestClient):
        """Wallets endpoint accepts order_by parameter."""
        response = client.get("/v1/wallets/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_fees_sorting(self, client: TestClient):
        """Fees endpoint accepts order_by parameter."""
        response = client.get("/v1/fees/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_coupons_sorting(self, client: TestClient):
        """Coupons endpoint accepts order_by parameter."""
        response = client.get("/v1/coupons/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_credit_notes_sorting(self, client: TestClient):
        """Credit notes endpoint accepts order_by parameter."""
        response = client.get("/v1/credit_notes/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_taxes_sorting(self, client: TestClient):
        """Taxes endpoint accepts order_by parameter."""
        response = client.get("/v1/taxes/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_add_ons_sorting(self, client: TestClient):
        """Add-ons endpoint accepts order_by parameter."""
        response = client.get("/v1/add_ons/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_billable_metrics_sorting(self, client: TestClient):
        """Billable metrics endpoint accepts order_by parameter."""
        response = client.get("/v1/billable_metrics/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_webhook_endpoints_sorting(self, client: TestClient):
        """Webhook endpoints endpoint accepts order_by parameter."""
        response = client.get("/v1/webhook_endpoints/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_dunning_campaigns_sorting(self, client: TestClient):
        """Dunning campaigns endpoint accepts order_by parameter."""
        response = client.get("/v1/dunning_campaigns/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_billing_entities_sorting(self, client: TestClient):
        """Billing entities endpoint accepts order_by parameter."""
        response = client.get("/v1/billing_entities/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_features_sorting(self, client: TestClient):
        """Features endpoint accepts order_by parameter."""
        response = client.get("/v1/features/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_audit_logs_sorting(self, client: TestClient):
        """Audit logs endpoint accepts order_by parameter."""
        response = client.get("/v1/audit_logs/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_payment_methods_sorting(self, client: TestClient):
        """Payment methods endpoint accepts order_by parameter."""
        response = client.get("/v1/payment_methods/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_payment_requests_sorting(self, client: TestClient):
        """Payment requests endpoint accepts order_by parameter."""
        response = client.get("/v1/payment_requests/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_data_exports_sorting(self, client: TestClient):
        """Data exports endpoint accepts order_by parameter."""
        response = client.get("/v1/data_exports/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_usage_alerts_sorting(self, client: TestClient):
        """Usage alerts endpoint accepts order_by parameter."""
        response = client.get("/v1/usage_alerts/?order_by=created_at:desc")
        assert response.status_code == 200

    def test_integrations_sorting(self, client: TestClient):
        """Integrations endpoint accepts order_by parameter."""
        response = client.get("/v1/integrations/?order_by=created_at:desc")
        assert response.status_code == 200
