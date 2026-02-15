"""Tests for usage alerts router, worker task, and event ingestion wiring."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core import database as db_module
from app.core.database import get_db
from app.main import app
from app.models.billable_metric import AggregationType, BillableMetric
from app.models.customer import Customer
from app.models.event import Event
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.usage_alert_trigger import UsageAlertTrigger  # noqa: F401 — register model
from app.repositories.usage_alert_repository import UsageAlertRepository
from app.repositories.usage_alert_trigger_repository import UsageAlertTriggerRepository
from app.routers.events import _enqueue_alert_checks
from app.schemas.usage_alert import UsageAlertCreate
from app.tasks import enqueue_check_usage_alerts
from app.worker import WorkerSettings, check_usage_alerts_task
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def client():
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


@pytest.fixture
def metric(db_session):
    m = BillableMetric(
        code=f"ua_rt_metric_{uuid.uuid4()}",
        name="Alert Router Metric",
        aggregation_type=AggregationType.COUNT.value,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def customer(db_session):
    c = Customer(
        external_id=f"ua_rt_cust_{uuid.uuid4()}",
        name="Alert Router Customer",
        email="alert_router@example.com",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def plan(db_session):
    p = Plan(
        code=f"ua_rt_plan_{uuid.uuid4()}",
        name="Alert Router Plan",
        interval=PlanInterval.MONTHLY.value,
        amount_cents=10000,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def subscription(db_session, customer, plan):
    sub = Subscription(
        external_id=f"ua_rt_sub_{uuid.uuid4()}",
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        started_at=datetime.now(UTC) - timedelta(days=30),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def alert(db_session, subscription, metric):
    repo = UsageAlertRepository(db_session)
    return repo.create(
        UsageAlertCreate(
            subscription_id=subscription.id,
            billable_metric_id=metric.id,
            threshold_value=Decimal("100"),
            name="Test Alert",
        ),
        DEFAULT_ORG_ID,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CRUD Router Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUsageAlertsAPI:
    """Tests for usage alerts CRUD endpoints."""

    def test_list_empty(self, client):
        """Test listing usage alerts when none exist."""
        response = client.get("/v1/usage_alerts/")
        assert response.status_code == 200
        assert response.json() == []
        assert response.headers["X-Total-Count"] == "0"

    def test_create_alert(self, client, subscription, metric):
        """Test creating a usage alert."""
        response = client.post(
            "/v1/usage_alerts/",
            json={
                "subscription_id": str(subscription.id),
                "billable_metric_id": str(metric.id),
                "threshold_value": "100",
                "name": "API calls alert",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subscription_id"] == str(subscription.id)
        assert data["billable_metric_id"] == str(metric.id)
        assert Decimal(data["threshold_value"]) == Decimal("100")
        assert data["name"] == "API calls alert"
        assert data["recurring"] is False
        assert data["times_triggered"] == 0
        assert data["triggered_at"] is None
        assert "id" in data

    def test_create_alert_recurring(self, client, subscription, metric):
        """Test creating a recurring usage alert."""
        response = client.post(
            "/v1/usage_alerts/",
            json={
                "subscription_id": str(subscription.id),
                "billable_metric_id": str(metric.id),
                "threshold_value": "50",
                "recurring": True,
                "name": "Every 50 calls",
            },
        )
        assert response.status_code == 201
        assert response.json()["recurring"] is True

    def test_create_alert_subscription_not_found(self, client, metric):
        """Test creating alert with non-existent subscription."""
        response = client.post(
            "/v1/usage_alerts/",
            json={
                "subscription_id": str(uuid.uuid4()),
                "billable_metric_id": str(metric.id),
                "threshold_value": "100",
            },
        )
        assert response.status_code == 404
        assert "Subscription not found" in response.json()["detail"]

    def test_create_alert_metric_not_found(self, client, subscription):
        """Test creating alert with non-existent metric."""
        response = client.post(
            "/v1/usage_alerts/",
            json={
                "subscription_id": str(subscription.id),
                "billable_metric_id": str(uuid.uuid4()),
                "threshold_value": "100",
            },
        )
        assert response.status_code == 404
        assert "Billable metric not found" in response.json()["detail"]

    def test_create_alert_invalid_threshold(self, client, subscription, metric):
        """Test creating alert with zero threshold."""
        response = client.post(
            "/v1/usage_alerts/",
            json={
                "subscription_id": str(subscription.id),
                "billable_metric_id": str(metric.id),
                "threshold_value": "0",
            },
        )
        assert response.status_code == 422

    def test_get_alert(self, client, alert):
        """Test getting a usage alert by ID."""
        response = client.get(f"/v1/usage_alerts/{alert.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(alert.id)
        assert data["name"] == "Test Alert"

    def test_get_alert_not_found(self, client):
        """Test getting a non-existent usage alert."""
        response = client.get(f"/v1/usage_alerts/{uuid.uuid4()}")
        assert response.status_code == 404
        assert "Usage alert not found" in response.json()["detail"]

    def test_list_alerts(self, client, alert):
        """Test listing alerts returns created alert."""
        response = client.get("/v1/usage_alerts/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(alert.id)
        assert response.headers["X-Total-Count"] == "1"

    def test_list_alerts_filter_by_subscription(
        self, client, db_session, subscription, metric
    ):
        """Test filtering alerts by subscription_id."""
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )

        # Filter by subscription_id
        response = client.get(
            f"/v1/usage_alerts/?subscription_id={subscription.id}"
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.headers["X-Total-Count"] == "1"

        # Filter with non-existent subscription
        response = client.get(
            f"/v1/usage_alerts/?subscription_id={uuid.uuid4()}"
        )
        assert response.status_code == 200
        assert len(response.json()) == 0
        assert response.headers["X-Total-Count"] == "0"

    def test_list_alerts_pagination(self, client, db_session, subscription, metric):
        """Test listing alerts with pagination."""
        repo = UsageAlertRepository(db_session)
        for i in range(5):
            repo.create(
                UsageAlertCreate(
                    subscription_id=subscription.id,
                    billable_metric_id=metric.id,
                    threshold_value=Decimal(str((i + 1) * 100)),
                ),
                DEFAULT_ORG_ID,
            )

        response = client.get("/v1/usage_alerts/?skip=2&limit=2")
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.headers["X-Total-Count"] == "5"

    def test_update_alert(self, client, alert):
        """Test updating a usage alert."""
        response = client.patch(
            f"/v1/usage_alerts/{alert.id}",
            json={"threshold_value": "200", "name": "Updated Alert"},
        )
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["threshold_value"]) == Decimal("200")
        assert data["name"] == "Updated Alert"

    def test_update_alert_partial(self, client, alert):
        """Test partial update of a usage alert."""
        response = client.patch(
            f"/v1/usage_alerts/{alert.id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        # Threshold should remain the same
        assert Decimal(data["threshold_value"]) == Decimal("100")

    def test_update_alert_recurring(self, client, alert):
        """Test updating recurring flag."""
        response = client.patch(
            f"/v1/usage_alerts/{alert.id}",
            json={"recurring": True},
        )
        assert response.status_code == 200
        assert response.json()["recurring"] is True

    def test_update_alert_not_found(self, client):
        """Test updating a non-existent usage alert."""
        response = client.patch(
            f"/v1/usage_alerts/{uuid.uuid4()}",
            json={"name": "nope"},
        )
        assert response.status_code == 404
        assert "Usage alert not found" in response.json()["detail"]

    def test_delete_alert(self, client, alert):
        """Test deleting a usage alert."""
        response = client.delete(f"/v1/usage_alerts/{alert.id}")
        assert response.status_code == 204

        # Verify it's gone
        response = client.get(f"/v1/usage_alerts/{alert.id}")
        assert response.status_code == 404

    def test_delete_alert_not_found(self, client):
        """Test deleting a non-existent usage alert."""
        response = client.delete(f"/v1/usage_alerts/{uuid.uuid4()}")
        assert response.status_code == 404
        assert "Usage alert not found" in response.json()["detail"]

    def test_create_alert_idempotency(self, client, subscription, metric):
        """Test idempotent creation records and returns cached response."""
        idem_key = f"idem-alert-{uuid.uuid4()}"
        body = {
            "subscription_id": str(subscription.id),
            "billable_metric_id": str(metric.id),
            "threshold_value": "100",
            "name": "Idempotent Alert",
        }

        # First request with Idempotency-Key
        resp1 = client.post(
            "/v1/usage_alerts/",
            json=body,
            headers={"Idempotency-Key": idem_key},
        )
        assert resp1.status_code == 201
        data1 = resp1.json()

        # Second request with same key returns cached response
        resp2 = client.post(
            "/v1/usage_alerts/",
            json=body,
            headers={"Idempotency-Key": idem_key},
        )
        assert resp2.status_code == 201
        assert resp2.json()["id"] == data1["id"]


# ─────────────────────────────────────────────────────────────────────────────
# Status / Triggers / Test Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUsageAlertStatusEndpoint:
    """Tests for GET /v1/usage_alerts/{id}/status."""

    def test_get_status(self, client, db_session, alert, customer, metric):
        """Test getting alert status returns current usage info."""
        # Create some events so there's usage
        billing_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0)
        for i in range(10):
            event = Event(
                transaction_id=f"ua_status_tx_{uuid.uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=billing_start + timedelta(hours=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        response = client.get(f"/v1/usage_alerts/{alert.id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["alert_id"] == str(alert.id)
        assert "current_usage" in data
        assert "threshold_value" in data
        assert "usage_percentage" in data
        assert "billing_period_start" in data
        assert "billing_period_end" in data

    def test_get_status_not_found(self, client):
        """Test status endpoint with non-existent alert."""
        response = client.get(f"/v1/usage_alerts/{uuid.uuid4()}/status")
        assert response.status_code == 404


class TestUsageAlertTriggersEndpoint:
    """Tests for GET /v1/usage_alerts/{id}/triggers."""

    def test_list_triggers_empty(self, client, alert):
        """Test listing triggers when none exist."""
        response = client.get(f"/v1/usage_alerts/{alert.id}/triggers")
        assert response.status_code == 200
        assert response.json() == []
        assert response.headers["X-Total-Count"] == "0"

    def test_list_triggers_with_data(self, client, db_session, alert, metric):
        """Test listing triggers returns trigger records."""
        trigger_repo = UsageAlertTriggerRepository(db_session)
        now = datetime.now(UTC)
        trigger_repo.create(
            usage_alert_id=alert.id,
            current_usage=Decimal("150"),
            threshold_value=Decimal("100"),
            metric_code=str(metric.code),
            triggered_at=now,
        )

        response = client.get(f"/v1/usage_alerts/{alert.id}/triggers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["usage_alert_id"] == str(alert.id)
        assert Decimal(data[0]["current_usage"]) == Decimal("150")
        assert data[0]["metric_code"] == str(metric.code)
        assert response.headers["X-Total-Count"] == "1"

    def test_list_triggers_not_found(self, client):
        """Test triggers endpoint with non-existent alert."""
        response = client.get(f"/v1/usage_alerts/{uuid.uuid4()}/triggers")
        assert response.status_code == 404

    def test_list_triggers_pagination(self, client, db_session, alert, metric):
        """Test listing triggers with pagination."""
        trigger_repo = UsageAlertTriggerRepository(db_session)
        now = datetime.now(UTC)
        for i in range(5):
            trigger_repo.create(
                usage_alert_id=alert.id,
                current_usage=Decimal(str((i + 1) * 100)),
                threshold_value=Decimal("100"),
                metric_code=str(metric.code),
                triggered_at=now - timedelta(hours=5 - i),
            )

        response = client.get(f"/v1/usage_alerts/{alert.id}/triggers?skip=2&limit=2")
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.headers["X-Total-Count"] == "5"


class TestUsageAlertTestEndpoint:
    """Tests for POST /v1/usage_alerts/{id}/test."""

    def test_test_alert(self, client, db_session, alert, customer, metric):
        """Test the test alert endpoint returns usage status."""
        billing_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0)
        for i in range(10):
            event = Event(
                transaction_id=f"ua_test_tx_{uuid.uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=billing_start + timedelta(hours=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        response = client.post(f"/v1/usage_alerts/{alert.id}/test")
        assert response.status_code == 200
        data = response.json()
        assert data["alert_id"] == str(alert.id)
        assert "current_usage" in data
        assert "usage_percentage" in data

    def test_test_alert_not_found(self, client):
        """Test test endpoint with non-existent alert."""
        response = client.post(f"/v1/usage_alerts/{uuid.uuid4()}/test")
        assert response.status_code == 404


class TestResolveBillingPeriodErrors:
    """Tests for _resolve_billing_period error cases."""

    def _make_alert_with_entities(self, db_session, metric):
        """Create customer, plan, subscription, and alert for error testing."""
        repo = UsageAlertRepository(db_session)
        c = Customer(
            external_id=f"ua_rbp_cust_{uuid.uuid4()}",
            name="RBP Cust",
            email="rbp@example.com",
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)

        p = Plan(
            code=f"ua_rbp_plan_{uuid.uuid4()}",
            name="RBP Plan",
            interval=PlanInterval.MONTHLY.value,
            amount_cents=1000,
        )
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)

        sub = Subscription(
            external_id=f"ua_rbp_sub_{uuid.uuid4()}",
            customer_id=c.id,
            plan_id=p.id,
            status=SubscriptionStatus.ACTIVE.value,
            started_at=datetime.now(UTC) - timedelta(days=5),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        alert = repo.create(
            UsageAlertCreate(
                subscription_id=sub.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )
        return c, p, sub, alert

    def test_status_subscription_not_found(self, client, db_session, metric):
        """Test status when subscription is deleted."""
        _, _, sub, alert = self._make_alert_with_entities(db_session, metric)

        db_session.delete(sub)
        db_session.commit()

        response = client.get(f"/v1/usage_alerts/{alert.id}/status")
        assert response.status_code == 404
        assert "Subscription not found" in response.json()["detail"]

    def test_status_plan_not_found(self, client, db_session, metric):
        """Test status when plan is deleted."""
        _, p, _, alert = self._make_alert_with_entities(db_session, metric)

        db_session.delete(p)
        db_session.commit()

        response = client.get(f"/v1/usage_alerts/{alert.id}/status")
        assert response.status_code == 404
        assert "Plan not found" in response.json()["detail"]

    def test_status_customer_not_found(self, client, db_session, metric):
        """Test status when customer is deleted."""
        c, _, _, alert = self._make_alert_with_entities(db_session, metric)

        db_session.delete(c)
        db_session.commit()

        response = client.get(f"/v1/usage_alerts/{alert.id}/status")
        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# Repository subscription_id filter Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUsageAlertRepositoryFilter:
    """Tests for the subscription_id filter on get_all and count."""

    def test_get_all_with_subscription_filter(self, db_session, subscription, metric):
        """Test get_all filters by subscription_id."""
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )
        assert len(repo.get_all(DEFAULT_ORG_ID, subscription_id=subscription.id)) == 1
        assert len(repo.get_all(DEFAULT_ORG_ID, subscription_id=uuid.uuid4())) == 0

    def test_count_with_subscription_filter(self, db_session, subscription, metric):
        """Test count filters by subscription_id."""
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )
        assert repo.count(DEFAULT_ORG_ID, subscription_id=subscription.id) == 1
        assert repo.count(DEFAULT_ORG_ID, subscription_id=uuid.uuid4()) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Event Ingestion Wiring Tests
# ─────────────────────────────────────────────────────────────────────────────


def _create_customer(db, external_id: str) -> Customer:
    c = Customer(external_id=external_id, name="Test", email="t@t.com")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _create_plan(db, code: str) -> Plan:
    p = Plan(
        code=code,
        name=f"Plan {code}",
        interval=PlanInterval.MONTHLY.value,
        amount_cents=10000,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _create_active_subscription(
    db, customer: Customer, plan: Plan, external_id: str
) -> Subscription:
    sub = Subscription(
        external_id=external_id,
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        started_at=datetime.now(UTC) - timedelta(days=5),
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


class TestEventAlertEnqueueing:
    """Tests for alert check task enqueueing on event ingestion."""

    @pytest.fixture(autouse=True)
    def _reset_rate_limiter(self):
        """Reset the event rate limiter before and after each test."""
        from app.core.config import settings
        from app.routers.events import event_rate_limiter

        event_rate_limiter.reset()
        original = event_rate_limiter.max_requests
        event_rate_limiter.max_requests = settings.RATE_LIMIT_EVENTS_PER_MINUTE
        yield
        event_rate_limiter.max_requests = original
        event_rate_limiter.reset()

    @pytest.fixture
    def billable_metric(self, db_session):
        code = f"ua_alert_calls_{uuid.uuid4().hex[:8]}"
        m = BillableMetric(
            code=code,
            name="API Calls For Alert Tests",
            aggregation_type=AggregationType.COUNT.value,
        )
        db_session.add(m)
        db_session.commit()
        db_session.refresh(m)
        return m

    def test_create_event_enqueues_alert_check(
        self, client, db_session, billable_metric
    ):
        """Test single event ingestion enqueues alert checks."""
        cust = _create_customer(db_session, f"cust-alert-enq-{uuid.uuid4().hex[:8]}")
        plan = _create_plan(db_session, f"plan-alert-enq-{uuid.uuid4().hex[:8]}")
        sub = _create_active_subscription(
            db_session, cust, plan, f"sub-alert-enq-{uuid.uuid4().hex[:8]}"
        )

        with patch(
            "app.routers.events.enqueue_check_usage_alerts",
            new_callable=AsyncMock,
        ) as mock_alert_enqueue, patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ):
            response = client.post(
                "/v1/events/",
                json={
                    "transaction_id": f"tx-alert-enq-{uuid.uuid4()}",
                    "external_customer_id": str(cust.external_id),
                    "code": str(billable_metric.code),
                    "timestamp": "2026-01-15T10:30:00Z",
                },
            )

        assert response.status_code == 201
        mock_alert_enqueue.assert_called_once_with(str(sub.id))

    def test_create_event_no_alert_enqueue_for_duplicate(
        self, client, db_session, billable_metric
    ):
        """Test duplicate event does not enqueue alert checks."""
        cust = _create_customer(db_session, f"cust-alert-dup-{uuid.uuid4().hex[:8]}")
        plan = _create_plan(db_session, f"plan-alert-dup-{uuid.uuid4().hex[:8]}")
        _create_active_subscription(
            db_session, cust, plan, f"sub-alert-dup-{uuid.uuid4().hex[:8]}"
        )
        tx_id = f"tx-alert-dup-{uuid.uuid4()}"

        # Create first event (with mocks to avoid Redis)
        with patch(
            "app.routers.events.enqueue_check_usage_alerts",
            new_callable=AsyncMock,
        ), patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ):
            client.post(
                "/v1/events/",
                json={
                    "transaction_id": tx_id,
                    "external_customer_id": str(cust.external_id),
                    "code": str(billable_metric.code),
                    "timestamp": "2026-01-15T10:30:00Z",
                },
            )

        # Send duplicate
        with patch(
            "app.routers.events.enqueue_check_usage_alerts",
            new_callable=AsyncMock,
        ) as mock_alert_enqueue, patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ):
            response = client.post(
                "/v1/events/",
                json={
                    "transaction_id": tx_id,
                    "external_customer_id": str(cust.external_id),
                    "code": str(billable_metric.code),
                    "timestamp": "2026-01-15T10:30:00Z",
                },
            )

        assert response.status_code == 201
        mock_alert_enqueue.assert_not_called()

    def test_batch_create_enqueues_alert_checks(
        self, client, db_session, billable_metric
    ):
        """Test batch event ingestion enqueues alert checks."""
        cust = _create_customer(
            db_session, f"cust-alert-batch-{uuid.uuid4().hex[:8]}"
        )
        plan = _create_plan(db_session, f"plan-alert-batch-{uuid.uuid4().hex[:8]}")
        sub = _create_active_subscription(
            db_session, cust, plan, f"sub-alert-batch-{uuid.uuid4().hex[:8]}"
        )

        with patch(
            "app.routers.events.enqueue_check_usage_alerts",
            new_callable=AsyncMock,
        ) as mock_alert_enqueue, patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ):
            response = client.post(
                "/v1/events/batch",
                json={
                    "events": [
                        {
                            "transaction_id": f"tx-alert-batch-{uuid.uuid4()}",
                            "external_customer_id": str(cust.external_id),
                            "code": str(billable_metric.code),
                            "timestamp": "2026-01-15T10:00:00Z",
                        },
                    ]
                },
            )

        assert response.status_code == 201
        mock_alert_enqueue.assert_called_once_with(str(sub.id))

    def test_create_event_no_alert_enqueue_without_customer(
        self, client, billable_metric
    ):
        """Test no alert check when customer doesn't exist."""
        with patch(
            "app.routers.events.enqueue_check_usage_alerts",
            new_callable=AsyncMock,
        ) as mock_alert_enqueue, patch(
            "app.routers.events.enqueue_check_usage_thresholds",
            new_callable=AsyncMock,
        ):
            response = client.post(
                "/v1/events/",
                json={
                    "transaction_id": f"tx-alert-nocust-{uuid.uuid4()}",
                    "external_customer_id": f"nonexistent-{uuid.uuid4().hex[:8]}",
                    "code": str(billable_metric.code),
                    "timestamp": "2026-01-15T10:30:00Z",
                },
            )

        assert response.status_code == 201
        mock_alert_enqueue.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# _enqueue_alert_checks helper Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEnqueueAlertChecks:
    """Tests for _enqueue_alert_checks helper."""

    @pytest.mark.asyncio
    async def test_enqueues_for_each_subscription(self):
        """Test enqueues a task for each subscription ID."""
        sub_ids = ["sub-a1", "sub-a2"]
        with patch(
            "app.routers.events.enqueue_check_usage_alerts",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            await _enqueue_alert_checks(sub_ids)

        assert mock_enqueue.call_count == 2
        mock_enqueue.assert_any_call("sub-a1")
        mock_enqueue.assert_any_call("sub-a2")

    @pytest.mark.asyncio
    async def test_continues_on_error(self):
        """Test continues processing if one enqueue fails."""
        sub_ids = ["sub-fail-a", "sub-ok-a"]
        with patch(
            "app.routers.events.enqueue_check_usage_alerts",
            new_callable=AsyncMock,
        ) as mock_enqueue:
            mock_enqueue.side_effect = [Exception("Redis error"), None]
            await _enqueue_alert_checks(sub_ids)

        assert mock_enqueue.call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# Task enqueue function Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEnqueueCheckUsageAlertsTask:
    """Tests for enqueue_check_usage_alerts in tasks.py."""

    @pytest.mark.asyncio
    async def test_enqueue_check_usage_alerts(self):
        """Test enqueue_check_usage_alerts helper function."""
        mock_job = MagicMock()
        mock_job.job_id = "alerts-job-001"

        with patch("app.tasks.enqueue_task", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_job
            result = await enqueue_check_usage_alerts("sub-uuid-123")

        assert result == mock_job
        mock_enqueue.assert_called_once_with("check_usage_alerts_task", "sub-uuid-123")


# ─────────────────────────────────────────────────────────────────────────────
# Worker task Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckUsageAlertsTask:
    """Tests for the check_usage_alerts_task worker function."""

    @pytest.mark.asyncio
    async def test_returns_zero_when_subscription_not_found(self, db_session):
        """Test returns 0 when subscription doesn't exist."""
        fake_id = str(uuid.uuid4())
        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await check_usage_alerts_task({}, fake_id)
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_for_inactive_subscription(self, db_session):
        """Test returns 0 for a canceled subscription."""
        cust = _create_customer(db_session, f"cust_alert_inactive_{uuid.uuid4()}")
        plan = _create_plan(db_session, f"plan_alert_inactive_{uuid.uuid4()}")
        sub = Subscription(
            external_id=f"sub_alert_inactive_{uuid.uuid4()}",
            customer_id=cust.id,
            plan_id=plan.id,
            status=SubscriptionStatus.CANCELED.value,
            started_at=datetime.now(UTC) - timedelta(days=5),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        with patch("app.worker.SessionLocal", db_module.SessionLocal):
            result = await check_usage_alerts_task({}, str(sub.id))
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_plan_not_found(self, db_session):
        """Test returns 0 when the plan doesn't exist."""
        cust = _create_customer(db_session, f"cust_alert_noplan_{uuid.uuid4()}")
        plan = _create_plan(db_session, f"plan_alert_noplan_{uuid.uuid4()}")
        sub = _create_active_subscription(
            db_session, cust, plan, f"sub_alert_noplan_{uuid.uuid4()}"
        )

        mock_plan_repo = MagicMock()
        mock_plan_repo.get_by_id.return_value = None

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.PlanRepository", return_value=mock_plan_repo),
        ):
            result = await check_usage_alerts_task({}, str(sub.id))
        assert result == 0

    @pytest.mark.asyncio
    async def test_returns_zero_when_customer_not_found(self, db_session):
        """Test returns 0 when the customer doesn't exist."""
        cust = _create_customer(db_session, f"cust_alert_nocust_{uuid.uuid4()}")
        plan = _create_plan(db_session, f"plan_alert_nocust_{uuid.uuid4()}")
        sub = _create_active_subscription(
            db_session, cust, plan, f"sub_alert_nocust_{uuid.uuid4()}"
        )

        mock_cust_repo = MagicMock()
        mock_cust_repo.get_by_id.return_value = None

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.CustomerRepository", return_value=mock_cust_repo),
        ):
            result = await check_usage_alerts_task({}, str(sub.id))
        assert result == 0

    @pytest.mark.asyncio
    async def test_calls_check_alerts_and_returns_count(self, db_session):
        """Test calls UsageAlertService.check_alerts and returns triggered count."""
        cust = _create_customer(db_session, f"cust_alert_ok_{uuid.uuid4()}")
        plan = _create_plan(db_session, f"plan_alert_ok_{uuid.uuid4()}")
        sub = _create_active_subscription(
            db_session, cust, plan, f"sub_alert_ok_{uuid.uuid4()}"
        )

        mock_service = MagicMock()
        mock_service.check_alerts.return_value = [MagicMock(), MagicMock()]

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.UsageAlertService", return_value=mock_service),
        ):
            result = await check_usage_alerts_task({}, str(sub.id))

        assert result == 2
        mock_service.check_alerts.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_alerts_triggered(self, db_session):
        """Test returns 0 when no alerts are triggered."""
        cust = _create_customer(db_session, f"cust_alert_none_{uuid.uuid4()}")
        plan = _create_plan(db_session, f"plan_alert_none_{uuid.uuid4()}")
        sub = _create_active_subscription(
            db_session, cust, plan, f"sub_alert_none_{uuid.uuid4()}"
        )

        mock_service = MagicMock()
        mock_service.check_alerts.return_value = []

        with (
            patch("app.worker.SessionLocal", db_module.SessionLocal),
            patch("app.worker.UsageAlertService", return_value=mock_service),
        ):
            result = await check_usage_alerts_task({}, str(sub.id))

        assert result == 0

    @pytest.mark.asyncio
    async def test_closes_session_on_exception(self, db_session):
        """Test that DB session is closed even when an exception occurs."""
        mock_db = MagicMock()
        mock_db.close = MagicMock()

        mock_sub_repo = MagicMock()
        mock_sub_repo.get_by_id.side_effect = RuntimeError("DB error")

        with (
            patch("app.worker.SessionLocal", return_value=mock_db),
            patch("app.worker.SubscriptionRepository", return_value=mock_sub_repo),
            pytest.raises(RuntimeError, match="DB error"),
        ):
            await check_usage_alerts_task({}, str(uuid.uuid4()))

        mock_db.close.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# WorkerSettings registration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestWorkerSettingsAlerts:
    """Tests for check_usage_alerts_task registration in WorkerSettings."""

    def test_functions_includes_alerts_task(self):
        """Test that check_usage_alerts_task is registered as a worker function."""
        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "check_usage_alerts_task" in func_names
