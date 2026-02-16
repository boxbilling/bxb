"""Global search API tests for bxb."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.customer import CustomerCreate
from app.schemas.invoice import InvoiceCreate
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Create a database session for direct repository testing."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def customer(db_session):
    """Create a test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id="search-cust-001",
            name="Acme Corporation",
            email="billing@acme.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code="search-plan-pro",
            name="Professional Plan",
            interval="monthly",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def subscription(db_session, customer, plan):
    """Create a test subscription."""
    repo = SubscriptionRepository(db_session)
    return repo.create(
        SubscriptionCreate(
            external_id="search-sub-001",
            customer_id=customer.id,
            plan_id=plan.id,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def invoice(db_session, customer, subscription):
    """Create a test invoice."""
    repo = InvoiceRepository(db_session)
    now = datetime.now(UTC)
    return repo.create(
        InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            currency="USD",
            billing_period_start=now,
            billing_period_end=now + timedelta(days=30),
        ),
        DEFAULT_ORG_ID,
    )


class TestSearchAPI:
    def test_search_empty_db(self, client: TestClient):
        """Test search returns empty results when no data exists."""
        response = client.get("/v1/search/?q=test")
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test"
        assert data["results"] == []
        assert data["total_count"] == 0

    def test_search_requires_query(self, client: TestClient):
        """Test search requires a non-empty query parameter."""
        response = client.get("/v1/search/")
        assert response.status_code == 422

    def test_search_customers_by_name(self, client: TestClient, customer):
        """Test searching customers by name."""
        response = client.get("/v1/search/?q=Acme")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] >= 1
        customer_results = [r for r in data["results"] if r["type"] == "customer"]
        assert len(customer_results) == 1
        assert customer_results[0]["title"] == "Acme Corporation"
        assert customer_results[0]["subtitle"] == "billing@acme.com"
        assert "/admin/customers/" in customer_results[0]["url"]

    def test_search_customers_by_email(self, client: TestClient, customer):
        """Test searching customers by email."""
        response = client.get("/v1/search/?q=billing@acme")
        assert response.status_code == 200
        data = response.json()
        customer_results = [r for r in data["results"] if r["type"] == "customer"]
        assert len(customer_results) == 1
        assert customer_results[0]["title"] == "Acme Corporation"

    def test_search_customers_by_external_id(self, client: TestClient, customer):
        """Test searching customers by external_id."""
        response = client.get("/v1/search/?q=search-cust-001")
        assert response.status_code == 200
        data = response.json()
        customer_results = [r for r in data["results"] if r["type"] == "customer"]
        assert len(customer_results) == 1

    def test_search_plans_by_name(self, client: TestClient, plan):
        """Test searching plans by name."""
        response = client.get("/v1/search/?q=Professional")
        assert response.status_code == 200
        data = response.json()
        plan_results = [r for r in data["results"] if r["type"] == "plan"]
        assert len(plan_results) == 1
        assert plan_results[0]["title"] == "Professional Plan"
        assert "search-plan-pro" in plan_results[0]["subtitle"]

    def test_search_plans_by_code(self, client: TestClient, plan):
        """Test searching plans by code."""
        response = client.get("/v1/search/?q=search-plan-pro")
        assert response.status_code == 200
        data = response.json()
        plan_results = [r for r in data["results"] if r["type"] == "plan"]
        assert len(plan_results) == 1

    def test_search_subscriptions(self, client: TestClient, subscription):
        """Test searching subscriptions by external_id."""
        response = client.get("/v1/search/?q=search-sub-001")
        assert response.status_code == 200
        data = response.json()
        sub_results = [r for r in data["results"] if r["type"] == "subscription"]
        assert len(sub_results) == 1
        assert "search-sub-001" in sub_results[0]["title"]

    def test_search_invoices(self, client: TestClient, invoice):
        """Test searching invoices by invoice_number."""
        inv_number = invoice.invoice_number
        response = client.get(f"/v1/search/?q={inv_number}")
        assert response.status_code == 200
        data = response.json()
        inv_results = [r for r in data["results"] if r["type"] == "invoice"]
        assert len(inv_results) == 1
        assert inv_number in inv_results[0]["title"]

    def test_search_case_insensitive(self, client: TestClient, customer):
        """Test search is case-insensitive."""
        response = client.get("/v1/search/?q=acme")
        assert response.status_code == 200
        data = response.json()
        customer_results = [r for r in data["results"] if r["type"] == "customer"]
        assert len(customer_results) == 1

    def test_search_no_results(self, client: TestClient, customer):
        """Test search with no matching results."""
        response = client.get("/v1/search/?q=zzz_nonexistent_zzz")
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["results"] == []

    def test_search_limit_parameter(self, client: TestClient, db_session):
        """Test search respects the limit parameter."""
        # Create multiple customers
        repo = CustomerRepository(db_session)
        for i in range(5):
            repo.create(
                CustomerCreate(
                    external_id=f"limit-cust-{i}",
                    name=f"Limit Test Customer {i}",
                ),
                DEFAULT_ORG_ID,
            )

        response = client.get("/v1/search/?q=Limit+Test&limit=2")
        assert response.status_code == 200
        data = response.json()
        customer_results = [r for r in data["results"] if r["type"] == "customer"]
        assert len(customer_results) == 2

    def test_search_across_types(self, client: TestClient, customer, plan, subscription, invoice):
        """Test search returns results across multiple entity types."""
        response = client.get("/v1/search/?q=search")
        assert response.status_code == 200
        data = response.json()
        types = {r["type"] for r in data["results"]}
        assert "customer" in types
        assert "plan" in types
        assert "subscription" in types

    def test_search_customer_without_email(self, client: TestClient, db_session):
        """Test search result for customer without email shows external_id."""
        repo = CustomerRepository(db_session)
        repo.create(
            CustomerCreate(
                external_id="no-email-cust",
                name="No Email Customer",
            ),
            DEFAULT_ORG_ID,
        )

        response = client.get("/v1/search/?q=No+Email")
        assert response.status_code == 200
        data = response.json()
        customer_results = [r for r in data["results"] if r["type"] == "customer"]
        assert len(customer_results) == 1
        assert "no-email-cust" in customer_results[0]["subtitle"]


class TestSearchSchema:
    def test_search_result_fields(self, client: TestClient, customer):
        """Test that search results have all required fields."""
        response = client.get("/v1/search/?q=Acme")
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert "total_count" in data
        result = data["results"][0]
        assert "type" in result
        assert "id" in result
        assert "title" in result
        assert "subtitle" in result
        assert "url" in result

    def test_search_max_limit(self, client: TestClient):
        """Test that limit is capped at 50."""
        response = client.get("/v1/search/?q=test&limit=100")
        assert response.status_code == 422

    def test_search_min_limit(self, client: TestClient):
        """Test that limit must be at least 1."""
        response = client.get("/v1/search/?q=test&limit=0")
        assert response.status_code == 422
