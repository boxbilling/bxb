"""Tests for UsageQueryService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.core.database import get_db
from app.models.billable_metric import BillableMetric
from app.models.billable_metric_filter import BillableMetricFilter
from app.models.charge import Charge, ChargeModel
from app.models.charge_filter import ChargeFilter
from app.models.charge_filter_value import ChargeFilterValue
from app.models.customer import Customer
from app.models.event import Event
from app.models.plan import Plan, PlanInterval
from app.models.subscription import BillingTime, Subscription, SubscriptionStatus
from app.services.usage_query_service import UsageQueryService

# Use a fixed reference: subscription started_at as anniversary anchor, events within first period
_SUB_START = datetime(2026, 2, 1, tzinfo=UTC)
_EVENT_TIME = datetime(2026, 2, 10, tzinfo=UTC)


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
    c = Customer(external_id="uqs_cust", name="Usage Query Customer")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    p = Plan(
        code="uqs_plan",
        name="Usage Query Plan",
        interval=PlanInterval.MONTHLY.value,
        currency="USD",
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def subscription(db_session, customer, plan):
    """Create an active subscription with calendar billing.

    Calendar billing with monthly interval means the current period is
    the first of this month to the first of next month.
    """
    sub = Subscription(
        external_id="uqs_sub",
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        billing_time=BillingTime.CALENDAR.value,
        started_at=_SUB_START,
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


@pytest.fixture
def count_metric(db_session):
    """Create a COUNT billable metric."""
    m = BillableMetric(
        code="uqs_api_calls",
        name="API Calls",
        aggregation_type="count",
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def sum_metric(db_session):
    """Create a SUM billable metric."""
    m = BillableMetric(
        code="uqs_data_transfer",
        name="Data Transfer",
        aggregation_type="sum",
        field_name="bytes",
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def standard_charge(db_session, plan, count_metric):
    """Create a standard charge for the count metric."""
    ch = Charge(
        plan_id=plan.id,
        billable_metric_id=count_metric.id,
        charge_model=ChargeModel.STANDARD.value,
        properties={"unit_price": "0.10"},
    )
    db_session.add(ch)
    db_session.commit()
    db_session.refresh(ch)
    return ch


def _add_events(db_session, customer, code, count, *, properties=None):
    """Helper to add events at _EVENT_TIME within the current billing period."""
    for i in range(count):
        db_session.add(
            Event(
                external_customer_id=str(customer.external_id),
                code=code,
                transaction_id=f"uqs_{code}_{uuid4()}",
                timestamp=_EVENT_TIME + timedelta(hours=i),
                properties=properties or {},
            )
        )
    db_session.commit()


class TestGetCurrentUsage:
    """Test get_current_usage method."""

    def test_basic_usage_aggregation(
        self, db_session, customer, subscription, count_metric, standard_charge
    ):
        """Test basic usage aggregation across a metric."""
        _add_events(db_session, customer, "uqs_api_calls", 10)

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert result.from_datetime is not None
        assert result.to_datetime is not None
        assert result.currency == "USD"
        assert len(result.charges) == 1

        charge = result.charges[0]
        assert charge.billable_metric.code == "uqs_api_calls"
        assert charge.billable_metric.name == "API Calls"
        assert charge.billable_metric.aggregation_type == "count"
        assert charge.units == Decimal(10)
        # 10 units * 0.10 = 1.0
        assert charge.amount_cents == Decimal("1.0")
        assert charge.charge_model == "standard"
        assert charge.filters == {}
        assert result.amount_cents == Decimal("1.0")

    def test_multiple_metrics(
        self, db_session, customer, plan, subscription, count_metric, sum_metric
    ):
        """Test usage aggregation across multiple metrics."""
        ch1 = Charge(
            plan_id=plan.id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "0.05"},
        )
        ch2 = Charge(
            plan_id=plan.id,
            billable_metric_id=sum_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "0.01"},
        )
        db_session.add_all([ch1, ch2])
        db_session.commit()

        _add_events(db_session, customer, "uqs_api_calls", 5)
        _add_events(db_session, customer, "uqs_data_transfer", 3, properties={"bytes": 100})

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 2
        # 5 * 0.05 = 0.25, 300 * 0.01 = 3.0 => total 3.25
        assert result.amount_cents == Decimal("0.25") + Decimal("3.0")

    def test_zero_usage(self, db_session, customer, subscription, count_metric, standard_charge):
        """Test zero-usage scenario (no events)."""
        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1
        charge = result.charges[0]
        assert charge.units == Decimal(0)
        assert charge.amount_cents == Decimal(0)
        assert result.amount_cents == Decimal(0)

    def test_subscription_not_found(self, db_session):
        """Test error when subscription not found."""
        service = UsageQueryService(db_session)
        fake_id = uuid4()

        with pytest.raises(ValueError, match=f"Subscription {fake_id} not found"):
            service.get_current_usage(
                subscription_id=fake_id,
                external_customer_id="nonexistent",
            )

    def test_filtered_charge_usage(self, db_session, customer, plan, subscription, count_metric):
        """Test usage with filtered charges."""
        bmf = BillableMetricFilter(
            billable_metric_id=count_metric.id,
            key="region",
            values=["us", "eu"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "0.10"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"unit_price": "0.20"},
            invoice_display_name="US API Calls",
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=bmf.id,
            value="us",
        )
        db_session.add(cfv)
        db_session.commit()

        # Events matching filter
        for i in range(4):
            db_session.add(
                Event(
                    external_customer_id=str(customer.external_id),
                    code="uqs_api_calls",
                    transaction_id=f"uqs_filter_us_{uuid4()}",
                    timestamp=_EVENT_TIME + timedelta(hours=i),
                    properties={"region": "us"},
                )
            )
        # Events not matching filter
        for i in range(2):
            db_session.add(
                Event(
                    external_customer_id=str(customer.external_id),
                    code="uqs_api_calls",
                    transaction_id=f"uqs_filter_eu_{uuid4()}",
                    timestamp=_EVENT_TIME + timedelta(hours=i),
                    properties={"region": "eu"},
                )
            )
        db_session.commit()

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1
        charge_usage = result.charges[0]
        assert charge_usage.units == Decimal(4)
        # 4 units * 0.20 (filter override) = 0.80
        assert charge_usage.amount_cents == Decimal("0.80")
        assert charge_usage.filters == {"region": "us"}


class TestGetProjectedUsage:
    """Test get_projected_usage method."""

    def test_projected_usage(
        self, db_session, customer, subscription, count_metric, standard_charge
    ):
        """Test projected usage returns same as current for now."""
        _add_events(db_session, customer, "uqs_api_calls", 5)

        service = UsageQueryService(db_session)
        result = service.get_projected_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1
        assert result.charges[0].units == Decimal(5)
        assert result.amount_cents == Decimal("0.5")

    def test_projected_usage_subscription_not_found(self, db_session):
        """Test error when subscription not found for projected usage."""
        service = UsageQueryService(db_session)
        fake_id = uuid4()

        with pytest.raises(ValueError, match=f"Subscription {fake_id} not found"):
            service.get_projected_usage(
                subscription_id=fake_id,
                external_customer_id="nonexistent",
            )


class TestComputeUsageEdgeCases:
    """Test edge cases in usage computation."""

    def test_no_charges_on_plan(self, db_session, customer, plan, subscription):
        """Test subscription with a plan that has no charges."""
        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 0
        assert result.amount_cents == Decimal(0)

    def test_charge_with_zero_events(self, db_session, customer, plan, subscription):
        """Test charge whose metric exists but has zero events."""
        metric = BillableMetric(
            code="uqs_zero_metric",
            name="Zero Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1
        assert result.charges[0].units == Decimal(0)
        assert result.charges[0].amount_cents == Decimal(0)

    def test_plan_not_found(self, db_session, customer):
        """Test error when plan not found for subscription."""
        p = Plan(
            code="uqs_temp_plan",
            name="Temp Plan",
            interval=PlanInterval.MONTHLY.value,
        )
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)

        sub = Subscription(
            external_id="uqs_orphan_sub",
            customer_id=customer.id,
            plan_id=p.id,
            status=SubscriptionStatus.ACTIVE.value,
            started_at=_SUB_START,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        # Delete the plan
        db_session.delete(p)
        db_session.commit()

        service = UsageQueryService(db_session)
        with pytest.raises(ValueError, match="Plan"):
            service.get_current_usage(
                subscription_id=sub.id,
                external_customer_id=str(customer.external_id),
            )

    def test_filtered_charge_no_filter_values(
        self, db_session, customer, plan, subscription, count_metric
    ):
        """Test filtered charge with no filter values is skipped."""
        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "0.10"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={},
        )
        db_session.add(cf)
        db_session.commit()

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 0

    def test_graduated_charge_model(self, db_session, customer, plan, subscription, count_metric):
        """Test usage with graduated charge model."""
        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "graduated_ranges": [
                    {"from_value": 0, "to_value": 5, "per_unit_amount": "0.10"},
                    {"from_value": 5, "to_value": None, "per_unit_amount": "0.05"},
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()

        _add_events(db_session, customer, "uqs_api_calls", 8)

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1
        charge_usage = result.charges[0]
        assert charge_usage.units == Decimal(8)
        # Tier 1: from_value=0, to_value=5 => capacity=6 units, 6 * 0.10 = 0.60
        # Tier 2: remaining=2 units, 2 * 0.05 = 0.10
        # Total = 0.70
        assert charge_usage.amount_cents == Decimal("0.70")

    def test_filtered_charge_with_missing_bmf(
        self, db_session, customer, plan, subscription, count_metric
    ):
        """Test filtered charge where BillableMetricFilter was deleted."""
        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "0.10"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        fake_bmf_id = uuid4()
        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=fake_bmf_id,
            value="test",
        )
        db_session.add(cfv)
        db_session.commit()

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 0

    def test_filtered_charge_deleted_metric(self, db_session, customer, plan, subscription):
        """Test filtered charge where the metric was deleted."""
        metric = BillableMetric(
            code="uqs_temp_metric",
            name="Temp Metric",
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

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        # Delete the metric
        db_session.delete(metric)
        db_session.commit()

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        # Filtered charge with deleted metric returns empty
        assert len(result.charges) == 0

    def test_unfiltered_charge_deleted_metric(self, db_session, customer, plan, subscription):
        """Test unfiltered charge where the metric was deleted returns None."""
        metric = BillableMetric(
            code="uqs_del_unf_metric",
            name="Del Unfiltered Metric",
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

        # Delete the metric so _compute_charge_usage returns None
        db_session.delete(metric)
        db_session.commit()

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 0

    def test_standard_charge_min_price(self, db_session, customer, plan, subscription):
        """Test standard charge with min_price enforcement."""
        metric = BillableMetric(
            code="uqs_min_metric",
            name="Min Price Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "0.01", "min_price": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        # 1 event * 0.01 = 0.01, but min_price = 5.00
        _add_events(db_session, customer, "uqs_min_metric", 1)

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1
        assert result.charges[0].amount_cents == Decimal("5.00")

    def test_standard_charge_max_price(self, db_session, customer, plan, subscription):
        """Test standard charge with max_price enforcement."""
        metric = BillableMetric(
            code="uqs_max_metric",
            name="Max Price Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "10.00", "max_price": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        # 1 event * 10.00 = 10.00, but max_price = 5.00
        _add_events(db_session, customer, "uqs_max_metric", 1)

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1
        assert result.charges[0].amount_cents == Decimal("5.00")

    def test_percentage_charge_model(self, db_session, customer, plan, subscription):
        """Test percentage charge model."""
        metric = BillableMetric(
            code="uqs_pct_metric",
            name="Percentage Metric",
            aggregation_type="sum",
            field_name="amount",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PERCENTAGE.value,
            properties={"rate": "10.0", "base_amount": "100"},
        )
        db_session.add(charge)
        db_session.commit()

        _add_events(db_session, customer, "uqs_pct_metric", 2, properties={"amount": 50})

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1

    def test_graduated_percentage_charge_model(self, db_session, customer, plan, subscription):
        """Test graduated percentage charge model."""
        metric = BillableMetric(
            code="uqs_grad_pct_metric",
            name="Grad Pct Metric",
            aggregation_type="sum",
            field_name="amount",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 100, "rate": "5.0"},
                    {"from_value": 100, "to_value": None, "rate": "3.0"},
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()

        _add_events(db_session, customer, "uqs_grad_pct_metric", 2, properties={"amount": 50})

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1

    def test_custom_charge_model(self, db_session, customer, plan, subscription):
        """Test custom charge model."""
        metric = BillableMetric(
            code="uqs_custom_metric",
            name="Custom Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"fixed_amount": "2.50"},
        )
        db_session.add(charge)
        db_session.commit()

        _add_events(db_session, customer, "uqs_custom_metric", 3)

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1

    def test_dynamic_charge_model(self, db_session, customer, plan, subscription):
        """Test dynamic charge model."""
        metric = BillableMetric(
            code="uqs_dynamic_metric",
            name="Dynamic Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={},
        )
        db_session.add(charge)
        db_session.commit()

        _add_events(
            db_session, customer, "uqs_dynamic_metric", 2, properties={"unit_price": "3.00"}
        )

        service = UsageQueryService(db_session)
        result = service.get_current_usage(
            subscription_id=subscription.id,
            external_customer_id=str(customer.external_id),
        )

        assert len(result.charges) == 1

    def test_unknown_calculator_returns_zero(
        self, db_session, customer, plan, subscription, count_metric
    ):
        """Test that a charge with no matching calculator returns zero amount."""
        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"unit_price": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _add_events(db_session, customer, "uqs_api_calls", 3)

        with patch(
            "app.services.usage_query_service.get_charge_calculator", return_value=None
        ):
            service = UsageQueryService(db_session)
            result = service.get_current_usage(
                subscription_id=subscription.id,
                external_customer_id=str(customer.external_id),
            )

        assert len(result.charges) == 1
        assert result.charges[0].amount_cents == Decimal(0)

    def test_compute_usage_for_period_plan_not_found(self, db_session, customer):
        """Test _compute_usage_for_period raises when plan is deleted."""
        p = Plan(
            code="uqs_period_plan",
            name="Period Plan",
            interval=PlanInterval.MONTHLY.value,
        )
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)

        sub = Subscription(
            external_id="uqs_period_sub",
            customer_id=customer.id,
            plan_id=p.id,
            status=SubscriptionStatus.ACTIVE.value,
            started_at=_SUB_START,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        # Delete the plan
        db_session.delete(p)
        db_session.commit()

        service = UsageQueryService(db_session)
        with pytest.raises(ValueError, match="Plan"):
            service._compute_usage_for_period(
                subscription=sub,
                external_customer_id=str(customer.external_id),
                period_start=_SUB_START,
                period_end=datetime(2026, 3, 1, tzinfo=UTC),
            )
