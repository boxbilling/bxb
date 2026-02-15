"""Subscription API tests for bxb."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.plan import Plan, PlanInterval
from app.models.subscription import BillingTime, Subscription, SubscriptionStatus, TerminationAction
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
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

    def test_paused(self):
        """Test PAUSED status."""
        assert SubscriptionStatus.PAUSED == "paused"
        assert SubscriptionStatus.PAUSED.value == "paused"

    def test_terminated(self):
        """Test TERMINATED status."""
        assert SubscriptionStatus.TERMINATED == "terminated"
        assert SubscriptionStatus.TERMINATED.value == "terminated"


class TestBillingTime:
    def test_calendar(self):
        """Test CALENDAR billing time."""
        assert BillingTime.CALENDAR == "calendar"
        assert BillingTime.CALENDAR.value == "calendar"

    def test_anniversary(self):
        """Test ANNIVERSARY billing time."""
        assert BillingTime.ANNIVERSARY == "anniversary"
        assert BillingTime.ANNIVERSARY.value == "anniversary"


class TestTerminationAction:
    def test_generate_invoice(self):
        """Test GENERATE_INVOICE termination action."""
        assert TerminationAction.GENERATE_INVOICE == "generate_invoice"
        assert TerminationAction.GENERATE_INVOICE.value == "generate_invoice"

    def test_generate_credit_note(self):
        """Test GENERATE_CREDIT_NOTE termination action."""
        assert TerminationAction.GENERATE_CREDIT_NOTE == "generate_credit_note"
        assert TerminationAction.GENERATE_CREDIT_NOTE.value == "generate_credit_note"

    def test_skip(self):
        """Test SKIP termination action."""
        assert TerminationAction.SKIP == "skip"
        assert TerminationAction.SKIP.value == "skip"


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
        assert subscription.billing_time == "calendar"
        assert subscription.trial_period_days == 0
        assert subscription.trial_ended_at is None
        assert subscription.subscription_at is None
        assert subscription.pay_in_advance is False
        assert subscription.previous_plan_id is None
        assert subscription.downgraded_at is None
        assert subscription.on_termination_action == "generate_invoice"
        assert subscription.started_at is None
        assert subscription.ending_at is None
        assert subscription.canceled_at is None
        assert subscription.paused_at is None
        assert subscription.resumed_at is None
        assert subscription.created_at is not None
        assert subscription.updated_at is not None

    def test_subscription_lifecycle_fields(self, db_session):
        """Test Subscription model with advanced lifecycle fields."""
        customer = create_test_customer(db_session, "cust_lifecycle")
        plan = create_test_plan(db_session, "plan_lifecycle")
        plan2 = create_test_plan(db_session, "plan_lifecycle_prev")

        now = datetime.now(UTC)
        subscription = Subscription(
            external_id="sub_lifecycle",
            customer_id=customer.id,
            plan_id=plan.id,
            billing_time="anniversary",
            trial_period_days=14,
            trial_ended_at=now,
            subscription_at=now,
            pay_in_advance=True,
            previous_plan_id=plan2.id,
            downgraded_at=now,
            on_termination_action="generate_credit_note",
        )
        db_session.add(subscription)
        db_session.commit()
        db_session.refresh(subscription)

        assert subscription.billing_time == "anniversary"
        assert subscription.trial_period_days == 14
        assert subscription.trial_ended_at is not None
        assert subscription.subscription_at is not None
        assert subscription.pay_in_advance is True
        assert subscription.previous_plan_id == plan2.id
        assert subscription.downgraded_at is not None
        assert subscription.on_termination_action == "generate_credit_note"


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
        subscription = repo.create(data, DEFAULT_ORG_ID)

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
            ),
            DEFAULT_ORG_ID,
        )

        found = repo.get_by_external_id("sub_ext", DEFAULT_ORG_ID)
        assert found is not None
        assert found.external_id == "sub_ext"

        not_found = repo.get_by_external_id("nonexistent", DEFAULT_ORG_ID)
        assert not_found is None

    def test_get_by_customer_id(self, db_session):
        """Test getting subscriptions by customer_id."""
        customer = create_test_customer(db_session)
        plan1 = create_test_plan(db_session, "plan1")
        plan2 = create_test_plan(db_session, "plan2")
        repo = SubscriptionRepository(db_session)

        repo.create(
            SubscriptionCreate(external_id="sub1", customer_id=customer.id, plan_id=plan1.id),
            DEFAULT_ORG_ID,
        )
        repo.create(
            SubscriptionCreate(external_id="sub2", customer_id=customer.id, plan_id=plan2.id),
            DEFAULT_ORG_ID,
        )

        subscriptions = repo.get_by_customer_id(customer.id, DEFAULT_ORG_ID)
        assert len(subscriptions) == 2

        empty = repo.get_by_customer_id(uuid.uuid4(), DEFAULT_ORG_ID)
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
            ),
            DEFAULT_ORG_ID,
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
            ),
            DEFAULT_ORG_ID,
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
            ),
            DEFAULT_ORG_ID,
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
            ),
            DEFAULT_ORG_ID,
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
            ),
            DEFAULT_ORG_ID,
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
            ),
            DEFAULT_ORG_ID,
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
            ),
            DEFAULT_ORG_ID,
        )

        assert repo.delete(subscription.id, DEFAULT_ORG_ID) is True
        assert repo.get_by_id(subscription.id) is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent subscription."""
        repo = SubscriptionRepository(db_session)
        assert repo.delete(uuid.uuid4(), DEFAULT_ORG_ID) is False

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
            ),
            DEFAULT_ORG_ID,
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
            ),
            DEFAULT_ORG_ID,
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

    def test_pause(self, db_session):
        """Test pausing a subscription."""
        customer = create_test_customer(db_session, "cust_pause_repo")
        plan = create_test_plan(db_session, "plan_pause_repo")
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_pause_repo",
                customer_id=customer.id,
                plan_id=plan.id,
                started_at=datetime.now(UTC) - timedelta(days=5),
            ),
            DEFAULT_ORG_ID,
        )

        paused = repo.pause(subscription.id)
        assert paused is not None
        assert paused.status == "paused"
        assert paused.paused_at is not None

    def test_pause_not_found(self, db_session):
        """Test pausing a non-existent subscription."""
        repo = SubscriptionRepository(db_session)
        result = repo.pause(uuid.uuid4())
        assert result is None

    def test_resume(self, db_session):
        """Test resuming a paused subscription."""
        customer = create_test_customer(db_session, "cust_resume_repo")
        plan = create_test_plan(db_session, "plan_resume_repo")
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_resume_repo",
                customer_id=customer.id,
                plan_id=plan.id,
                started_at=datetime.now(UTC) - timedelta(days=5),
            ),
            DEFAULT_ORG_ID,
        )

        # Pause first
        repo.pause(subscription.id)
        # Then resume
        resumed = repo.resume(subscription.id)
        assert resumed is not None
        assert resumed.status == "active"
        assert resumed.paused_at is None
        assert resumed.resumed_at is not None

    def test_resume_not_found(self, db_session):
        """Test resuming a non-existent subscription."""
        repo = SubscriptionRepository(db_session)
        result = repo.resume(uuid.uuid4())
        assert result is None

    def test_create_with_lifecycle_fields(self, db_session):
        """Test creating a subscription with advanced lifecycle fields."""
        customer = create_test_customer(db_session, "cust_lc_repo")
        plan = create_test_plan(db_session, "plan_lc_repo")
        repo = SubscriptionRepository(db_session)

        now = datetime.now(UTC)
        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_lc_repo",
                customer_id=customer.id,
                plan_id=plan.id,
                started_at=now - timedelta(hours=1),
                billing_time=BillingTime.ANNIVERSARY,
                trial_period_days=7,
                subscription_at=now,
                pay_in_advance=True,
                on_termination_action=TerminationAction.SKIP,
            ),
            DEFAULT_ORG_ID,
        )

        assert subscription.billing_time == "anniversary"
        assert subscription.trial_period_days == 7
        assert subscription.subscription_at is not None
        assert subscription.pay_in_advance is True
        assert subscription.on_termination_action == "skip"
        assert subscription.status == "active"

    def test_update_billing_time(self, db_session):
        """Test updating billing_time via repository."""
        customer = create_test_customer(db_session, "cust_bt")
        plan = create_test_plan(db_session, "plan_bt")
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_bt",
                customer_id=customer.id,
                plan_id=plan.id,
            ),
            DEFAULT_ORG_ID,
        )
        assert subscription.billing_time == "calendar"

        updated = repo.update(
            subscription.id,
            SubscriptionUpdate(billing_time=BillingTime.ANNIVERSARY),
        )
        assert updated is not None
        assert updated.billing_time == "anniversary"

    def test_update_billing_time_none(self, db_session):
        """Test updating with explicit None billing_time (should skip)."""
        customer = create_test_customer(db_session, "cust_bt_none")
        plan = create_test_plan(db_session, "plan_bt_none")
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_bt_none",
                customer_id=customer.id,
                plan_id=plan.id,
            ),
            DEFAULT_ORG_ID,
        )

        updated = repo.update(
            subscription.id,
            SubscriptionUpdate(billing_time=None, trial_period_days=10),
        )
        assert updated is not None
        assert updated.billing_time == "calendar"  # Unchanged
        assert updated.trial_period_days == 10

    def test_update_on_termination_action(self, db_session):
        """Test updating on_termination_action via repository."""
        customer = create_test_customer(db_session, "cust_ota")
        plan = create_test_plan(db_session, "plan_ota")
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_ota",
                customer_id=customer.id,
                plan_id=plan.id,
            ),
            DEFAULT_ORG_ID,
        )
        assert subscription.on_termination_action == "generate_invoice"

        updated = repo.update(
            subscription.id,
            SubscriptionUpdate(on_termination_action=TerminationAction.GENERATE_CREDIT_NOTE),
        )
        assert updated is not None
        assert updated.on_termination_action == "generate_credit_note"

    def test_update_on_termination_action_none(self, db_session):
        """Test updating with explicit None on_termination_action (should skip)."""
        customer = create_test_customer(db_session, "cust_ota_none")
        plan = create_test_plan(db_session, "plan_ota_none")
        repo = SubscriptionRepository(db_session)

        subscription = repo.create(
            SubscriptionCreate(
                external_id="sub_ota_none",
                customer_id=customer.id,
                plan_id=plan.id,
            ),
            DEFAULT_ORG_ID,
        )

        updated = repo.update(
            subscription.id,
            SubscriptionUpdate(on_termination_action=None, trial_period_days=5),
        )
        assert updated is not None
        assert updated.on_termination_action == "generate_invoice"  # Unchanged
        assert updated.trial_period_days == 5

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
            ),
            DEFAULT_ORG_ID,
        )

        assert repo.external_id_exists("exists_test", DEFAULT_ORG_ID) is True
        assert repo.external_id_exists("not_exists", DEFAULT_ORG_ID) is False


class TestSubscriptionsAPI:
    def test_list_subscriptions_empty(self, client: TestClient):
        """Test listing subscriptions when none exist."""
        response = client.get("/v1/subscriptions/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_subscription(self, client: TestClient, db_session):
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
        assert data["billing_time"] == "calendar"
        assert data["trial_period_days"] == 0
        assert data["trial_ended_at"] is None
        assert data["subscription_at"] is None
        assert data["pay_in_advance"] is False
        assert data["previous_plan_id"] is None
        assert data["downgraded_at"] is None
        assert data["on_termination_action"] == "generate_invoice"
        assert "id" in data
        assert "created_at" in data

        # Verify audit log was created
        sub_id = uuid.UUID(data["id"])
        logs = db_session.query(AuditLog).filter(AuditLog.resource_id == sub_id).all()
        assert any(log.action == "created" for log in logs)

    def test_create_subscription_with_lifecycle_fields(self, client: TestClient):
        """Test creating a subscription with advanced lifecycle fields."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_api_lc", "name": "API LC Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "api_lc_plan", "name": "API LC Plan", "interval": "monthly"},
        ).json()

        sub_at = datetime.now(UTC).isoformat()
        response = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_api_lc",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
                "billing_time": "anniversary",
                "trial_period_days": 14,
                "subscription_at": sub_at,
                "pay_in_advance": True,
                "on_termination_action": "skip",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["billing_time"] == "anniversary"
        assert data["trial_period_days"] == 14
        assert data["subscription_at"] is not None
        assert data["pay_in_advance"] is True
        assert data["on_termination_action"] == "skip"

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

    def test_terminate_subscription(self, client: TestClient, db_session):
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

        # Verify audit log for termination
        sub_id = uuid.UUID(subscription_id)
        logs = db_session.query(AuditLog).filter(
            AuditLog.resource_id == sub_id,
            AuditLog.action == "status_changed",
        ).all()
        assert any(log.changes.get("status", {}).get("new") == "terminated" for log in logs)

    def test_terminate_subscription_not_found(self, client: TestClient):
        """Test terminating a non-existent subscription."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/v1/subscriptions/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_cancel_subscription(self, client: TestClient, db_session):
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

        # Verify audit log for cancellation
        sub_id = uuid.UUID(subscription_id)
        logs = db_session.query(AuditLog).filter(
            AuditLog.resource_id == sub_id,
            AuditLog.action == "status_changed",
        ).all()
        assert any(log.changes.get("status", {}).get("new") == "canceled" for log in logs)

    def test_cancel_subscription_not_found(self, client: TestClient):
        """Test canceling a non-existent subscription."""
        fake_id = str(uuid.uuid4())
        response = client.post(f"/v1/subscriptions/{fake_id}/cancel")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_terminate_with_skip_action(self, client: TestClient):
        """Test terminating with skip on_termination_action."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_term_skip", "name": "Skip Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "term_skip_plan", "name": "Skip Plan", "interval": "monthly"},
        ).json()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_term_skip",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
            },
        ).json()

        response = client.delete(f"/v1/subscriptions/{sub['id']}?on_termination_action=skip")
        assert response.status_code == 204

        get_response = client.get(f"/v1/subscriptions/{sub['id']}")
        assert get_response.json()["status"] == "terminated"

    def test_cancel_with_skip_action(self, client: TestClient):
        """Test canceling with skip on_termination_action."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_can_skip", "name": "Skip Cancel Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "can_skip_plan", "name": "Skip Plan", "interval": "monthly"},
        ).json()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_can_skip",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
            },
        ).json()

        response = client.post(f"/v1/subscriptions/{sub['id']}/cancel?on_termination_action=skip")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "canceled"
        assert data["canceled_at"] is not None

    def test_pause_subscription(self, client: TestClient, db_session):
        """Test pausing a subscription via API."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_pause_api", "name": "Pause Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "pause_plan", "name": "Pause Plan", "interval": "monthly"},
        ).json()
        create_response = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_pause_api",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
                "started_at": (datetime.now(UTC) - timedelta(days=5)).isoformat(),
            },
        )
        subscription_id = create_response.json()["id"]

        response = client.post(f"/v1/subscriptions/{subscription_id}/pause")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"
        assert data["paused_at"] is not None

        # Verify audit log
        sub_id = uuid.UUID(subscription_id)
        logs = db_session.query(AuditLog).filter(
            AuditLog.resource_id == sub_id,
            AuditLog.action == "status_changed",
        ).all()
        assert any(log.changes.get("status", {}).get("new") == "paused" for log in logs)

    def test_pause_subscription_not_found(self, client: TestClient):
        """Test pausing a non-existent subscription."""
        fake_id = str(uuid.uuid4())
        response = client.post(f"/v1/subscriptions/{fake_id}/pause")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_pause_subscription_not_active(self, client: TestClient):
        """Test pausing a non-active subscription returns 400."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_pause_pend", "name": "Pause Pending"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "pause_pend_plan", "name": "Plan", "interval": "monthly"},
        ).json()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_pause_pend",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
            },
        ).json()

        response = client.post(f"/v1/subscriptions/{sub['id']}/pause")
        assert response.status_code == 400
        assert "active" in response.json()["detail"].lower()

    def test_resume_subscription(self, client: TestClient, db_session):
        """Test resuming a paused subscription via API."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_resume_api", "name": "Resume Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "resume_plan", "name": "Resume Plan", "interval": "monthly"},
        ).json()
        create_response = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_resume_api",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
                "started_at": (datetime.now(UTC) - timedelta(days=5)).isoformat(),
            },
        )
        subscription_id = create_response.json()["id"]

        # Pause first
        client.post(f"/v1/subscriptions/{subscription_id}/pause")

        # Resume
        response = client.post(f"/v1/subscriptions/{subscription_id}/resume")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["resumed_at"] is not None
        assert data["paused_at"] is None

        # Verify audit log
        sub_id = uuid.UUID(subscription_id)
        logs = db_session.query(AuditLog).filter(
            AuditLog.resource_id == sub_id,
            AuditLog.action == "status_changed",
        ).all()
        assert any(log.changes.get("status", {}).get("new") == "active" for log in logs)

    def test_resume_subscription_not_found(self, client: TestClient):
        """Test resuming a non-existent subscription."""
        fake_id = str(uuid.uuid4())
        response = client.post(f"/v1/subscriptions/{fake_id}/resume")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_resume_subscription_not_paused(self, client: TestClient):
        """Test resuming a non-paused subscription returns 400."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_resume_act", "name": "Resume Active"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "resume_act_plan", "name": "Plan", "interval": "monthly"},
        ).json()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_resume_act",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
                "started_at": (datetime.now(UTC) - timedelta(days=5)).isoformat(),
            },
        ).json()

        response = client.post(f"/v1/subscriptions/{sub['id']}/resume")
        assert response.status_code == 400
        assert "paused" in response.json()["detail"].lower()

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


class TestChangePlanPreviewAPI:
    """Tests for the change plan preview endpoint."""

    def _setup(self, client: TestClient) -> dict:
        """Create customer, two plans, and a subscription for testing."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": f"cust_cp_{uuid.uuid4().hex[:6]}", "name": "CP Customer"},
        ).json()
        plan_a = client.post(
            "/v1/plans/",
            json={
                "code": f"plan_a_{uuid.uuid4().hex[:6]}",
                "name": "Basic Plan",
                "interval": "monthly",
                "amount_cents": 2000,
                "currency": "USD",
            },
        ).json()
        plan_b = client.post(
            "/v1/plans/",
            json={
                "code": f"plan_b_{uuid.uuid4().hex[:6]}",
                "name": "Pro Plan",
                "interval": "monthly",
                "amount_cents": 5000,
                "currency": "USD",
            },
        ).json()
        started = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": f"sub_cp_{uuid.uuid4().hex[:6]}",
                "customer_id": customer["id"],
                "plan_id": plan_a["id"],
                "started_at": started,
            },
        ).json()
        return {"customer": customer, "plan_a": plan_a, "plan_b": plan_b, "sub": sub}

    def test_change_plan_preview_basic(self, client: TestClient):
        """Test basic plan change preview returns comparison and proration."""
        setup = self._setup(client)
        response = client.post(
            f"/v1/subscriptions/{setup['sub']['id']}/change_plan_preview",
            json={"new_plan_id": setup["plan_b"]["id"]},
        )
        assert response.status_code == 200
        data = response.json()

        # Verify plan summaries
        assert data["current_plan"]["id"] == setup["plan_a"]["id"]
        assert data["current_plan"]["name"] == "Basic Plan"
        assert data["current_plan"]["amount_cents"] == 2000
        assert data["new_plan"]["id"] == setup["plan_b"]["id"]
        assert data["new_plan"]["name"] == "Pro Plan"
        assert data["new_plan"]["amount_cents"] == 5000

        # Verify proration structure
        proration = data["proration"]
        assert "days_remaining" in proration
        assert "total_days" in proration
        assert proration["total_days"] == 30  # monthly
        assert "current_plan_credit_cents" in proration
        assert "new_plan_charge_cents" in proration
        assert "net_amount_cents" in proration
        # Net should be positive (upgrading from $20 to $50)
        assert proration["net_amount_cents"] > 0

    def test_change_plan_preview_with_effective_date(self, client: TestClient):
        """Test preview with explicit future effective date."""
        setup = self._setup(client)
        future_date = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        response = client.post(
            f"/v1/subscriptions/{setup['sub']['id']}/change_plan_preview",
            json={
                "new_plan_id": setup["plan_b"]["id"],
                "effective_date": future_date,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["effective_date"] is not None
        assert data["proration"]["days_remaining"] >= 0

    def test_change_plan_preview_naive_effective_date(self, client: TestClient):
        """Test preview with timezone-naive effective date (no +00:00 suffix)."""
        setup = self._setup(client)
        # Send a naive datetime string without timezone info
        naive_date = (datetime.now(UTC) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
        response = client.post(
            f"/v1/subscriptions/{setup['sub']['id']}/change_plan_preview",
            json={
                "new_plan_id": setup["plan_b"]["id"],
                "effective_date": naive_date,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["proration"]["days_remaining"] >= 0

    def test_change_plan_preview_downgrade(self, client: TestClient):
        """Test preview for a downgrade (new plan is cheaper)."""
        setup = self._setup(client)
        # Create a cheaper plan
        cheap_plan = client.post(
            "/v1/plans/",
            json={
                "code": f"plan_cheap_{uuid.uuid4().hex[:6]}",
                "name": "Starter Plan",
                "interval": "monthly",
                "amount_cents": 500,
                "currency": "USD",
            },
        ).json()
        response = client.post(
            f"/v1/subscriptions/{setup['sub']['id']}/change_plan_preview",
            json={"new_plan_id": cheap_plan["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        # Net should be negative (downgrading from $20 to $5)
        assert data["proration"]["net_amount_cents"] < 0

    def test_change_plan_preview_same_plan(self, client: TestClient):
        """Test preview when selecting the same plan returns 400."""
        setup = self._setup(client)
        response = client.post(
            f"/v1/subscriptions/{setup['sub']['id']}/change_plan_preview",
            json={"new_plan_id": setup["plan_a"]["id"]},
        )
        assert response.status_code == 400
        assert "different" in response.json()["detail"].lower()

    def test_change_plan_preview_subscription_not_found(self, client: TestClient):
        """Test preview with non-existent subscription returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.post(
            f"/v1/subscriptions/{fake_id}/change_plan_preview",
            json={"new_plan_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404
        assert "Subscription not found" in response.json()["detail"]

    def test_change_plan_preview_new_plan_not_found(self, client: TestClient):
        """Test preview with non-existent new plan returns 404."""
        setup = self._setup(client)
        response = client.post(
            f"/v1/subscriptions/{setup['sub']['id']}/change_plan_preview",
            json={"new_plan_id": str(uuid.uuid4())},
        )
        assert response.status_code == 404
        assert "New plan not found" in response.json()["detail"]

    def test_change_plan_preview_weekly_interval(self, client: TestClient):
        """Test proration with weekly plan interval."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": f"cust_wk_{uuid.uuid4().hex[:6]}", "name": "Weekly Cust"},
        ).json()
        plan_weekly = client.post(
            "/v1/plans/",
            json={
                "code": f"plan_wk_{uuid.uuid4().hex[:6]}",
                "name": "Weekly Plan",
                "interval": "weekly",
                "amount_cents": 700,
            },
        ).json()
        plan_weekly_2 = client.post(
            "/v1/plans/",
            json={
                "code": f"plan_wk2_{uuid.uuid4().hex[:6]}",
                "name": "Weekly Plan 2",
                "interval": "weekly",
                "amount_cents": 1400,
            },
        ).json()
        started = (datetime.now(UTC) - timedelta(days=3)).isoformat()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": f"sub_wk_{uuid.uuid4().hex[:6]}",
                "customer_id": customer["id"],
                "plan_id": plan_weekly["id"],
                "started_at": started,
            },
        ).json()
        response = client.post(
            f"/v1/subscriptions/{sub['id']}/change_plan_preview",
            json={"new_plan_id": plan_weekly_2["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["proration"]["total_days"] == 7

    def test_change_plan_preview_yearly_interval(self, client: TestClient):
        """Test proration with yearly plan interval."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": f"cust_yr_{uuid.uuid4().hex[:6]}", "name": "Yearly Cust"},
        ).json()
        plan_yearly = client.post(
            "/v1/plans/",
            json={
                "code": f"plan_yr_{uuid.uuid4().hex[:6]}",
                "name": "Yearly Plan",
                "interval": "yearly",
                "amount_cents": 12000,
            },
        ).json()
        plan_yearly_2 = client.post(
            "/v1/plans/",
            json={
                "code": f"plan_yr2_{uuid.uuid4().hex[:6]}",
                "name": "Yearly Plan 2",
                "interval": "yearly",
                "amount_cents": 24000,
            },
        ).json()
        started = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": f"sub_yr_{uuid.uuid4().hex[:6]}",
                "customer_id": customer["id"],
                "plan_id": plan_yearly["id"],
                "started_at": started,
            },
        ).json()
        response = client.post(
            f"/v1/subscriptions/{sub['id']}/change_plan_preview",
            json={"new_plan_id": plan_yearly_2["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["proration"]["total_days"] == 365

    def test_change_plan_preview_no_started_at(self, client: TestClient):
        """Test preview when subscription has no started_at (uses full period)."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": f"cust_ns_{uuid.uuid4().hex[:6]}", "name": "NoStart Cust"},
        ).json()
        plan_a = client.post(
            "/v1/plans/",
            json={
                "code": f"plan_ns_a_{uuid.uuid4().hex[:6]}",
                "name": "Plan A NoStart",
                "interval": "monthly",
                "amount_cents": 1000,
            },
        ).json()
        plan_b = client.post(
            "/v1/plans/",
            json={
                "code": f"plan_ns_b_{uuid.uuid4().hex[:6]}",
                "name": "Plan B NoStart",
                "interval": "monthly",
                "amount_cents": 3000,
            },
        ).json()
        # Create without started_at — pending subscription
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": f"sub_ns_{uuid.uuid4().hex[:6]}",
                "customer_id": customer["id"],
                "plan_id": plan_a["id"],
            },
        ).json()
        response = client.post(
            f"/v1/subscriptions/{sub['id']}/change_plan_preview",
            json={"new_plan_id": plan_b["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        # Should use created_at as anchor
        assert data["proration"]["total_days"] == 30

    def test_update_subscription_plan_id(self, client: TestClient):
        """Test that plan_id can be updated via the PUT endpoint."""
        setup = self._setup(client)
        response = client.put(
            f"/v1/subscriptions/{setup['sub']['id']}",
            json={
                "plan_id": setup["plan_b"]["id"],
                "previous_plan_id": setup["plan_a"]["id"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan_id"] == setup["plan_b"]["id"]
        assert data["previous_plan_id"] == setup["plan_a"]["id"]


class TestChangePlanPreviewSchemas:
    """Tests for the change plan preview Pydantic schemas."""

    def test_change_plan_preview_request_defaults(self):
        """Test ChangePlanPreviewRequest default values."""
        from app.schemas.subscription import ChangePlanPreviewRequest

        req = ChangePlanPreviewRequest(new_plan_id=uuid.uuid4())
        assert req.effective_date is None

    def test_change_plan_preview_request_with_date(self):
        """Test ChangePlanPreviewRequest with effective_date."""
        from app.schemas.subscription import ChangePlanPreviewRequest

        now = datetime.now(UTC)
        req = ChangePlanPreviewRequest(new_plan_id=uuid.uuid4(), effective_date=now)
        assert req.effective_date == now

    def test_plan_summary(self):
        """Test PlanSummary schema."""
        from app.schemas.subscription import PlanSummary

        ps = PlanSummary(
            id=uuid.uuid4(),
            name="Test Plan",
            code="test",
            interval="monthly",
            amount_cents=2000,
            currency="USD",
        )
        assert ps.name == "Test Plan"
        assert ps.amount_cents == 2000

    def test_proration_detail(self):
        """Test ProrationDetail schema."""
        from app.schemas.subscription import ProrationDetail

        pd = ProrationDetail(
            days_remaining=15,
            total_days=30,
            current_plan_credit_cents=1000,
            new_plan_charge_cents=2500,
            net_amount_cents=1500,
        )
        assert pd.days_remaining == 15
        assert pd.net_amount_cents == 1500

    def test_change_plan_preview_response(self):
        """Test ChangePlanPreviewResponse schema."""
        from app.schemas.subscription import (
            ChangePlanPreviewResponse,
            PlanSummary,
            ProrationDetail,
        )

        now = datetime.now(UTC)
        resp = ChangePlanPreviewResponse(
            current_plan=PlanSummary(
                id=uuid.uuid4(), name="A", code="a", interval="monthly",
                amount_cents=2000, currency="USD",
            ),
            new_plan=PlanSummary(
                id=uuid.uuid4(), name="B", code="b", interval="monthly",
                amount_cents=5000, currency="USD",
            ),
            effective_date=now,
            proration=ProrationDetail(
                days_remaining=20, total_days=30,
                current_plan_credit_cents=1333, new_plan_charge_cents=3333,
                net_amount_cents=2000,
            ),
        )
        assert resp.current_plan.name == "A"
        assert resp.new_plan.name == "B"
        assert resp.proration.net_amount_cents == 2000


class TestNextBillingDateSchema:
    def test_schema_fields(self):
        """Test NextBillingDateResponse schema."""
        from app.schemas.subscription import NextBillingDateResponse

        now = datetime.now(UTC)
        resp = NextBillingDateResponse(
            next_billing_date=now + timedelta(days=15),
            current_period_started_at=now - timedelta(days=15),
            interval="monthly",
            days_until_next_billing=15,
        )
        assert resp.interval == "monthly"
        assert resp.days_until_next_billing == 15


class TestNextBillingDateAPI:
    def test_next_billing_date_active_subscription(self, client: TestClient, db_session):
        """Test getting next billing date for an active subscription."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_nbd", "name": "NBD Customer"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "nbd_plan", "name": "NBD Plan", "interval": "monthly"},
        ).json()

        # Create subscription with started_at 10 days ago
        started_at = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_nbd",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
                "started_at": started_at,
            },
        ).json()

        # Set to active
        client.put(
            f"/v1/subscriptions/{sub['id']}",
            json={"status": "active"},
        )

        response = client.get(f"/v1/subscriptions/{sub['id']}/next_billing_date")
        assert response.status_code == 200
        data = response.json()
        assert "next_billing_date" in data
        assert "current_period_started_at" in data
        assert data["interval"] == "monthly"
        assert data["days_until_next_billing"] in (19, 20)

    def test_next_billing_date_pending_subscription(self, client: TestClient, db_session):
        """Test getting next billing date for a pending subscription (future start)."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_nbd_pend", "name": "NBD Pending"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "nbd_pend_plan", "name": "NBD Pending Plan", "interval": "weekly"},
        ).json()

        # Create pending subscription with future started_at
        started_at = (datetime.now(UTC) + timedelta(days=5)).isoformat()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_nbd_pend",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
                "started_at": started_at,
            },
        ).json()

        response = client.get(f"/v1/subscriptions/{sub['id']}/next_billing_date")
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "weekly"
        # For a future subscription, days_until should be around 5 (±1 for timing)
        assert 4 <= data["days_until_next_billing"] <= 5

    def test_next_billing_date_terminated_subscription(self, client: TestClient, db_session):
        """Test getting next billing date for a terminated subscription returns 400."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_nbd_term", "name": "NBD Terminated"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "nbd_term_plan", "name": "NBD Term Plan", "interval": "monthly"},
        ).json()

        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_nbd_term",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
            },
        ).json()

        # Set to active then terminate
        client.put(
            f"/v1/subscriptions/{sub['id']}",
            json={"status": "active"},
        )
        client.delete(f"/v1/subscriptions/{sub['id']}")

        response = client.get(f"/v1/subscriptions/{sub['id']}/next_billing_date")
        assert response.status_code == 400
        assert "terminated" in response.json()["detail"]

    def test_next_billing_date_paused_subscription(self, client: TestClient, db_session):
        """Test getting next billing date for a paused subscription returns 400."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_nbd_pause", "name": "NBD Paused"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "nbd_pause_plan", "name": "NBD Pause Plan", "interval": "monthly"},
        ).json()

        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_nbd_pause",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
            },
        ).json()

        # Set to active then pause
        client.put(
            f"/v1/subscriptions/{sub['id']}",
            json={"status": "active"},
        )
        client.post(f"/v1/subscriptions/{sub['id']}/pause")

        response = client.get(f"/v1/subscriptions/{sub['id']}/next_billing_date")
        assert response.status_code == 400
        assert "paused" in response.json()["detail"]

    def test_next_billing_date_not_found(self, client: TestClient):
        """Test getting next billing date for a non-existent subscription."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/subscriptions/{fake_id}/next_billing_date")
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_next_billing_date_yearly_interval(self, client: TestClient, db_session):
        """Test next billing date with yearly interval."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_nbd_yr", "name": "NBD Yearly"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "nbd_yr_plan", "name": "NBD Yearly Plan", "interval": "yearly"},
        ).json()

        started_at = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_nbd_yr",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
                "started_at": started_at,
            },
        ).json()

        client.put(
            f"/v1/subscriptions/{sub['id']}",
            json={"status": "active"},
        )

        response = client.get(f"/v1/subscriptions/{sub['id']}/next_billing_date")
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "yearly"
        assert data["days_until_next_billing"] in (264, 265)

    def test_next_billing_date_quarterly_interval(self, client: TestClient, db_session):
        """Test next billing date with quarterly interval."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_nbd_qt", "name": "NBD Quarterly"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "nbd_qt_plan", "name": "NBD Quarterly Plan", "interval": "quarterly"},
        ).json()

        started_at = (datetime.now(UTC) - timedelta(days=20)).isoformat()
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_nbd_qt",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
                "started_at": started_at,
            },
        ).json()

        client.put(
            f"/v1/subscriptions/{sub['id']}",
            json={"status": "active"},
        )

        response = client.get(f"/v1/subscriptions/{sub['id']}/next_billing_date")
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "quarterly"
        assert data["days_until_next_billing"] in (69, 70)

    def test_next_billing_date_no_started_at_uses_created_at(self, client: TestClient, db_session):
        """Test next billing date falls back to created_at when started_at is null."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_nbd_fb", "name": "NBD Fallback"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "nbd_fb_plan", "name": "NBD Fallback Plan", "interval": "monthly"},
        ).json()

        # Create without started_at - pending status still allows calculation
        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_nbd_fb",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
            },
        ).json()

        response = client.get(f"/v1/subscriptions/{sub['id']}/next_billing_date")
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "monthly"
        # created_at is just now, so next billing should be ~30 days away
        assert 29 <= data["days_until_next_billing"] <= 30

    def test_next_billing_date_canceled_subscription(self, client: TestClient, db_session):
        """Test getting next billing date for a canceled subscription returns 400."""
        customer = client.post(
            "/v1/customers/",
            json={"external_id": "cust_nbd_cancel", "name": "NBD Canceled"},
        ).json()
        plan = client.post(
            "/v1/plans/",
            json={"code": "nbd_cancel_plan", "name": "NBD Cancel Plan", "interval": "monthly"},
        ).json()

        sub = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": "sub_nbd_cancel",
                "customer_id": customer["id"],
                "plan_id": plan["id"],
            },
        ).json()

        client.put(
            f"/v1/subscriptions/{sub['id']}",
            json={"status": "active"},
        )
        client.post(f"/v1/subscriptions/{sub['id']}/cancel")

        response = client.get(f"/v1/subscriptions/{sub['id']}/next_billing_date")
        assert response.status_code == 400
        assert "canceled" in response.json()["detail"]

    def test_next_billing_date_naive_started_at(self, client: TestClient, db_session):
        """Test next billing date with a naive (no timezone) started_at."""
        customer = create_test_customer(db_session, "cust_nbd_naive")
        plan = create_test_plan(db_session, "nbd_naive_plan")

        # Create subscription with naive datetime directly in DB
        sub = Subscription(
            external_id="sub_nbd_naive",
            customer_id=customer.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            started_at=datetime(2025, 1, 1, 0, 0, 0),  # naive
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        response = client.get(f"/v1/subscriptions/{sub.id}/next_billing_date")
        assert response.status_code == 200
        data = response.json()
        assert data["interval"] == "monthly"
        assert data["days_until_next_billing"] >= 0
