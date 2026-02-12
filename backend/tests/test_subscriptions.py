"""Subscription API tests for bxb."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.customer import Customer
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate


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


def create_test_customer(db_session, external_id: str = "cust_123") -> Customer:
    """Helper to create a test customer."""
    customer = Customer(
        external_id=external_id,
        name=f"Test Customer {external_id}",
        email="test@example.com",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


def create_test_plan(db_session, code: str = "test_plan") -> Plan:
    """Helper to create a test plan."""
    plan = Plan(
        code=code,
        name=f"Test Plan {code}",
        interval=PlanInterval.MONTHLY.value,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


class TestSubscriptionStatus:
    def test_pending(self):
        """Test PENDING status."""
        assert SubscriptionStatus.PENDING == "pending"
        assert SubscriptionStatus.PENDING.value == "pending"

    def test_active(self):
        """Test ACTIVE status."""
        assert SubscriptionStatus.ACTIVE == "active"
        assert SubscriptionStatus.ACTIVE.value == "active"

    def test_canceled(self):
        """Test CANCELED status."""
        assert SubscriptionStatus.CANCELED == "canceled"
        assert SubscriptionStatus.CANCELED.value == "canceled"

    def test_terminated(self):
        """Test TERMINATED status."""
        assert SubscriptionStatus.TERMINATED == "terminated"
        assert SubscriptionStatus.TERMINATED.value == "terminated"


class TestSubscriptionModel:
    def test_subscription_defaults(self, db_session):
        """Test Subscription model default values."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)

        subscription = Subscription(
            external_id="sub_123",
            customer_id=customer.id,
            plan_id=plan.id,
        )
        db_session.add(subscription)
        db_session.commit()
        db_session.refresh(subscription)

        assert subscription.id is not None
        assert subscription.external_id == "sub_123"
        assert subscription.customer_id == customer.id
        assert subscription.plan_id == plan.id
        assert subscription.status == "pending"
        assert subscription.started_at is None
        assert subscription.ending_at is None
        assert subscription.canceled_at is None
        assert subscription.created_at is not None
        assert subscription.updated_at is not None


class TestSubscriptionRepository:
    def test_get_by_id(self, db_session):
        """Test getting subscription by ID."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        data = SubscriptionCreate(
            external_id="sub_get",
            customer_id=customer.id,
            plan_id=plan.id,
        )
        subscription = repo.create(data)

        found = repo.get_by_id(subscription.id)
        assert found is not None
        assert found.id == subscription.id

        not_found = repo.get_by_id(uuid.uuid4())
        assert not_found is None

    def test_get_by_external_id(self, db_session):
        """Test getting subscription by external_id."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        repo.create(
            SubscriptionCreate(
                external_id="sub_ext",
                customer_id=customer.id,
                plan_id=plan.id,
            )
        )

        found = repo.get_by_external_id("sub_ext")
        assert found is not None
        assert found.external_id == "sub_ext"

        not_found = repo.get_by_external_id("nonexistent")
        assert not_found is None

    def test_get_by_customer_id(self, db_session):
        """Test getting subscriptions by customer_id."""
        customer = create_test_customer(db_session)
        plan1 = create_test_plan(db_session, "plan1")
        plan2 = create_test_plan(db_session, "plan2")
        repo = SubscriptionRepository(db_session)

        repo.create(
            SubscriptionCreate(external_id="sub1", customer_id=customer.id, plan_id=plan1.id)
        )
        repo.create(
            SubscriptionCreate(external_id="sub2", customer_id=customer.id, plan_id=plan2.id)
        )

        subscriptions = repo.get_by_customer_id(customer.id)
        assert len(subscriptions) == 2

        empty = repo.get_by_customer_id(uuid.uuid4())
        assert len(empty) == 0

    def test_create_pending(self, db_session):
        """Test creating a subscription without started_at (PENDING)."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_pending",
                customer_id=customer.id,
                plan_id=plan.id,
            )
        )

        assert subscription.status == "pending"
        assert subscription.started_at is None

    def test_create_active_past_start(self, db_session):
        """Test creating a subscription with past started_at (ACTIVE)."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        past_time = datetime.now(UTC) - timedelta(hours=1)
        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_active",
                customer_id=customer.id,
                plan_id=plan.id,
                started_at=past_time,
            )
        )

        assert subscription.status == "active"
        # Compare timestamps without timezone (SQLite doesn't preserve tz info)
        assert subscription.started_at.replace(tzinfo=None) == past_time.replace(tzinfo=None)

    def test_create_pending_future_start(self, db_session):
        """Test creating a subscription with future started_at (PENDING)."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        future_time = datetime.now(UTC) + timedelta(days=1)
        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_future",
                customer_id=customer.id,
                plan_id=plan.id,
                started_at=future_time,
            )
        )

        assert subscription.status == "pending"
        # Compare timestamps without timezone (SQLite doesn't preserve tz info)
        assert subscription.started_at.replace(tzinfo=None) == future_time.replace(tzinfo=None)

    def test_update(self, db_session):
        """Test updating a subscription."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_update",
                customer_id=customer.id,
                plan_id=plan.id,
            )
        )

        ending = datetime.now(UTC) + timedelta(days=30)
        updated = repo.update(
            subscription.id,
            SubscriptionUpdate(
                status=SubscriptionStatus.ACTIVE,
                ending_at=ending,
            ),
        )
        assert updated is not None
        assert updated.status == "active"
        # Compare timestamps without timezone (SQLite doesn't preserve tz info)
        assert updated.ending_at.replace(tzinfo=None) == ending.replace(tzinfo=None)

    def test_update_partial(self, db_session):
        """Test partial update of a subscription (without status)."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_partial",
                customer_id=customer.id,
                plan_id=plan.id,
            )
        )

        # Update only ending_at, not status (tests branch where status not in update_data)
        ending = datetime.now(UTC) + timedelta(days=30)
        updated = repo.update(
            subscription.id,
            SubscriptionUpdate(
                ending_at=ending,
            ),
        )
        assert updated is not None
        assert updated.status == "pending"  # Unchanged
        assert updated.ending_at.replace(tzinfo=None) == ending.replace(tzinfo=None)

    def test_update_with_none_status(self, db_session):
        """Test updating a subscription with explicit None status (should skip conversion)."""
        customer = create_test_customer(db_session, "cust_none")
        plan = create_test_plan(db_session, "plan_none")
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_none_status",
                customer_id=customer.id,
                plan_id=plan.id,
            )
        )

        # Update with explicit None for status (tests the branch where status is in data but is None)
        canceled_time = datetime.now(UTC)
        updated = repo.update(
            subscription.id,
            SubscriptionUpdate(
                status=None,  # Explicitly None
                canceled_at=canceled_time,
            ),
        )
        assert updated is not None
        assert updated.status == "pending"  # Status unchanged
        assert updated.canceled_at is not None

    def test_update_not_found(self, db_session):
        """Test updating a non-existent subscription."""
        repo = SubscriptionRepository(db_session)
        result = repo.update(uuid.uuid4(), SubscriptionUpdate(status=SubscriptionStatus.ACTIVE))
        assert result is None

    def test_delete(self, db_session):
        """Test deleting a subscription."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_delete",
                customer_id=customer.id,
                plan_id=plan.id,
            )
        )

        assert repo.delete(subscription.id) is True
        assert repo.get_by_id(subscription.id) is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent subscription."""
        repo = SubscriptionRepository(db_session)
        assert repo.delete(uuid.uuid4()) is False

    def test_terminate(self, db_session):
        """Test terminating a subscription."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_term",
                customer_id=customer.id,
                plan_id=plan.id,
            )
        )

        terminated = repo.terminate(subscription.id)
        assert terminated is not None
        assert terminated.status == "terminated"
        assert terminated.ending_at is not None

    def test_terminate_not_found(self, db_session):
        """Test terminating a non-existent subscription."""
        repo = SubscriptionRepository(db_session)
        result = repo.terminate(uuid.uuid4())
        assert result is None

    def test_cancel(self, db_session):
        """Test canceling a subscription."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_cancel",
                customer_id=customer.id,
                plan_id=plan.id,
            )
        )

        canceled = repo.cancel(subscription.id)
        assert canceled is not None
        assert canceled.status == "canceled"
        assert canceled.canceled_at is not None

    def test_cancel_not_found(self, db_session):
        """Test canceling a non-existent subscription."""
        repo = SubscriptionRepository(db_session)
        result = repo.cancel(uuid.uuid4())
        assert result is None

    def test_external_id_exists(self, db_session):
        """Test checking if external_id exists."""
        customer = create_test_customer(db_session)
        plan = create_test_plan(db_session)
        repo = SubscriptionRepository(db_session)

        repo.create(
            SubscriptionCreate(
                external_id="exists_test",
                customer_id=customer.id,
                plan_id=plan.id,
            )
        )

        assert repo.external_id_exists("exists_test") is True
        assert repo.external_id_exists("not_exists") is False


class TestSubscriptionsAPI:
    def test_list_subscriptions_empty(self, client: TestClient):
        """Test listing subscriptions when none exist."""
        response = client.get("/v1/subscriptions/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_subscription(self, client: TestClient):
        """Test creating a subscription."""
        # Create customer
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_api", "name": "API Customer"},
        ).json()

        # Create plan
        plan = client.post(
            "/v1/plans/",
            json={"code": "api_plan", "name": "API Plan", "interval": "monthly"},
        ).json()

        # Create subscription
        response = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_api",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["external_id"] == "sub_api"
        assert data["customer_id"] == customer["id"]
        assert data["plan_id"] == plan["id"]
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    def test_create_subscription_with_start_date(self, client: TestClient):
        """Test creating a subscription with a past start date (ACTIVE)."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_start", "name": "Start Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "start_plan", "name": "Start Plan", "interval": "monthly"},
        ).json()

        past_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        response = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_started",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
                "started_at": past_time,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "active"

    def test_create_subscription_duplicate_external_id(self, client: TestClient):
        """Test creating a subscription with duplicate external_id."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_dup", "name": "Dup Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "dup_plan", "name": "Dup Plan", "interval": "monthly"},
        ).json()

        client.post(
            "/v1/subscriptions/",
            json={"external_id": "dup_sub", "customer_id": customer["id"], "plan_id": plan["id"]},
        )
        response = client.post(
            "/v1/subscriptions/",
            json={"external_id": "dup_sub", "customer_id": customer["id"], "plan_id": plan["id"]},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Subscription with this external_id already exists"

    def test_create_subscription_invalid_customer(self, client: TestClient):
        """Test creating a subscription with non-existent customer."""
        plan = client.post(
            "/v1/plans/",
            json={"code": "inv_cust_plan", "name": "Invalid Customer Plan", "interval": "monthly"},
        ).json()

        fake_customer_id = str(uuid.uuid4())
        response = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "inv_cust",
                "customer_id": fake_customer_id,
                "plan_id": plan["id"],
            },
        )
        assert response.status_code == 400
        assert f"Customer {fake_customer_id} not found" in response.json()["detail"]

    def test_create_subscription_invalid_plan(self, client: TestClient):
        """Test creating a subscription with non-existent plan."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_inv_plan", "name": "Invalid Plan Customer"},
        ).json()

        fake_plan_id = str(uuid.uuid4())
        response = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "inv_plan",
                "customer_id": customer["id"],
                "plan_id": fake_plan_id,
            },
        )
        assert response.status_code == 400
        assert f"Plan {fake_plan_id} not found" in response.json()["detail"]

    def test_create_subscription_empty_external_id(self, client: TestClient):
        """Test creating a subscription with empty external_id."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_empty", "name": "Empty Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "empty_plan", "name": "Empty Plan", "interval": "monthly"},
        ).json()

        response = client.post(
            "/v1/subscriptions/",
            json={"external_id": "", "customer_id": customer["id"], "plan_id": plan["id"]},
        )
        assert response.status_code == 422

    def test_get_subscription(self, client: TestClient):
        """Test getting a subscription by ID."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_get", "name": "Get Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "get_plan", "name": "Get Plan", "interval": "monthly"},
        ).json()
        create_response = client.post(
            "/v1/subscriptions/",
            json={"external_id": "sub_get", "customer_id": customer["id"], "plan_id": plan["id"]},
        )
        subscription_id = create_response.json()["id"]

        response = client.get(f"/v1/subscriptions/{subscription_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == subscription_id
        assert data["external_id"] == "sub_get"

    def test_get_subscription_not_found(self, client: TestClient):
        """Test getting a non-existent subscription."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/subscriptions/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_get_subscription_invalid_uuid(self, client: TestClient):
        """Test getting a subscription with invalid UUID."""
        response = client.get("/v1/subscriptions/not-a-uuid")
        assert response.status_code == 422

    def test_update_subscription(self, client: TestClient):
        """Test updating a subscription."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_upd", "name": "Update Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "upd_plan", "name": "Update Plan", "interval": "monthly"},
        ).json()
        create_response = client.post(
            "/v1/subscriptions/",
            json={"external_id": "sub_upd", "customer_id": customer["id"], "plan_id": plan["id"]},
        )
        subscription_id = create_response.json()["id"]

        response = client.put(
            f"/v1/subscriptions/{subscription_id}",
            json={"status": "active"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

    def test_update_subscription_not_found(self, client: TestClient):
        """Test updating a non-existent subscription."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/v1/subscriptions/{fake_id}",
            json={"status": "active"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_terminate_subscription(self, client: TestClient):
        """Test terminating a subscription via DELETE."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_term", "name": "Terminate Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "term_plan", "name": "Terminate Plan", "interval": "monthly"},
        ).json()
        create_response = client.post(
            "/v1/subscriptions/",
            json={"external_id": "sub_term", "customer_id": customer["id"], "plan_id": plan["id"]},
        )
        subscription_id = create_response.json()["id"]

        response = client.delete(f"/v1/subscriptions/{subscription_id}")
        assert response.status_code == 204

        # Verify it's terminated (not deleted)
        get_response = client.get(f"/v1/subscriptions/{subscription_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "terminated"
        assert get_response.json()["ending_at"] is not None

    def test_terminate_subscription_not_found(self, client: TestClient):
        """Test terminating a non-existent subscription."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/v1/subscriptions/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_cancel_subscription(self, client: TestClient):
        """Test canceling a subscription."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_cancel", "name": "Cancel Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "cancel_plan", "name": "Cancel Plan", "interval": "monthly"},
        ).json()
        create_response = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_cancel",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
            },
        )
        subscription_id = create_response.json()["id"]

        response = client.post(f"/v1/subscriptions/{subscription_id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "canceled"
        assert data["canceled_at"] is not None

    def test_cancel_subscription_not_found(self, client: TestClient):
        """Test canceling a non-existent subscription."""
        fake_id = str(uuid.uuid4())
        response = client.post(f"/v1/subscriptions/{fake_id}/cancel")
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_list_subscriptions_pagination(self, client: TestClient):
        """Test listing subscriptions with pagination."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_page", "name": "Page Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "page_plan", "name": "Page Plan", "interval": "monthly"},
        ).json()

        for i in range(5):
            client.post(
                "/v1/subscriptions/",
                json={
                    "external_id": f"sub_page_{i}",
                    "customer_id": customer["id"],
                    "plan_id": plan["id"],
                },
            )

        response = client.get("/v1/subscriptions/?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_subscriptions_by_customer(self, client: TestClient):
        """Test listing subscriptions filtered by customer_id."""
        customer1 = client.post(
            "/v1/customers/",
            json={"external_id": "cust_filter1", "name": "Filter Customer 1"},
        ).json()
        customer2 = client.post(
            "/v1/customers/",
            json={"external_id": "cust_filter2", "name": "Filter Customer 2"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "filter_plan", "name": "Filter Plan", "interval": "monthly"},
        ).json()

        client.post(
            "/v1/subscriptions/",
            json={"external_id": "sub_c1_1", "customer_id": customer1["id"], "plan_id": plan["id"]},
        )
        client.post(
            "/v1/subscriptions/",
            json={"external_id": "sub_c1_2", "customer_id": customer1["id"], "plan_id": plan["id"]},
        )
        client.post(
            "/v1/subscriptions/",
            json={"external_id": "sub_c2_1", "customer_id": customer2["id"], "plan_id": plan["id"]},
        )

        # Filter by customer1
        response = client.get(f"/v1/subscriptions/?customer_id={customer1['id']}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        for sub in data:
            assert sub["customer_id"] == customer1["id"]
