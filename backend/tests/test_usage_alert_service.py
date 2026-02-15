"""Tests for UsageAlertService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import get_db
from app.models.billable_metric import AggregationType, BillableMetric
from app.models.customer import Customer
from app.models.event import Event
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.usage_alert_trigger import UsageAlertTrigger  # noqa: F401 — register model
from app.repositories.usage_alert_repository import UsageAlertRepository
from app.repositories.usage_alert_trigger_repository import UsageAlertTriggerRepository
from app.schemas.usage_alert import (
    UsageAlertCreate,
    UsageAlertResponse,
    UsageAlertStatusResponse,
    UsageAlertTriggerResponse,
    UsageAlertUpdate,
)
from app.services.usage_alert_service import UsageAlertService
from app.services.webhook_service import WEBHOOK_EVENT_TYPES
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
def customer(db_session):
    c = Customer(
        external_id=f"ua_cust_{uuid4()}",
        name="Alert Test Customer",
        email="alert@example.com",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def metric(db_session):
    m = BillableMetric(
        code=f"ua_api_calls_{uuid4()}",
        name="API Calls",
        aggregation_type=AggregationType.COUNT.value,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def sum_metric(db_session):
    m = BillableMetric(
        code=f"ua_data_transfer_{uuid4()}",
        name="Data Transfer",
        aggregation_type=AggregationType.SUM.value,
        field_name="bytes",
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def subscription(db_session, customer):
    from app.models.plan import Plan, PlanInterval

    p = Plan(
        code=f"ua_plan_{uuid4()}",
        name="Alert Test Plan",
        interval=PlanInterval.MONTHLY.value,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    sub = Subscription(
        external_id=f"ua_sub_{uuid4()}",
        customer_id=p.id,
        plan_id=p.id,
        status=SubscriptionStatus.ACTIVE.value,
        started_at=datetime.now(UTC) - timedelta(days=30),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def billing_period():
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


# ─────────────────────────────────────────────────────────────────────────────
# check_alerts Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckAlerts:
    """Tests for UsageAlertService.check_alerts."""

    def test_no_alerts_returns_empty(
        self, db_session, subscription, customer, billing_period
    ):
        """No alerts configured should return empty list."""
        start, end = billing_period
        service = UsageAlertService(db_session)
        result = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert result == []

    def test_single_threshold_crossing(
        self, db_session, subscription, customer, metric, billing_period
    ):
        """Alert should fire when usage crosses the threshold."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        alert = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("50"),
                name="50 API calls alert",
            ),
            DEFAULT_ORG_ID,
        )

        # Create 100 events (above 50 threshold)
        for i in range(100):
            event = Event(
                transaction_id=f"ua_tx_single_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageAlertService(db_session)
        result = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert len(result) == 1
        assert result[0].id == alert.id
        assert result[0].times_triggered == 1
        assert result[0].triggered_at is not None

    def test_already_triggered_alert_not_re_firing(
        self, db_session, subscription, customer, metric, billing_period
    ):
        """Non-recurring alert already triggered should not fire again."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("50"),
                recurring=False,
            ),
            DEFAULT_ORG_ID,
        )

        # Create 100 events
        for i in range(100):
            event = Event(
                transaction_id=f"ua_tx_norepeat_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageAlertService(db_session)
        # First check: fires
        result1 = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert len(result1) == 1

        # Second check: should NOT fire again
        result2 = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert result2 == []

    def test_recurring_threshold_fires_at_multiples(
        self, db_session, subscription, customer, metric, billing_period
    ):
        """Recurring alert should fire at each multiple of threshold (100, 200, 300)."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
                recurring=True,
                name="Every 100 calls",
            ),
            DEFAULT_ORG_ID,
        )

        # Create 150 events (crosses 100 threshold once)
        for i in range(150):
            event = Event(
                transaction_id=f"ua_tx_recur1_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageAlertService(db_session)
        result1 = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert len(result1) == 1
        assert result1[0].times_triggered == 1

        # Add more events to reach 350 (crosses 200 and 300)
        for i in range(200):
            event = Event(
                transaction_id=f"ua_tx_recur2_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i + 200),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        result2 = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert len(result2) == 1
        # 350 // 100 = 3 expected triggers, was 1, so fires again
        assert result2[0].times_triggered == 3

    def test_recurring_threshold_no_fire_when_same_multiple(
        self, db_session, subscription, customer, metric, billing_period
    ):
        """Recurring alert should not fire if still at same multiple."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
                recurring=True,
            ),
            DEFAULT_ORG_ID,
        )

        # Create 150 events (crosses 100 once)
        for i in range(150):
            event = Event(
                transaction_id=f"ua_tx_recur_same_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageAlertService(db_session)
        result1 = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert len(result1) == 1

        # Check again with same usage (still at 150, same multiple of 100)
        result2 = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert result2 == []

    def test_below_threshold_not_triggered(
        self, db_session, subscription, customer, metric, billing_period
    ):
        """Usage below threshold should not trigger the alert."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("200"),
            ),
            DEFAULT_ORG_ID,
        )

        # Create 50 events (below 200 threshold)
        for i in range(50):
            event = Event(
                transaction_id=f"ua_tx_below_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageAlertService(db_session)
        result = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert result == []

    def test_missing_metric_skipped(
        self, db_session, subscription, customer, billing_period
    ):
        """Alert with a non-existent metric should be skipped."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=uuid4(),
                threshold_value=Decimal("10"),
            ),
            DEFAULT_ORG_ID,
        )

        service = UsageAlertService(db_session)
        result = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert result == []

    def test_webhook_sent_on_trigger(
        self, db_session, subscription, customer, metric, billing_period
    ):
        """Verify that a webhook record is created when an alert fires."""
        from app.models.webhook import Webhook
        from app.models.webhook_endpoint import WebhookEndpoint

        start, end = billing_period
        # Create a webhook endpoint to receive events
        endpoint = WebhookEndpoint(
            url="https://example.com/webhook",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(endpoint)
        db_session.commit()

        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("10"),
            ),
            DEFAULT_ORG_ID,
        )

        # Create 20 events
        for i in range(20):
            event = Event(
                transaction_id=f"ua_tx_webhook_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageAlertService(db_session)
        result = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert len(result) == 1

        webhooks = (
            db_session.query(Webhook)
            .filter(Webhook.webhook_type == "usage_alert.triggered")
            .all()
        )
        assert len(webhooks) == 1
        assert webhooks[0].object_type == "usage_alert"

    def test_sum_metric_alert(
        self, db_session, subscription, customer, sum_metric, billing_period
    ):
        """Alert on a SUM metric should aggregate field values."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=sum_metric.id,
                threshold_value=Decimal("500"),
                name="500 bytes alert",
            ),
            DEFAULT_ORG_ID,
        )

        # Create events summing to 600 bytes (above 500 threshold)
        for i in range(6):
            event = Event(
                transaction_id=f"ua_tx_sum_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(sum_metric.code),
                timestamp=start + timedelta(hours=i),
                properties={"bytes": 100},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageAlertService(db_session)
        result = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert len(result) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Repository Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUsageAlertRepository:
    """Tests for UsageAlertRepository CRUD operations."""

    def test_create(self, db_session, subscription, metric):
        repo = UsageAlertRepository(db_session)
        alert = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
                name="Test Alert",
            ),
            DEFAULT_ORG_ID,
        )
        assert alert.id is not None
        assert alert.threshold_value == Decimal("100")
        assert alert.name == "Test Alert"
        assert alert.recurring is False
        assert alert.times_triggered == 0
        assert alert.triggered_at is None

    def test_get_by_id(self, db_session, subscription, metric):
        repo = UsageAlertRepository(db_session)
        created = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )
        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_by_id_with_org(self, db_session, subscription, metric):
        repo = UsageAlertRepository(db_session)
        created = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )
        fetched = repo.get_by_id(created.id, DEFAULT_ORG_ID)
        assert fetched is not None
        # Wrong org should not find
        fetched_wrong = repo.get_by_id(created.id, uuid4())
        assert fetched_wrong is None

    def test_get_by_subscription_id(self, db_session, subscription, metric):
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("200"),
            ),
            DEFAULT_ORG_ID,
        )
        alerts = repo.get_by_subscription_id(subscription.id)
        assert len(alerts) == 2

    def test_get_all(self, db_session, subscription, metric):
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )
        alerts = repo.get_all(DEFAULT_ORG_ID)
        assert len(alerts) == 1

    def test_get_all_pagination(self, db_session, subscription, metric):
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
        assert len(repo.get_all(DEFAULT_ORG_ID, skip=0, limit=3)) == 3
        assert len(repo.get_all(DEFAULT_ORG_ID, skip=3, limit=3)) == 2

    def test_count(self, db_session, subscription, metric):
        repo = UsageAlertRepository(db_session)
        assert repo.count(DEFAULT_ORG_ID) == 0
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )
        assert repo.count(DEFAULT_ORG_ID) == 1

    def test_update(self, db_session, subscription, metric):
        repo = UsageAlertRepository(db_session)
        created = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
                name="Original",
            ),
            DEFAULT_ORG_ID,
        )
        updated = repo.update(
            created.id,
            UsageAlertUpdate(threshold_value=Decimal("200"), name="Updated"),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.threshold_value == Decimal("200")
        assert updated.name == "Updated"

    def test_update_not_found(self, db_session):
        repo = UsageAlertRepository(db_session)
        result = repo.update(uuid4(), UsageAlertUpdate(name="nope"), DEFAULT_ORG_ID)
        assert result is None

    def test_update_partial(self, db_session, subscription, metric):
        repo = UsageAlertRepository(db_session)
        created = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
                name="Original",
            ),
            DEFAULT_ORG_ID,
        )
        updated = repo.update(
            created.id,
            UsageAlertUpdate(name="New Name"),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.name == "New Name"
        assert updated.threshold_value == Decimal("100")

    def test_delete(self, db_session, subscription, metric):
        repo = UsageAlertRepository(db_session)
        created = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )
        assert repo.delete(created.id, DEFAULT_ORG_ID) is True
        assert repo.get_by_id(created.id) is None

    def test_delete_not_found(self, db_session):
        repo = UsageAlertRepository(db_session)
        assert repo.delete(uuid4(), DEFAULT_ORG_ID) is False


# ─────────────────────────────────────────────────────────────────────────────
# Schema Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUsageAlertSchemas:
    """Tests for UsageAlert Pydantic schemas."""

    def test_create_schema_valid(self):
        data = UsageAlertCreate(
            subscription_id=uuid4(),
            billable_metric_id=uuid4(),
            threshold_value=Decimal("100"),
            recurring=True,
            name="Test",
        )
        assert data.threshold_value == Decimal("100")
        assert data.recurring is True

    def test_create_schema_defaults(self):
        data = UsageAlertCreate(
            subscription_id=uuid4(),
            billable_metric_id=uuid4(),
            threshold_value=Decimal("50"),
        )
        assert data.recurring is False
        assert data.name is None

    def test_create_schema_invalid_threshold(self):
        with pytest.raises(ValueError):
            UsageAlertCreate(
                subscription_id=uuid4(),
                billable_metric_id=uuid4(),
                threshold_value=Decimal("0"),
            )

    def test_update_schema_partial(self):
        data = UsageAlertUpdate(name="Updated")
        dumped = data.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "threshold_value" not in dumped

    def test_response_schema_from_model(self, db_session, subscription, metric):
        repo = UsageAlertRepository(db_session)
        alert = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )
        response = UsageAlertResponse.model_validate(alert)
        assert response.id == alert.id
        assert response.threshold_value == Decimal("100")
        assert response.times_triggered == 0


# ─────────────────────────────────────────────────────────────────────────────
# Webhook Event Type Registration Test
# ─────────────────────────────────────────────────────────────────────────────


class TestUsageAlertWebhookEventType:
    """Test that usage_alert.triggered is registered."""

    def test_usage_alert_triggered_in_event_types(self):
        assert "usage_alert.triggered" in WEBHOOK_EVENT_TYPES


# ─────────────────────────────────────────────────────────────────────────────
# Trigger History Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTriggerHistoryRecording:
    """Tests that trigger history records are created when alerts fire."""

    def test_trigger_recorded_on_alert_fire(
        self, db_session, subscription, customer, metric, billing_period
    ):
        """A trigger record should be created when an alert fires."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("10"),
            ),
            DEFAULT_ORG_ID,
        )

        for i in range(20):
            event = Event(
                transaction_id=f"ua_tx_trig_hist_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageAlertService(db_session)
        result = service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert len(result) == 1

        trigger_repo = UsageAlertTriggerRepository(db_session)
        triggers = trigger_repo.get_by_alert_id(result[0].id)
        assert len(triggers) == 1
        assert triggers[0].current_usage == Decimal("20")
        assert triggers[0].threshold_value == Decimal("10")
        assert triggers[0].metric_code == str(metric.code)

    def test_recurring_trigger_records_multiple(
        self, db_session, subscription, customer, metric, billing_period
    ):
        """Recurring alert should create a trigger record each time it fires."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        alert = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("50"),
                recurring=True,
            ),
            DEFAULT_ORG_ID,
        )

        # Create 60 events (crosses 50 once)
        for i in range(60):
            event = Event(
                transaction_id=f"ua_tx_trig_rec1_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageAlertService(db_session)
        service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )

        # Add more events (crosses 100)
        for i in range(60):
            event = Event(
                transaction_id=f"ua_tx_trig_rec2_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i + 100),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service.check_alerts(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )

        trigger_repo = UsageAlertTriggerRepository(db_session)
        triggers = trigger_repo.get_by_alert_id(alert.id)
        assert len(triggers) == 2


# ─────────────────────────────────────────────────────────────────────────────
# get_current_usage_for_alert Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestGetCurrentUsageForAlert:
    """Tests for UsageAlertService.get_current_usage_for_alert."""

    def test_returns_current_usage(
        self, db_session, subscription, customer, metric, billing_period
    ):
        """Should return aggregated usage for the alert's metric."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        alert = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )

        for i in range(25):
            event = Event(
                transaction_id=f"ua_tx_cur_usage_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageAlertService(db_session)
        usage = service.get_current_usage_for_alert(
            alert=alert,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert usage == Decimal("25")

    def test_returns_zero_for_missing_metric(
        self, db_session, subscription, customer, billing_period
    ):
        """Should return 0 if the alert's metric doesn't exist."""
        start, end = billing_period
        repo = UsageAlertRepository(db_session)
        alert = repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=uuid4(),
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )

        service = UsageAlertService(db_session)
        usage = service.get_current_usage_for_alert(
            alert=alert,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert usage == Decimal("0")


# ─────────────────────────────────────────────────────────────────────────────
# Trigger Repository Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUsageAlertTriggerRepository:
    """Tests for UsageAlertTriggerRepository."""

    def test_create_trigger(self, db_session, subscription, metric):
        """Should create a trigger record."""
        alert_repo = UsageAlertRepository(db_session)
        alert = alert_repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )

        trigger_repo = UsageAlertTriggerRepository(db_session)
        now = datetime.now(UTC)
        trigger = trigger_repo.create(
            usage_alert_id=alert.id,
            current_usage=Decimal("150"),
            threshold_value=Decimal("100"),
            metric_code=str(metric.code),
            triggered_at=now,
        )
        assert trigger.id is not None
        assert trigger.current_usage == Decimal("150")
        assert trigger.threshold_value == Decimal("100")
        assert trigger.metric_code == str(metric.code)

    def test_get_by_alert_id(self, db_session, subscription, metric):
        """Should return triggers for a specific alert."""
        alert_repo = UsageAlertRepository(db_session)
        alert = alert_repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )

        trigger_repo = UsageAlertTriggerRepository(db_session)
        now = datetime.now(UTC)
        trigger_repo.create(
            usage_alert_id=alert.id,
            current_usage=Decimal("150"),
            threshold_value=Decimal("100"),
            metric_code="metric1",
            triggered_at=now - timedelta(hours=2),
        )
        trigger_repo.create(
            usage_alert_id=alert.id,
            current_usage=Decimal("250"),
            threshold_value=Decimal("100"),
            metric_code="metric1",
            triggered_at=now - timedelta(hours=1),
        )

        triggers = trigger_repo.get_by_alert_id(alert.id)
        assert len(triggers) == 2
        # Should be ordered by triggered_at DESC (most recent first)
        assert triggers[0].current_usage == Decimal("250")
        assert triggers[1].current_usage == Decimal("150")

    def test_get_by_alert_id_pagination(self, db_session, subscription, metric):
        """Should support pagination."""
        alert_repo = UsageAlertRepository(db_session)
        alert = alert_repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )

        trigger_repo = UsageAlertTriggerRepository(db_session)
        now = datetime.now(UTC)
        for i in range(5):
            trigger_repo.create(
                usage_alert_id=alert.id,
                current_usage=Decimal(str((i + 1) * 100)),
                threshold_value=Decimal("100"),
                metric_code="metric1",
                triggered_at=now - timedelta(hours=5 - i),
            )

        page1 = trigger_repo.get_by_alert_id(alert.id, skip=0, limit=2)
        assert len(page1) == 2
        page2 = trigger_repo.get_by_alert_id(alert.id, skip=2, limit=2)
        assert len(page2) == 2
        page3 = trigger_repo.get_by_alert_id(alert.id, skip=4, limit=2)
        assert len(page3) == 1

    def test_count_by_alert_id(self, db_session, subscription, metric):
        """Should return count of triggers for an alert."""
        alert_repo = UsageAlertRepository(db_session)
        alert = alert_repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )

        trigger_repo = UsageAlertTriggerRepository(db_session)
        assert trigger_repo.count_by_alert_id(alert.id) == 0

        now = datetime.now(UTC)
        trigger_repo.create(
            usage_alert_id=alert.id,
            current_usage=Decimal("150"),
            threshold_value=Decimal("100"),
            metric_code="metric1",
            triggered_at=now,
        )
        assert trigger_repo.count_by_alert_id(alert.id) == 1


# ─────────────────────────────────────────────────────────────────────────────
# New Schema Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestNewSchemas:
    """Tests for new Pydantic schemas."""

    def test_trigger_response_schema(self, db_session, subscription, metric):
        """UsageAlertTriggerResponse should validate from a trigger model."""
        alert_repo = UsageAlertRepository(db_session)
        alert = alert_repo.create(
            UsageAlertCreate(
                subscription_id=subscription.id,
                billable_metric_id=metric.id,
                threshold_value=Decimal("100"),
            ),
            DEFAULT_ORG_ID,
        )

        trigger_repo = UsageAlertTriggerRepository(db_session)
        trigger = trigger_repo.create(
            usage_alert_id=alert.id,
            current_usage=Decimal("150"),
            threshold_value=Decimal("100"),
            metric_code="api_calls",
            triggered_at=datetime.now(UTC),
        )

        response = UsageAlertTriggerResponse.model_validate(trigger)
        assert response.id == trigger.id
        assert response.current_usage == Decimal("150")
        assert response.metric_code == "api_calls"

    def test_status_response_schema(self):
        """UsageAlertStatusResponse should construct properly."""
        now = datetime.now(UTC)
        status = UsageAlertStatusResponse(
            alert_id=uuid4(),
            current_usage=Decimal("75"),
            threshold_value=Decimal("100"),
            usage_percentage=Decimal("75"),
            billing_period_start=now,
            billing_period_end=now + timedelta(days=30),
        )
        assert status.usage_percentage == Decimal("75")
