"""Customer API tests for bxb."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.customer import Customer, UUIDType, generate_uuid, utc_now
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate


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


class TestUUIDType:
    def test_process_bind_param_none(self):
        """Test processing None value for bind param."""
        uuid_type = UUIDType()
        result = uuid_type.process_bind_param(None, None)
        assert result is None

    def test_process_bind_param_uuid(self):
        """Test processing UUID value for bind param."""
        uuid_type = UUIDType()
        test_uuid = uuid.uuid4()
        result = uuid_type.process_bind_param(test_uuid, None)
        assert result == str(test_uuid)

    def test_process_bind_param_string(self):
        """Test processing string value for bind param."""
        uuid_type = UUIDType()
        test_uuid = str(uuid.uuid4())
        result = uuid_type.process_bind_param(test_uuid, None)
        assert result == test_uuid

    def test_process_result_value_none(self):
        """Test processing None value from result."""
        uuid_type = UUIDType()
        result = uuid_type.process_result_value(None, None)
        assert result is None

    def test_process_result_value_uuid(self):
        """Test processing UUID value from result."""
        uuid_type = UUIDType()
        test_uuid = uuid.uuid4()
        result = uuid_type.process_result_value(test_uuid, None)
        assert result == test_uuid

    def test_process_result_value_string(self):
        """Test processing string value from result."""
        uuid_type = UUIDType()
        test_uuid = uuid.uuid4()
        result = uuid_type.process_result_value(str(test_uuid), None)
        assert result == test_uuid


class TestCustomerModel:
    def test_generate_uuid(self):
        """Test that generate_uuid returns a valid UUID."""
        result = generate_uuid()
        assert isinstance(result, uuid.UUID)

    def test_utc_now(self):
        """Test that utc_now returns a datetime."""
        result = utc_now()
        assert result is not None
        assert result.tzinfo is not None

    def test_customer_defaults(self, db_session):
        """Test Customer model default values."""
        customer = Customer(
            external_id="test-123",
            name="Test Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        assert customer.id is not None
        assert customer.currency == "USD"
        assert customer.timezone == "UTC"
        assert customer.billing_metadata == {}
        assert customer.email is None
        assert customer.invoice_grace_period == 0
        assert customer.net_payment_term == 30
        assert customer.created_at is not None
        assert customer.updated_at is not None

    def test_customer_grace_period_fields(self, db_session):
        """Test Customer model with custom grace period fields."""
        customer = Customer(
            external_id="test-gp",
            name="Grace Period Customer",
            invoice_grace_period=5,
            net_payment_term=45,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        assert customer.invoice_grace_period == 5
        assert customer.net_payment_term == 45


class TestCustomerRepository:
    def test_get_by_external_id(self, db_session):
        """Test getting customer by external_id."""
        repo = CustomerRepository(db_session)
        data = CustomerCreate(
            external_id="ext-123",
            name="Test Customer",
        )
        repo.create(data)

        customer = repo.get_by_external_id("ext-123")
        assert customer is not None
        assert customer.external_id == "ext-123"

        # Test not found
        not_found = repo.get_by_external_id("nonexistent")
        assert not_found is None

    def test_external_id_exists(self, db_session):
        """Test checking if external_id exists."""
        repo = CustomerRepository(db_session)
        data = CustomerCreate(
            external_id="exists-123",
            name="Test Customer",
        )
        repo.create(data)

        assert repo.external_id_exists("exists-123") is True
        assert repo.external_id_exists("not-exists") is False


class TestCustomersAPI:
    def test_list_customers_empty(self, client: TestClient):
        """Test listing customers when none exist."""
        response = client.get("/v1/customers/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_customer_minimal(self, client: TestClient):
        """Test creating a customer with minimal data."""
        response = client.post(
            "/v1/customers/",
            json={"external_id": "cust-001", "name": "Acme Corp"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["external_id"] == "cust-001"
        assert data["name"] == "Acme Corp"
        assert data["currency"] == "USD"
        assert data["timezone"] == "UTC"
        assert data["email"] is None
        assert data["billing_metadata"] == {}
        assert data["invoice_grace_period"] == 0
        assert data["net_payment_term"] == 30
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_customer_full(self, client: TestClient):
        """Test creating a customer with all fields."""
        response = client.post(
            "/v1/customers/",
            json={
                "external_id": "cust-002",
                "name": "Globex Corp",
                "email": "billing@globex.com",
                "currency": "EUR",
                "timezone": "Europe/London",
                "billing_metadata": {"industry": "tech", "tier": "enterprise"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["external_id"] == "cust-002"
        assert data["name"] == "Globex Corp"
        assert data["email"] == "billing@globex.com"
        assert data["currency"] == "EUR"
        assert data["timezone"] == "Europe/London"
        assert data["billing_metadata"] == {"industry": "tech", "tier": "enterprise"}

    def test_create_customer_duplicate_external_id(self, client: TestClient):
        """Test creating a customer with duplicate external_id."""
        client.post(
            "/v1/customers/",
            json={"external_id": "dup-001", "name": "First"},
        )
        response = client.post(
            "/v1/customers/",
            json={"external_id": "dup-001", "name": "Second"},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Customer with this external_id already exists"

    def test_create_customer_invalid_email(self, client: TestClient):
        """Test creating a customer with invalid email."""
        response = client.post(
            "/v1/customers/",
            json={"external_id": "cust-003", "name": "Test", "email": "not-an-email"},
        )
        assert response.status_code == 422

    def test_create_customer_invalid_currency(self, client: TestClient):
        """Test creating a customer with invalid currency length."""
        response = client.post(
            "/v1/customers/",
            json={"external_id": "cust-004", "name": "Test", "currency": "EURO"},
        )
        assert response.status_code == 422

    def test_create_customer_empty_external_id(self, client: TestClient):
        """Test creating a customer with empty external_id."""
        response = client.post(
            "/v1/customers/",
            json={"external_id": "", "name": "Test"},
        )
        assert response.status_code == 422

    def test_create_customer_empty_name(self, client: TestClient):
        """Test creating a customer with empty name."""
        response = client.post(
            "/v1/customers/",
            json={"external_id": "cust-005", "name": ""},
        )
        assert response.status_code == 422

    def test_get_customer(self, client: TestClient):
        """Test getting a customer by ID."""
        create_response = client.post(
            "/v1/customers/",
            json={"external_id": "get-001", "name": "Get Test"},
        )
        customer_id = create_response.json()["id"]

        response = client.get(f"/v1/customers/{customer_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == customer_id
        assert data["name"] == "Get Test"

    def test_get_customer_not_found(self, client: TestClient):
        """Test getting a non-existent customer."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/customers/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"

    def test_get_customer_invalid_uuid(self, client: TestClient):
        """Test getting a customer with invalid UUID."""
        response = client.get("/v1/customers/not-a-uuid")
        assert response.status_code == 422

    def test_update_customer(self, client: TestClient):
        """Test updating a customer."""
        create_response = client.post(
            "/v1/customers/",
            json={"external_id": "upd-001", "name": "Original Name"},
        )
        customer_id = create_response.json()["id"]

        response = client.put(
            f"/v1/customers/{customer_id}",
            json={"name": "Updated Name", "email": "new@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["email"] == "new@example.com"
        assert data["external_id"] == "upd-001"  # Unchanged

    def test_update_customer_partial(self, client: TestClient):
        """Test partial update of a customer."""
        create_response = client.post(
            "/v1/customers/",
            json={
                "external_id": "upd-002",
                "name": "Full Customer",
                "email": "original@example.com",
                "currency": "USD",
            },
        )
        customer_id = create_response.json()["id"]

        # Only update currency
        response = client.put(
            f"/v1/customers/{customer_id}",
            json={"currency": "GBP"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Full Customer"  # Unchanged
        assert data["email"] == "original@example.com"  # Unchanged
        assert data["currency"] == "GBP"  # Updated

    def test_update_customer_billing_metadata(self, client: TestClient):
        """Test updating customer billing_metadata."""
        create_response = client.post(
            "/v1/customers/",
            json={
                "external_id": "upd-003",
                "name": "Meta Customer",
                "billing_metadata": {"key1": "value1"},
            },
        )
        customer_id = create_response.json()["id"]

        response = client.put(
            f"/v1/customers/{customer_id}",
            json={"billing_metadata": {"key2": "value2", "key3": "value3"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["billing_metadata"] == {"key2": "value2", "key3": "value3"}

    def test_update_customer_not_found(self, client: TestClient):
        """Test updating a non-existent customer."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/v1/customers/{fake_id}",
            json={"name": "Ghost"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"

    def test_delete_customer(self, client: TestClient):
        """Test deleting a customer."""
        create_response = client.post(
            "/v1/customers/",
            json={"external_id": "del-001", "name": "Delete Me"},
        )
        customer_id = create_response.json()["id"]

        response = client.delete(f"/v1/customers/{customer_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/v1/customers/{customer_id}")
        assert get_response.status_code == 404

    def test_delete_customer_not_found(self, client: TestClient):
        """Test deleting a non-existent customer."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/v1/customers/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"

    def test_list_customers_pagination(self, client: TestClient):
        """Test listing customers with pagination."""
        # Create multiple customers
        for i in range(5):
            client.post(
                "/v1/customers/",
                json={"external_id": f"page-{i}", "name": f"Customer {i}"},
            )

        # Test pagination
        response = client.get("/v1/customers/?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_customers_default_pagination(self, client: TestClient):
        """Test listing customers with default pagination."""
        # Create a customer
        client.post(
            "/v1/customers/",
            json={"external_id": "default-001", "name": "Default Test"},
        )

        response = client.get("/v1/customers/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_create_customer_with_grace_period(self, client: TestClient):
        """Test creating a customer with custom grace period settings."""
        response = client.post(
            "/v1/customers/",
            json={
                "external_id": "gp-001",
                "name": "Grace Period Corp",
                "invoice_grace_period": 7,
                "net_payment_term": 45,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["invoice_grace_period"] == 7
        assert data["net_payment_term"] == 45

    def test_create_customer_grace_period_negative(self, client: TestClient):
        """Test creating a customer with negative grace period is rejected."""
        response = client.post(
            "/v1/customers/",
            json={
                "external_id": "gp-neg",
                "name": "Negative GP",
                "invoice_grace_period": -1,
            },
        )
        assert response.status_code == 422

    def test_create_customer_net_payment_term_negative(self, client: TestClient):
        """Test creating a customer with negative net_payment_term is rejected."""
        response = client.post(
            "/v1/customers/",
            json={
                "external_id": "npt-neg",
                "name": "Negative NPT",
                "net_payment_term": -5,
            },
        )
        assert response.status_code == 422

    def test_update_customer_grace_period(self, client: TestClient):
        """Test updating customer grace period settings."""
        create_response = client.post(
            "/v1/customers/",
            json={"external_id": "gp-upd", "name": "Update GP"},
        )
        customer_id = create_response.json()["id"]

        response = client.put(
            f"/v1/customers/{customer_id}",
            json={"invoice_grace_period": 10, "net_payment_term": 60},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["invoice_grace_period"] == 10
        assert data["net_payment_term"] == 60

    def test_update_customer_grace_period_partial(self, client: TestClient):
        """Test partial update of grace period (only one field)."""
        create_response = client.post(
            "/v1/customers/",
            json={
                "external_id": "gp-partial",
                "name": "Partial GP",
                "invoice_grace_period": 5,
                "net_payment_term": 45,
            },
        )
        customer_id = create_response.json()["id"]

        # Only update net_payment_term
        response = client.put(
            f"/v1/customers/{customer_id}",
            json={"net_payment_term": 90},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["invoice_grace_period"] == 5  # Unchanged
        assert data["net_payment_term"] == 90  # Updated

    def test_update_customer_grace_period_negative(self, client: TestClient):
        """Test updating customer with negative grace period is rejected."""
        create_response = client.post(
            "/v1/customers/",
            json={"external_id": "gp-upd-neg", "name": "Update Neg GP"},
        )
        customer_id = create_response.json()["id"]

        response = client.put(
            f"/v1/customers/{customer_id}",
            json={"invoice_grace_period": -1},
        )
        assert response.status_code == 422
