"""Tests for UsageThresholdService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.core.database import get_db
from app.models.billable_metric import AggregationType, BillableMetric
from app.models.charge import Charge, ChargeModel
from app.models.customer import Customer
from app.models.event import Event
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.applied_usage_threshold_repository import (
    AppliedUsageThresholdRepository,
)
from app.repositories.usage_threshold_repository import UsageThresholdRepository
from app.schemas.usage_threshold import UsageThresholdCreate
from app.services.usage_threshold_service import UsageThresholdService
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
        external_id=f"uts_cust_{uuid4()}",
        name="Threshold Test Customer",
        email="threshold@example.com",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def plan(db_session):
    p = Plan(
        code=f"uts_plan_{uuid4()}",
        name="Threshold Test Plan",
        interval=PlanInterval.MONTHLY.value,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def active_subscription(db_session, customer, plan):
    sub = Subscription(
        external_id=f"uts_sub_{uuid4()}",
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
def pending_subscription(db_session, customer, plan):
    sub = Subscription(
        external_id=f"uts_sub_pending_{uuid4()}",
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.PENDING.value,
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def metric(db_session):
    m = BillableMetric(
        code=f"uts_api_calls_{uuid4()}",
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
        code=f"uts_data_transfer_{uuid4()}",
        name="Data Transfer",
        aggregation_type=AggregationType.SUM.value,
        field_name="bytes",
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def charge(db_session, plan, metric):
    c = Charge(
        plan_id=plan.id,
        billable_metric_id=metric.id,
        charge_model=ChargeModel.STANDARD.value,
        properties={"unit_price": "100"},  # 100 cents per API call
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def billing_period():
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start + timedelta(days=32)).replace(day=1)
    return start, end


# ─────────────────────────────────────────────────────────────────────────────
# check_thresholds Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckThresholds:
    """Tests for UsageThresholdService.check_thresholds."""

    def test_no_thresholds_returns_empty(
        self, db_session, active_subscription, customer, billing_period
    ):
        service = UsageThresholdService(db_session)
        start, end = billing_period
        result = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert result == []

    def test_threshold_not_crossed_below_amount(
        self, db_session, active_subscription, customer, plan, metric, charge, billing_period
    ):
        """Usage below threshold should not trigger crossing."""
        start, end = billing_period
        # Create threshold at $100 (10000 cents)
        repo = UsageThresholdRepository(db_session)
        repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("10000"),
            ),
            DEFAULT_ORG_ID,
        )

        # Create 50 API calls = 50 * 100 = 5000 cents (below 10000 threshold)
        for i in range(50):
            event = Event(
                transaction_id=f"uts_tx_below_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        result = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert result == []

    def test_threshold_crossed_at_exact_amount(
        self, db_session, active_subscription, customer, plan, metric, charge, billing_period
    ):
        """Usage exactly at threshold should trigger crossing."""
        start, end = billing_period
        # Threshold at 10000 cents
        threshold_repo = UsageThresholdRepository(db_session)
        threshold = threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("10000"),
                threshold_display_name="$100 threshold",
            ),
            DEFAULT_ORG_ID,
        )

        # Create 100 API calls = 100 * 100 = 10000 cents (exactly at threshold)
        for i in range(100):
            event = Event(
                transaction_id=f"uts_tx_exact_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        result = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert len(result) == 1
        assert result[0].usage_threshold_id == threshold.id
        assert result[0].subscription_id == active_subscription.id
        assert result[0].lifetime_usage_amount_cents == Decimal("10000")

    def test_threshold_crossed_above_amount(
        self, db_session, active_subscription, customer, plan, metric, charge, billing_period
    ):
        """Usage above threshold should trigger crossing."""
        start, end = billing_period
        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
            ),
            DEFAULT_ORG_ID,
        )

        # Create 100 API calls = 100 * 100 = 10000 cents (above 5000 threshold)
        for i in range(100):
            event = Event(
                transaction_id=f"uts_tx_above_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        result = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert len(result) == 1
        assert result[0].lifetime_usage_amount_cents == Decimal("10000")

    def test_threshold_not_crossed_again_in_same_period(
        self, db_session, active_subscription, customer, plan, metric, charge, billing_period
    ):
        """Once a threshold is crossed, it should not be crossed again in the same period."""
        start, end = billing_period
        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
            ),
            DEFAULT_ORG_ID,
        )

        # Create enough events to cross threshold
        for i in range(100):
            event = Event(
                transaction_id=f"uts_tx_again_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        # First check: crosses
        result1 = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert len(result1) == 1

        # Second check: should NOT cross again
        result2 = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert result2 == []

    def test_multiple_thresholds_on_same_subscription(
        self, db_session, active_subscription, customer, plan, metric, charge, billing_period
    ):
        """Multiple thresholds can be crossed at different levels."""
        start, end = billing_period
        threshold_repo = UsageThresholdRepository(db_session)
        t1 = threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("3000"),
                threshold_display_name="Low",
            ),
            DEFAULT_ORG_ID,
        )
        t2 = threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
                threshold_display_name="Mid",
            ),
            DEFAULT_ORG_ID,
        )
        t3 = threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("15000"),
                threshold_display_name="High",
            ),
            DEFAULT_ORG_ID,
        )

        # Create 100 API calls = 10000 cents (crosses t1 and t2, not t3)
        for i in range(100):
            event = Event(
                transaction_id=f"uts_tx_multi_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        result = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert len(result) == 2
        crossed_ids = {UUID(str(r.usage_threshold_id)) for r in result}
        assert UUID(str(t1.id)) in crossed_ids
        assert UUID(str(t2.id)) in crossed_ids
        assert UUID(str(t3.id)) not in crossed_ids

    def test_subscription_level_thresholds_included(
        self, db_session, active_subscription, customer, plan, metric, charge, billing_period
    ):
        """Subscription-level thresholds are checked along with plan-level."""
        start, end = billing_period
        threshold_repo = UsageThresholdRepository(db_session)
        # Plan-level threshold
        plan_t = threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("3000"),
            ),
            DEFAULT_ORG_ID,
        )
        # Subscription-level threshold
        sub_t = threshold_repo.create(
            UsageThresholdCreate(
                subscription_id=active_subscription.id,
                amount_cents=Decimal("5000"),
            ),
            DEFAULT_ORG_ID,
        )

        # Create 100 API calls = 10000 cents (crosses both)
        for i in range(100):
            event = Event(
                transaction_id=f"uts_tx_sublevel_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        result = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert len(result) == 2
        crossed_ids = {UUID(str(r.usage_threshold_id)) for r in result}
        assert UUID(str(plan_t.id)) in crossed_ids
        assert UUID(str(sub_t.id)) in crossed_ids

    def test_pending_subscription_returns_empty(
        self, db_session, pending_subscription, customer, billing_period
    ):
        """Threshold checks on non-active subscriptions return empty."""
        start, end = billing_period
        service = UsageThresholdService(db_session)
        result = service.check_thresholds(
            subscription_id=pending_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert result == []

    def test_subscription_not_found_raises(self, db_session, billing_period):
        start, end = billing_period
        service = UsageThresholdService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.check_thresholds(
                subscription_id=uuid4(),
                billing_period_start=start,
                billing_period_end=end,
                external_customer_id="nonexistent",
            )

    def test_webhook_triggered_on_crossing(
        self, db_session, active_subscription, customer, plan, metric, charge, billing_period
    ):
        """Verify that a webhook record is created when a threshold is crossed."""
        from app.models.webhook_endpoint import WebhookEndpoint

        start, end = billing_period
        # Create a webhook endpoint to receive the event
        endpoint = WebhookEndpoint(
            url="https://example.com/webhook",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(endpoint)
        db_session.commit()

        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
            ),
            DEFAULT_ORG_ID,
        )

        # Create 100 events = 10000 cents (exceeds 5000)
        for i in range(100):
            event = Event(
                transaction_id=f"uts_tx_webhook_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        result = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert len(result) == 1

        # Check that a webhook was created
        from app.models.webhook import Webhook

        webhooks = (
            db_session.query(Webhook)
            .filter(Webhook.webhook_type == "usage_threshold.crossed")
            .all()
        )
        assert len(webhooks) == 1
        assert webhooks[0].object_type == "usage_threshold"

    def test_no_charges_zero_usage(
        self, db_session, active_subscription, customer, plan, billing_period
    ):
        """Plan with no charges should have zero usage and not cross thresholds."""
        start, end = billing_period
        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("1000"),
            ),
            DEFAULT_ORG_ID,
        )

        service = UsageThresholdService(db_session)
        result = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert result == []

    def test_recurring_threshold_crosses_again_in_new_period(
        self, db_session, active_subscription, customer, plan, metric, charge, billing_period
    ):
        """Recurring thresholds can be crossed again in a new billing period."""
        start, end = billing_period
        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
                recurring=True,
            ),
            DEFAULT_ORG_ID,
        )

        # Create events for first period
        for i in range(100):
            event = Event(
                transaction_id=f"uts_tx_recur1_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        # First period: crosses
        result1 = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert len(result1) == 1

        # New period: create new events
        new_start = end
        new_end = new_start + timedelta(days=30)
        for i in range(100):
            event = Event(
                transaction_id=f"uts_tx_recur2_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=new_start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        # New period: crosses again (recurring)
        result2 = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=new_start,
            billing_period_end=new_end,
            external_customer_id=str(customer.external_id),
        )
        assert len(result2) == 1

    def test_non_recurring_threshold_not_crossed_in_new_period_if_already_in_same(
        self, db_session, active_subscription, customer, plan, metric, charge, billing_period
    ):
        """Non-recurring threshold crossed in same period shouldn't cross again in same period."""
        start, end = billing_period
        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
                recurring=False,
            ),
            DEFAULT_ORG_ID,
        )

        for i in range(100):
            event = Event(
                transaction_id=f"uts_tx_nonrecur_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        result1 = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert len(result1) == 1

        # Same period: should NOT cross again
        result2 = service.check_thresholds(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert result2 == []


# ─────────────────────────────────────────────────────────────────────────────
# get_current_usage_amount Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestGetCurrentUsageAmount:
    """Tests for UsageThresholdService.get_current_usage_amount."""

    def test_zero_usage_no_charges(self, db_session, active_subscription, customer, billing_period):
        """Subscription with no charges should return zero."""
        start, end = billing_period
        service = UsageThresholdService(db_session)
        amount = service.get_current_usage_amount(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert amount == Decimal("0")

    def test_zero_usage_no_events(
        self, db_session, active_subscription, customer, metric, charge, billing_period
    ):
        """Charge with no events should return zero."""
        start, end = billing_period
        service = UsageThresholdService(db_session)
        amount = service.get_current_usage_amount(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert amount == Decimal("0")

    def test_standard_charge_usage(
        self, db_session, active_subscription, customer, metric, charge, billing_period
    ):
        """Standard charge with events should return correct amount."""
        start, end = billing_period
        # Create 50 API calls at 100 cents each = 5000
        for i in range(50):
            event = Event(
                transaction_id=f"uts_tx_usage_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service.get_current_usage_amount(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert amount == Decimal("5000")

    def test_multiple_charges_summed(
        self,
        db_session,
        active_subscription,
        customer,
        plan,
        metric,
        charge,
        sum_metric,
        billing_period,
    ):
        """Multiple charges on the same plan should be summed."""
        start, end = billing_period
        # Add a second charge (SUM-based)
        charge2 = Charge(
            plan_id=plan.id,
            billable_metric_id=sum_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "50"},  # 50 cents per unit
        )
        db_session.add(charge2)
        db_session.commit()

        # Create 10 API call events = 10 * 100 = 1000 cents
        for i in range(10):
            event = Event(
                transaction_id=f"uts_tx_multi_c1_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i),
                properties={},
            )
            db_session.add(event)

        # Create 5 data transfer events with 10 bytes each = 50 units * 50 cents = 2500 cents
        for i in range(5):
            event = Event(
                transaction_id=f"uts_tx_multi_c2_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(sum_metric.code),
                timestamp=start + timedelta(hours=i),
                properties={"bytes": 10},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service.get_current_usage_amount(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        # COUNT charge: 10 * 100 = 1000
        # SUM charge: 50 * 50 = 2500
        assert amount == Decimal("3500")

    def test_subscription_not_found_raises(self, db_session, billing_period):
        start, end = billing_period
        service = UsageThresholdService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.get_current_usage_amount(
                subscription_id=uuid4(),
                billing_period_start=start,
                billing_period_end=end,
                external_customer_id="nonexistent",
            )

    def test_standard_charge_with_min_price(
        self, db_session, active_subscription, customer, plan, metric, billing_period
    ):
        """Standard charge with min_price should clamp up."""
        start, end = billing_period
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "10", "min_price": "5000"},
        )
        db_session.add(c)
        db_session.commit()

        # 1 event = 1 * 10 = 10 cents, but min_price = 5000
        event = Event(
            transaction_id=f"uts_tx_min_{uuid4()}",
            external_customer_id=str(customer.external_id),
            code=str(metric.code),
            timestamp=start + timedelta(hours=1),
            properties={},
        )
        db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service.get_current_usage_amount(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert amount == Decimal("5000")

    def test_standard_charge_with_max_price(
        self, db_session, active_subscription, customer, plan, metric, billing_period
    ):
        """Standard charge with max_price should clamp down."""
        start, end = billing_period
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "100", "max_price": "2000"},
        )
        db_session.add(c)
        db_session.commit()

        # 50 events = 50 * 100 = 5000, but max_price = 2000
        for i in range(50):
            event = Event(
                transaction_id=f"uts_tx_max_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service.get_current_usage_amount(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert amount == Decimal("2000")

    def test_charge_with_missing_metric_returns_zero(
        self, db_session, active_subscription, customer, plan, billing_period
    ):
        """Charge with a non-existent metric ID returns zero for that charge."""
        start, end = billing_period
        # Create a charge pointing to a non-existent metric
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=uuid4(),
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "100"},
        )
        db_session.add(c)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service.get_current_usage_amount(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert amount == Decimal("0")

    def test_graduated_charge(
        self, db_session, active_subscription, customer, plan, metric, billing_period
    ):
        """Graduated charge model should calculate correctly."""
        start, end = billing_period
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "graduated_ranges": [
                    {"from_value": 0, "to_value": 10, "per_unit_amount": "100", "flat_amount": "0"},
                    {
                        "from_value": 10,
                        "to_value": None,
                        "per_unit_amount": "50",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        db_session.add(c)
        db_session.commit()

        # Create 15 events
        # Graduated ranges: from_value=0, to_value=10 => capacity = 10-0+1 = 11 units
        # First 11 at 100 + 4 at 50 = 1100 + 200 = 1300
        for i in range(15):
            event = Event(
                transaction_id=f"uts_tx_grad_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service.get_current_usage_amount(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert amount == Decimal("1300")

    def test_package_charge(
        self, db_session, active_subscription, customer, plan, metric, billing_period
    ):
        """Package charge model should calculate correctly."""
        start, end = billing_period
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PACKAGE.value,
            properties={"package_size": "10", "amount": "500"},
        )
        db_session.add(c)
        db_session.commit()

        # Create 25 events = ceil(25/10) = 3 packages * 500 = 1500
        for i in range(25):
            event = Event(
                transaction_id=f"uts_tx_pkg_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service.get_current_usage_amount(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert amount == Decimal("1500")

    def test_volume_charge(
        self, db_session, active_subscription, customer, plan, metric, billing_period
    ):
        """Volume charge model should calculate correctly."""
        start, end = billing_period
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.VOLUME.value,
            properties={
                "volume_ranges": [
                    {"from_value": 0, "to_value": 10, "per_unit_amount": "200", "flat_amount": "0"},
                    {
                        "from_value": 10,
                        "to_value": None,
                        "per_unit_amount": "100",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        db_session.add(c)
        db_session.commit()

        # Create 15 events = all 15 at 100 (volume = entire amount at matching tier) = 1500
        for i in range(15):
            event = Event(
                transaction_id=f"uts_tx_vol_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i % 24, minutes=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service.get_current_usage_amount(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=str(customer.external_id),
        )
        assert amount == Decimal("1500")


# ─────────────────────────────────────────────────────────────────────────────
# reset_recurring_thresholds Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestResetRecurringThresholds:
    """Tests for UsageThresholdService.reset_recurring_thresholds."""

    def test_no_thresholds_returns_zero(self, db_session, active_subscription):
        service = UsageThresholdService(db_session)
        count = service.reset_recurring_thresholds(
            subscription_id=active_subscription.id,
            period_start=datetime.now(UTC),
        )
        assert count == 0

    def test_non_recurring_thresholds_not_counted(self, db_session, active_subscription, plan):
        """Non-recurring thresholds should not be counted."""
        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
                recurring=False,
            ),
            DEFAULT_ORG_ID,
        )

        service = UsageThresholdService(db_session)
        count = service.reset_recurring_thresholds(
            subscription_id=active_subscription.id,
            period_start=datetime.now(UTC),
        )
        assert count == 0

    def test_recurring_thresholds_eligible_in_new_period(
        self, db_session, active_subscription, plan
    ):
        """Recurring thresholds should be eligible for crossing in new period."""
        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
                recurring=True,
            ),
            DEFAULT_ORG_ID,
        )
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("10000"),
                recurring=True,
            ),
            DEFAULT_ORG_ID,
        )

        service = UsageThresholdService(db_session)
        count = service.reset_recurring_thresholds(
            subscription_id=active_subscription.id,
            period_start=datetime.now(UTC),
        )
        assert count == 2

    def test_recurring_threshold_already_crossed_in_new_period(
        self, db_session, active_subscription, plan
    ):
        """Recurring threshold already crossed in current period should not be counted."""
        threshold_repo = UsageThresholdRepository(db_session)
        threshold = threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
                recurring=True,
            ),
            DEFAULT_ORG_ID,
        )

        now = datetime.now(UTC)
        period_start = now - timedelta(days=5)

        # Simulate crossing in this period
        applied_repo = AppliedUsageThresholdRepository(db_session)
        applied_repo.create(
            usage_threshold_id=threshold.id,
            subscription_id=active_subscription.id,
            crossed_at=now - timedelta(days=2),
            organization_id=DEFAULT_ORG_ID,
        )

        service = UsageThresholdService(db_session)
        count = service.reset_recurring_thresholds(
            subscription_id=active_subscription.id,
            period_start=period_start,
        )
        assert count == 0

    def test_recurring_threshold_crossed_in_old_period_eligible(
        self, db_session, active_subscription, plan
    ):
        """Recurring threshold crossed in old period should be eligible in new."""
        threshold_repo = UsageThresholdRepository(db_session)
        threshold = threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
                recurring=True,
            ),
            DEFAULT_ORG_ID,
        )

        now = datetime.now(UTC)
        old_period_crossing = now - timedelta(days=60)
        new_period_start = now - timedelta(days=5)

        # Simulate crossing in old period
        applied_repo = AppliedUsageThresholdRepository(db_session)
        applied_repo.create(
            usage_threshold_id=threshold.id,
            subscription_id=active_subscription.id,
            crossed_at=old_period_crossing,
            organization_id=DEFAULT_ORG_ID,
        )

        service = UsageThresholdService(db_session)
        count = service.reset_recurring_thresholds(
            subscription_id=active_subscription.id,
            period_start=new_period_start,
        )
        assert count == 1

    def test_subscription_not_found_raises(self, db_session):
        service = UsageThresholdService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.reset_recurring_thresholds(
                subscription_id=uuid4(),
                period_start=datetime.now(UTC),
            )

    def test_mixed_recurring_and_non_recurring(self, db_session, active_subscription, plan):
        """Only recurring thresholds should be counted."""
        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
                recurring=True,
            ),
            DEFAULT_ORG_ID,
        )
        threshold_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("10000"),
                recurring=False,
            ),
            DEFAULT_ORG_ID,
        )
        threshold_repo.create(
            UsageThresholdCreate(
                subscription_id=active_subscription.id,
                amount_cents=Decimal("15000"),
                recurring=True,
            ),
            DEFAULT_ORG_ID,
        )

        service = UsageThresholdService(db_session)
        count = service.reset_recurring_thresholds(
            subscription_id=active_subscription.id,
            period_start=datetime.now(UTC),
        )
        assert count == 2


# ─────────────────────────────────────────────────────────────────────────────
# _get_effective_thresholds Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestGetEffectiveThresholds:
    """Tests for the internal _get_effective_thresholds method."""

    def test_empty_when_no_thresholds(self, db_session, active_subscription, plan):
        service = UsageThresholdService(db_session)
        result = service._get_effective_thresholds(active_subscription.id, UUID(str(plan.id)))
        assert result == []

    def test_plan_thresholds_only(self, db_session, active_subscription, plan):
        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(plan_id=plan.id, amount_cents=Decimal("5000")),
            DEFAULT_ORG_ID,
        )
        threshold_repo.create(
            UsageThresholdCreate(plan_id=plan.id, amount_cents=Decimal("1000")),
            DEFAULT_ORG_ID,
        )

        service = UsageThresholdService(db_session)
        result = service._get_effective_thresholds(active_subscription.id, UUID(str(plan.id)))
        assert len(result) == 2
        # Should be sorted by amount ascending
        amounts = [Decimal(str(t.amount_cents)) for t in result]
        assert amounts == [Decimal("1000"), Decimal("5000")]

    def test_subscription_and_plan_thresholds_combined(self, db_session, active_subscription, plan):
        threshold_repo = UsageThresholdRepository(db_session)
        threshold_repo.create(
            UsageThresholdCreate(plan_id=plan.id, amount_cents=Decimal("5000")),
            DEFAULT_ORG_ID,
        )
        threshold_repo.create(
            UsageThresholdCreate(
                subscription_id=active_subscription.id, amount_cents=Decimal("3000")
            ),
            DEFAULT_ORG_ID,
        )

        service = UsageThresholdService(db_session)
        result = service._get_effective_thresholds(active_subscription.id, UUID(str(plan.id)))
        assert len(result) == 2
        amounts = [Decimal(str(t.amount_cents)) for t in result]
        assert amounts == [Decimal("3000"), Decimal("5000")]


# ─────────────────────────────────────────────────────────────────────────────
# _calculate_charge_amount Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCalculateChargeAmount:
    """Tests for the internal _calculate_charge_amount method."""

    def test_standard_charge_calculation(
        self, db_session, active_subscription, customer, metric, charge, billing_period
    ):
        start, end = billing_period
        for i in range(10):
            event = Event(
                transaction_id=f"uts_tx_calc_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service._calculate_charge_amount(
            charge=charge,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert amount == Decimal("1000")  # 10 events * 100 cents

    def test_charge_no_events_returns_zero(
        self, db_session, plan, metric, customer, billing_period
    ):
        """Charge with zero events should return zero."""
        start, end = billing_period
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "500"},
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)

        service = UsageThresholdService(db_session)
        amount = service._calculate_charge_amount(
            charge=c,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert amount == Decimal("0")  # 0 events * 500

    def test_percentage_charge(self, db_session, plan, metric, customer, billing_period):
        """Percentage charge model should calculate correctly."""
        start, end = billing_period
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PERCENTAGE.value,
            properties={"rate": "10", "base_amount": "10000"},  # 10% of 10000
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)

        # Create some events
        for i in range(5):
            event = Event(
                transaction_id=f"uts_tx_pct_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service._calculate_charge_amount(
            charge=c,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        # 10% of 10000 = 1000
        assert amount == Decimal("1000")

    def test_graduated_percentage_charge(self, db_session, plan, metric, customer, billing_period):
        """Graduated percentage charge model should calculate correctly."""
        start, end = billing_period
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "base_amount": "10000",
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 5000, "rate": "5", "flat_amount": "0"},
                    {"from_value": 5000, "to_value": None, "rate": "10", "flat_amount": "0"},
                ],
            },
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)

        event = Event(
            transaction_id=f"uts_tx_gp_{uuid4()}",
            external_customer_id=str(customer.external_id),
            code=str(metric.code),
            timestamp=start + timedelta(hours=1),
            properties={},
        )
        db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service._calculate_charge_amount(
            charge=c,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        # 5% of first 5000 = 250, 10% of remaining 5000 = 500, total = 750
        assert amount == Decimal("750")

    def test_custom_charge(self, db_session, plan, metric, customer, billing_period):
        """Custom charge model should calculate correctly."""
        start, end = billing_period
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"custom_amount": "999"},
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)

        event = Event(
            transaction_id=f"uts_tx_custom_{uuid4()}",
            external_customer_id=str(customer.external_id),
            code=str(metric.code),
            timestamp=start + timedelta(hours=1),
            properties={},
        )
        db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service._calculate_charge_amount(
            charge=c,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        assert amount == Decimal("999")

    def test_dynamic_charge(self, db_session, plan, metric, customer, billing_period):
        """Dynamic charge model should calculate correctly."""
        start, end = billing_period
        c = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={"price_field": "unit_price", "quantity_field": "quantity"},
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)

        # Create events with price/quantity properties
        for i in range(3):
            event = Event(
                transaction_id=f"uts_tx_dyn_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(metric.code),
                timestamp=start + timedelta(hours=i),
                properties={"unit_price": 100, "quantity": 2},
            )
            db_session.add(event)
        db_session.commit()

        service = UsageThresholdService(db_session)
        amount = service._calculate_charge_amount(
            charge=c,
            external_customer_id=str(customer.external_id),
            billing_period_start=start,
            billing_period_end=end,
        )
        # 3 events * (100 * 2) = 600
        assert amount == Decimal("600")


# ─────────────────────────────────────────────────────────────────────────────
# Webhook Event Type Registration Test
# ─────────────────────────────────────────────────────────────────────────────


class TestWebhookEventType:
    """Tests for the usage_threshold.crossed webhook event type."""

    def test_usage_threshold_crossed_in_event_types(self):
        assert "usage_threshold.crossed" in WEBHOOK_EVENT_TYPES
