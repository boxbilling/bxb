"""Billing entity API endpoint tests."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.billing_entity import BillingEntity
from app.models.customer import Customer, generate_uuid
from app.models.invoice import Invoice
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


def _create_billing_entity(
    db_session,
    code: str = "be-test",
    name: str = "Test Entity",
    **kwargs,
) -> BillingEntity:
    """Helper to create a billing entity directly in the DB."""
    entity = BillingEntity(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        code=code,
        name=name,
        **kwargs,
    )
    db_session.add(entity)
    db_session.commit()
    db_session.refresh(entity)
    return entity


def _create_invoice_for_entity(db_session, billing_entity_id) -> Invoice:
    """Helper to create an invoice linked to a billing entity."""
    customer = Customer(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        external_id=f"cust-{uuid.uuid4().hex[:8]}",
        name="Test Customer",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    invoice = Invoice(
        organization_id=DEFAULT_ORG_ID,
        invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
        customer_id=customer.id,
        billing_entity_id=billing_entity_id,
        billing_period_start=datetime(2024, 1, 1, tzinfo=UTC),
        billing_period_end=datetime(2024, 2, 1, tzinfo=UTC),
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


class TestBillingEntitiesAPI:
    """Tests for billing entity CRUD endpoints."""

    def test_create_billing_entity(self, client):
        """Test creating a billing entity via POST."""
        resp = client.post(
            "/v1/billing_entities/",
            json={"code": "api-create", "name": "API Created"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["code"] == "api-create"
        assert data["name"] == "API Created"
        assert data["currency"] == "USD"
        assert data["timezone"] == "UTC"
        assert data["invoice_grace_period"] == 0
        assert data["net_payment_term"] == 30
        assert data["invoice_footer"] is None
        assert data["is_default"] is False
        assert data["id"] is not None

    def test_create_billing_entity_all_fields(self, client):
        """Test creating a billing entity with all fields."""
        resp = client.post(
            "/v1/billing_entities/",
            json={
                "code": "api-full",
                "name": "Full Entity",
                "legal_name": "Full Entity LLC",
                "address_line1": "123 Main St",
                "address_line2": "Suite 100",
                "city": "San Francisco",
                "state": "CA",
                "country": "US",
                "zip_code": "94105",
                "tax_id": "TAX123",
                "email": "billing@example.com",
                "currency": "EUR",
                "timezone": "Europe/Berlin",
                "document_locale": "de",
                "invoice_prefix": "FE",
                "next_invoice_number": 100,
                "invoice_grace_period": 5,
                "net_payment_term": 60,
                "invoice_footer": "Thank you for your business",
                "is_default": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["legal_name"] == "Full Entity LLC"
        assert data["currency"] == "EUR"
        assert data["invoice_prefix"] == "FE"
        assert data["next_invoice_number"] == 100
        assert data["invoice_grace_period"] == 5
        assert data["net_payment_term"] == 60
        assert data["invoice_footer"] == "Thank you for your business"
        assert data["is_default"] is True

    def test_create_billing_entity_duplicate_code(self, client):
        """Test creating a billing entity with duplicate code returns 409."""
        client.post(
            "/v1/billing_entities/",
            json={"code": "dup-code", "name": "First"},
        )
        resp = client.post(
            "/v1/billing_entities/",
            json={"code": "dup-code", "name": "Second"},
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    def test_create_billing_entity_validation_error(self, client):
        """Test creating a billing entity with invalid data returns 422."""
        resp = client.post(
            "/v1/billing_entities/",
            json={"code": "", "name": ""},
        )
        assert resp.status_code == 422

    def test_list_billing_entities(self, client, db_session):
        """Test listing billing entities."""
        for i in range(3):
            _create_billing_entity(db_session, code=f"list-{i}", name=f"Entity {i}")

        resp = client.get("/v1/billing_entities/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert resp.headers["X-Total-Count"] == "3"

    def test_list_billing_entities_pagination(self, client, db_session):
        """Test listing billing entities with pagination."""
        for i in range(5):
            _create_billing_entity(db_session, code=f"page-{i}", name=f"Entity {i}")

        resp = client.get("/v1/billing_entities/?skip=1&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_billing_entities_empty(self, client):
        """Test listing billing entities when none exist."""
        resp = client.get("/v1/billing_entities/")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    def test_get_billing_entity_by_code(self, client, db_session):
        """Test getting a billing entity by code."""
        _create_billing_entity(db_session, code="get-code", name="Get By Code")

        resp = client.get("/v1/billing_entities/get-code")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "get-code"
        assert data["name"] == "Get By Code"

    def test_get_billing_entity_not_found(self, client):
        """Test getting a non-existent billing entity returns 404."""
        resp = client.get("/v1/billing_entities/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    def test_update_billing_entity(self, client, db_session):
        """Test updating a billing entity via PATCH."""
        _create_billing_entity(db_session, code="upd-code", name="Original Name")

        resp = client.patch(
            "/v1/billing_entities/upd-code",
            json={"name": "Updated Name", "currency": "GBP"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["currency"] == "GBP"
        assert data["code"] == "upd-code"

    def test_update_billing_entity_partial(self, client, db_session):
        """Test partial update only changes specified fields."""
        _create_billing_entity(
            db_session, code="partial-upd", name="Partial", currency="USD"
        )

        resp = client.patch(
            "/v1/billing_entities/partial-upd",
            json={"name": "New Name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Name"
        assert data["currency"] == "USD"

    def test_update_billing_entity_not_found(self, client):
        """Test updating a non-existent billing entity returns 404."""
        resp = client.patch(
            "/v1/billing_entities/nonexistent",
            json={"name": "Nope"},
        )
        assert resp.status_code == 404

    def test_delete_billing_entity(self, client, db_session):
        """Test deleting a billing entity."""
        _create_billing_entity(db_session, code="del-code", name="Delete Me")

        resp = client.delete("/v1/billing_entities/del-code")
        assert resp.status_code == 204

        # Verify it was deleted
        resp = client.get("/v1/billing_entities/del-code")
        assert resp.status_code == 404

    def test_delete_billing_entity_not_found(self, client):
        """Test deleting a non-existent billing entity returns 404."""
        resp = client.delete("/v1/billing_entities/nonexistent")
        assert resp.status_code == 404

    def test_delete_billing_entity_with_invoices(self, client, db_session):
        """Test deleting a billing entity with invoices returns 400."""
        entity = _create_billing_entity(
            db_session, code="del-invoices", name="Has Invoices"
        )
        _create_invoice_for_entity(db_session, entity.id)

        resp = client.delete("/v1/billing_entities/del-invoices")
        assert resp.status_code == 400
        assert "existing invoices" in resp.json()["detail"]

    def test_customer_counts_empty(self, client):
        """Test customer counts endpoint with no entities."""
        resp = client.get("/v1/billing_entities/customer_counts")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_customer_counts_with_data(self, client, db_session):
        """Test customer counts endpoint returns correct counts."""
        entity = _create_billing_entity(
            db_session, code="cc-api-test", name="Count Test"
        )
        for i in range(2):
            customer = Customer(
                id=generate_uuid(),
                organization_id=DEFAULT_ORG_ID,
                external_id=f"cc-api-{uuid.uuid4().hex[:8]}",
                name=f"Customer {i}",
                billing_entity_id=entity.id,
            )
            db_session.add(customer)
        db_session.commit()

        resp = client.get("/v1/billing_entities/customer_counts")
        assert resp.status_code == 200
        data = resp.json()
        assert data[str(entity.id)] == 2

    def test_customer_counts_excludes_unlinked(self, client, db_session):
        """Test customer counts excludes customers without billing entity."""
        _create_billing_entity(
            db_session, code="cc-excl-test", name="Exclusion Test"
        )
        customer = Customer(
            id=generate_uuid(),
            organization_id=DEFAULT_ORG_ID,
            external_id=f"cc-no-be-{uuid.uuid4().hex[:8]}",
            name="Unlinked Customer",
        )
        db_session.add(customer)
        db_session.commit()

        resp = client.get("/v1/billing_entities/customer_counts")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_create_idempotency(self, client):
        """Test idempotent creation with Idempotency-Key header."""
        key = str(uuid.uuid4())
        headers = {"Idempotency-Key": key}
        resp1 = client.post(
            "/v1/billing_entities/",
            json={"code": "idempotent", "name": "Idempotent"},
            headers=headers,
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/v1/billing_entities/",
            json={"code": "idempotent", "name": "Idempotent"},
            headers=headers,
        )
        assert resp2.status_code == 201
        assert resp1.json()["id"] == resp2.json()["id"]
