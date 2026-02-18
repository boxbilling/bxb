"""Customer API tests for bxb."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.add_on import AddOn
from app.models.applied_add_on import AppliedAddOn
from app.models.billable_metric import BillableMetric
from app.models.charge import Charge, ChargeModel
from app.models.customer import Customer, UUIDType, generate_uuid, utc_now
from app.models.event import Event
from app.models.integration import Integration
from app.models.integration_customer import IntegrationCustomer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.plan import Plan, PlanInterval
from app.models.subscription import BillingTime, Subscription, SubscriptionStatus
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate
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
        repo.create(data, DEFAULT_ORG_ID)

        customer = repo.get_by_external_id("ext-123", DEFAULT_ORG_ID)
        assert customer is not None
        assert customer.external_id == "ext-123"

        # Test not found
        not_found = repo.get_by_external_id("nonexistent", DEFAULT_ORG_ID)
        assert not_found is None

    def test_external_id_exists(self, db_session):
        """Test checking if external_id exists."""
        repo = CustomerRepository(db_session)
        data = CustomerCreate(
            external_id="exists-123",
            name="Test Customer",
        )
        repo.create(data, DEFAULT_ORG_ID)

        assert repo.external_id_exists("exists-123", DEFAULT_ORG_ID) is True
        assert repo.external_id_exists("not-exists", DEFAULT_ORG_ID) is False


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
        assert data["billing_entity_id"] is None
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


# Fixed reference dates for usage endpoint tests
_SUB_START = datetime(2026, 1, 1, tzinfo=UTC)
_EVENT_TIME = datetime(2026, 2, 10, tzinfo=UTC)


class TestCustomerUsageAPI:
    """Tests for customer usage endpoints."""

    @pytest.fixture
    def usage_setup(self, db_session):
        """Create customer, plan, subscription, metric, charge, and events for usage tests."""
        customer = Customer(external_id="usage-cust-001", name="Usage Customer")
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        plan = Plan(
            code="usage-plan",
            name="Usage Plan",
            interval=PlanInterval.MONTHLY.value,
            currency="USD",
        )
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)

        subscription = Subscription(
            external_id="usage-sub-001",
            customer_id=customer.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            billing_time=BillingTime.CALENDAR.value,
            started_at=_SUB_START,
        )
        db_session.add(subscription)
        db_session.commit()
        db_session.refresh(subscription)

        metric = BillableMetric(
            code="usage_api_calls",
            name="API Calls",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "0.10"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # Add events in the current billing period (Feb 2026)
        for i in range(5):
            db_session.add(
                Event(
                    external_customer_id=str(customer.external_id),
                    code="usage_api_calls",
                    transaction_id=f"usage_tx_{uuid.uuid4()}",
                    timestamp=_EVENT_TIME + timedelta(hours=i),
                    properties={},
                )
            )
        db_session.commit()

        return {
            "customer": customer,
            "plan": plan,
            "subscription": subscription,
            "metric": metric,
            "charge": charge,
        }

    def test_current_usage_with_charges(self, client: TestClient, db_session, usage_setup):
        """Test GET current_usage returns charges and amount."""
        customer = usage_setup["customer"]
        subscription = usage_setup["subscription"]

        response = client.get(
            f"/v1/customers/{customer.external_id}/current_usage",
            params={"subscription_id": str(subscription.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["currency"] == "USD"
        assert data["from_datetime"] is not None
        assert data["to_datetime"] is not None
        assert len(data["charges"]) == 1
        charge = data["charges"][0]
        assert charge["billable_metric"]["code"] == "usage_api_calls"
        assert charge["billable_metric"]["name"] == "API Calls"
        assert float(charge["units"]) == 5.0
        # 5 * 0.10 = 0.50
        assert float(charge["amount_cents"]) == 0.5
        assert float(data["amount_cents"]) == 0.5

    def test_projected_usage(self, client: TestClient, db_session, usage_setup):
        """Test GET projected_usage returns same as current for now."""
        customer = usage_setup["customer"]
        subscription = usage_setup["subscription"]

        response = client.get(
            f"/v1/customers/{customer.external_id}/projected_usage",
            params={"subscription_id": str(subscription.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["currency"] == "USD"
        assert len(data["charges"]) == 1
        assert float(data["charges"][0]["units"]) == 5.0
        assert float(data["amount_cents"]) == 0.5

    def test_past_usage_with_multiple_periods(self, client: TestClient, db_session, usage_setup):
        """Test GET past_usage returns usage for completed billing periods."""
        customer = usage_setup["customer"]
        subscription = usage_setup["subscription"]

        # Add events in January 2026 (past billing period)
        jan_time = datetime(2026, 1, 15, tzinfo=UTC)
        for i in range(3):
            db_session.add(
                Event(
                    external_customer_id=str(customer.external_id),
                    code="usage_api_calls",
                    transaction_id=f"usage_past_jan_{uuid.uuid4()}",
                    timestamp=jan_time + timedelta(hours=i),
                    properties={},
                )
            )
        db_session.commit()

        response = client.get(
            f"/v1/customers/{customer.external_id}/past_usage",
            params={
                "external_subscription_id": str(subscription.external_id),
                "periods_count": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # First period (most recent past) should be January
        # Second period should be December (no events, zero usage)
        for period in data:
            assert period["currency"] == "USD"
            assert period["from_datetime"] is not None
            assert period["to_datetime"] is not None
            assert "charges" in period

    def test_current_usage_customer_not_found(self, client: TestClient):
        """Test 404 when customer external_id does not exist."""
        fake_sub_id = str(uuid.uuid4())
        response = client.get(
            "/v1/customers/nonexistent-customer/current_usage",
            params={"subscription_id": fake_sub_id},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"

    def test_projected_usage_customer_not_found(self, client: TestClient):
        """Test 404 for projected_usage with unknown customer."""
        fake_sub_id = str(uuid.uuid4())
        response = client.get(
            "/v1/customers/nonexistent-customer/projected_usage",
            params={"subscription_id": fake_sub_id},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"

    def test_past_usage_customer_not_found(self, client: TestClient):
        """Test 404 for past_usage with unknown customer."""
        response = client.get(
            "/v1/customers/nonexistent-customer/past_usage",
            params={"external_subscription_id": "nonexistent-sub"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"

    def test_current_usage_subscription_not_belonging_to_customer(
        self, client: TestClient, db_session, usage_setup
    ):
        """Test 404 when subscription does not belong to the customer."""
        # Create another customer
        other_customer = Customer(external_id="other-cust-001", name="Other Customer")
        db_session.add(other_customer)
        db_session.commit()
        db_session.refresh(other_customer)

        subscription = usage_setup["subscription"]

        response = client.get(
            f"/v1/customers/{other_customer.external_id}/current_usage",
            params={"subscription_id": str(subscription.id)},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription does not belong to this customer"

    def test_current_usage_subscription_not_found(
        self, client: TestClient, db_session, usage_setup
    ):
        """Test 404 when subscription_id does not exist."""
        customer = usage_setup["customer"]
        fake_sub_id = str(uuid.uuid4())

        response = client.get(
            f"/v1/customers/{customer.external_id}/current_usage",
            params={"subscription_id": fake_sub_id},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_past_usage_subscription_not_found(
        self, client: TestClient, db_session, usage_setup
    ):
        """Test 404 for past_usage when subscription external_id not found."""
        customer = usage_setup["customer"]

        response = client.get(
            f"/v1/customers/{customer.external_id}/past_usage",
            params={"external_subscription_id": "nonexistent-sub"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_past_usage_subscription_not_belonging_to_customer(
        self, client: TestClient, db_session, usage_setup
    ):
        """Test 404 for past_usage when subscription belongs to another customer."""
        other_customer = Customer(external_id="other-past-cust", name="Other Past Customer")
        db_session.add(other_customer)
        db_session.commit()
        db_session.refresh(other_customer)

        subscription = usage_setup["subscription"]

        response = client.get(
            f"/v1/customers/{other_customer.external_id}/past_usage",
            params={
                "external_subscription_id": str(subscription.external_id),
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription does not belong to this customer"

    def test_past_usage_plan_not_found(self, client: TestClient, db_session):
        """Test 404 for past_usage when subscription's plan is deleted."""
        customer = Customer(external_id="plan-del-cust", name="Plan Del Customer")
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        plan = Plan(
            code="plan-del-test",
            name="Plan Del Test",
            interval=PlanInterval.MONTHLY.value,
            currency="USD",
        )
        db_session.add(plan)
        db_session.commit()
        db_session.refresh(plan)

        subscription = Subscription(
            external_id="plan-del-sub",
            customer_id=customer.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            billing_time=BillingTime.CALENDAR.value,
            started_at=_SUB_START,
        )
        db_session.add(subscription)
        db_session.commit()
        db_session.refresh(subscription)

        # Delete the plan
        db_session.delete(plan)
        db_session.commit()

        response = client.get(
            f"/v1/customers/{customer.external_id}/past_usage",
            params={"external_subscription_id": str(subscription.external_id)},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"


class TestCustomerHealthAPI:
    """Tests for customer health indicator endpoint."""

    def _create_customer(self, db_session) -> Customer:
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id=f"health-cust-{uuid.uuid4().hex[:8]}",
            name="Health Test Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        return customer

    def _create_invoice(
        self, db_session, customer: Customer, status: str, overdue: bool = False
    ) -> Invoice:
        now = datetime.now(UTC)
        due_date = now - timedelta(days=10) if overdue else now + timedelta(days=30)
        inv = Invoice(
            organization_id=DEFAULT_ORG_ID,
            invoice_number=f"HEALTH-INV-{uuid.uuid4().hex[:8]}",
            customer_id=customer.id,
            status=status,
            billing_period_start=now - timedelta(days=30),
            billing_period_end=now,
            subtotal=Decimal("100.00"),
            total=Decimal("100.00"),
            currency="USD",
            due_date=due_date,
            issued_at=now - timedelta(days=5),
            line_items=[],
        )
        db_session.add(inv)
        db_session.commit()
        db_session.refresh(inv)
        return inv

    def _create_payment(
        self, db_session, customer: Customer, invoice: Invoice, status: str
    ) -> Payment:
        payment = Payment(
            organization_id=DEFAULT_ORG_ID,
            invoice_id=invoice.id,
            customer_id=customer.id,
            amount=Decimal("100.00"),
            currency="USD",
            status=status,
            provider="stripe",
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)
        return payment

    def test_health_good_no_billing_history(self, client: TestClient, db_session):
        """Customer with no invoices or payments is healthy."""
        customer = self._create_customer(db_session)
        response = client.get(f"/v1/customers/{customer.id}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "good"
        assert data["total_invoices"] == 0
        assert data["paid_invoices"] == 0
        assert data["overdue_invoices"] == 0
        assert data["total_payments"] == 0
        assert data["failed_payments"] == 0
        assert data["overdue_amount"] == 0.0

    def test_health_good_all_paid(self, client: TestClient, db_session):
        """Customer with all invoices paid is healthy."""
        customer = self._create_customer(db_session)
        inv = self._create_invoice(db_session, customer, InvoiceStatus.PAID.value)
        self._create_payment(db_session, customer, inv, PaymentStatus.SUCCEEDED.value)

        response = client.get(f"/v1/customers/{customer.id}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "good"
        assert data["total_invoices"] == 1
        assert data["paid_invoices"] == 1
        assert data["overdue_invoices"] == 0

    def test_health_warning_unpaid_not_overdue(self, client: TestClient, db_session):
        """Customer with finalized but not-yet-overdue invoice is warning."""
        customer = self._create_customer(db_session)
        self._create_invoice(
            db_session, customer, InvoiceStatus.FINALIZED.value, overdue=False
        )

        response = client.get(f"/v1/customers/{customer.id}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "warning"
        assert data["total_invoices"] == 1
        assert data["paid_invoices"] == 0
        assert data["overdue_invoices"] == 0

    def test_health_warning_one_failed_payment(self, client: TestClient, db_session):
        """Customer with exactly one failed payment is warning."""
        customer = self._create_customer(db_session)
        inv = self._create_invoice(db_session, customer, InvoiceStatus.PAID.value)
        self._create_payment(db_session, customer, inv, PaymentStatus.FAILED.value)

        response = client.get(f"/v1/customers/{customer.id}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "warning"
        assert data["failed_payments"] == 1

    def test_health_critical_overdue_invoices(self, client: TestClient, db_session):
        """Customer with overdue invoices is critical."""
        customer = self._create_customer(db_session)
        self._create_invoice(
            db_session, customer, InvoiceStatus.FINALIZED.value, overdue=True
        )

        response = client.get(f"/v1/customers/{customer.id}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "critical"
        assert data["overdue_invoices"] == 1
        assert data["overdue_amount"] == 100.0

    def test_health_critical_multiple_failed_payments(
        self, client: TestClient, db_session
    ):
        """Customer with 2+ failed payments is critical."""
        customer = self._create_customer(db_session)
        inv = self._create_invoice(db_session, customer, InvoiceStatus.PAID.value)
        self._create_payment(db_session, customer, inv, PaymentStatus.FAILED.value)
        self._create_payment(db_session, customer, inv, PaymentStatus.FAILED.value)

        response = client.get(f"/v1/customers/{customer.id}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "critical"
        assert data["failed_payments"] == 2

    def test_health_excludes_draft_and_voided(self, client: TestClient, db_session):
        """Draft and voided invoices are excluded from health calculation."""
        customer = self._create_customer(db_session)
        self._create_invoice(db_session, customer, InvoiceStatus.DRAFT.value)
        self._create_invoice(db_session, customer, InvoiceStatus.VOIDED.value)

        response = client.get(f"/v1/customers/{customer.id}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "good"
        assert data["total_invoices"] == 0

    def test_health_customer_not_found(self, client: TestClient):
        """404 for nonexistent customer."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/customers/{fake_id}/health")
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"

    def test_health_mixed_scenario(self, client: TestClient, db_session):
        """Customer with mix of paid invoices and one overdue is critical."""
        customer = self._create_customer(db_session)
        inv1 = self._create_invoice(db_session, customer, InvoiceStatus.PAID.value)
        self._create_payment(db_session, customer, inv1, PaymentStatus.SUCCEEDED.value)
        self._create_invoice(
            db_session, customer, InvoiceStatus.FINALIZED.value, overdue=True
        )

        response = client.get(f"/v1/customers/{customer.id}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "critical"
        assert data["total_invoices"] == 2
        assert data["paid_invoices"] == 1
        assert data["overdue_invoices"] == 1


class TestCustomerAppliedAddOnsAPI:
    """Tests for GET /v1/customers/{customer_id}/applied_add_ons endpoint."""

    def test_list_applied_add_ons_empty(self, client: TestClient, db_session):
        """Customer with no applied add-ons returns empty list."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id=f"addon-empty-{uuid.uuid4().hex[:8]}",
            name="No AddOns Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        response = client.get(f"/v1/customers/{customer.id}/applied_add_ons")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_applied_add_ons_success(self, client: TestClient, db_session):
        """Customer with applied add-ons returns correct data."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id=f"addon-succ-{uuid.uuid4().hex[:8]}",
            name="AddOn Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        add_on = AddOn(
            organization_id=DEFAULT_ORG_ID,
            code=f"addon-{uuid.uuid4().hex[:8]}",
            name="Test Add-On",
            amount_cents=Decimal("1000"),
            amount_currency="USD",
        )
        db_session.add(add_on)
        db_session.commit()
        db_session.refresh(add_on)

        applied = AppliedAddOn(
            add_on_id=add_on.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
        )
        db_session.add(applied)
        db_session.commit()
        db_session.refresh(applied)

        response = client.get(f"/v1/customers/{customer.id}/applied_add_ons")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        item = data[0]
        assert item["add_on_id"] == str(add_on.id)
        assert item["customer_id"] == str(customer.id)
        assert item["customer_name"] == "AddOn Customer"
        assert float(item["amount_cents"]) == 1000
        assert item["amount_currency"] == "USD"

    def test_list_applied_add_ons_customer_not_found(self, client: TestClient):
        """404 for nonexistent customer."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/customers/{fake_id}/applied_add_ons")
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"


class TestCustomerIntegrationMappingsAPI:
    """Tests for GET /v1/customers/{customer_id}/integration_mappings endpoint."""

    def test_list_integration_mappings_empty(self, client: TestClient, db_session):
        """Customer with no integration mappings returns empty list."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id=f"intmap-empty-{uuid.uuid4().hex[:8]}",
            name="No Mappings Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        response = client.get(f"/v1/customers/{customer.id}/integration_mappings")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_integration_mappings_success(self, client: TestClient, db_session):
        """Customer with integration mappings returns correct data."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id=f"intmap-succ-{uuid.uuid4().hex[:8]}",
            name="Mapped Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        integration = Integration(
            organization_id=DEFAULT_ORG_ID,
            integration_type="payment_provider",
            provider_type="stripe",
            settings={},
        )
        db_session.add(integration)
        db_session.commit()
        db_session.refresh(integration)

        ic = IntegrationCustomer(
            integration_id=integration.id,
            customer_id=customer.id,
            external_customer_id="stripe_cus_123",
        )
        db_session.add(ic)
        db_session.commit()
        db_session.refresh(ic)

        response = client.get(f"/v1/customers/{customer.id}/integration_mappings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        item = data[0]
        assert item["integration_name"] == "payment_provider"
        assert item["integration_provider"] == "stripe"
        assert item["external_customer_id"] == "stripe_cus_123"

    def test_list_integration_mappings_missing_integration(
        self, client: TestClient, db_session
    ):
        """Mapping with missing integration returns 'Unknown' for name and provider."""
        from sqlalchemy import text

        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id=f"intmap-miss-{uuid.uuid4().hex[:8]}",
            name="Missing Integration Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        fake_integration_id = uuid.uuid4()
        mapping_id = uuid.uuid4()
        # Disable FK checks to insert an orphan mapping
        db_session.execute(text("PRAGMA foreign_keys=OFF"))
        db_session.execute(
            IntegrationCustomer.__table__.insert().values(
                id=str(mapping_id),
                integration_id=str(fake_integration_id),
                customer_id=str(customer.id),
                external_customer_id="orphan_cus_456",
            )
        )
        db_session.commit()
        db_session.execute(text("PRAGMA foreign_keys=ON"))

        response = client.get(f"/v1/customers/{customer.id}/integration_mappings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["integration_name"] == "Unknown"
        assert data[0]["integration_provider"] == "Unknown"

    def test_list_integration_mappings_customer_not_found(self, client: TestClient):
        """404 for nonexistent customer."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/customers/{fake_id}/integration_mappings")
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"
