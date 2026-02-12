"""Comprehensive tests for advanced charge models and filtered charge calculation.

Tests graduated_percentage, custom, and dynamic charge models through the full
invoice generation flow. Also tests filtered charges: multiple filters per charge,
different pricing per filter, and separate fee records per filter.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from app.core.database import get_db
from app.models.billable_metric import AggregationType, BillableMetric
from app.models.billable_metric_filter import BillableMetricFilter
from app.models.charge import Charge, ChargeModel
from app.models.charge_filter import ChargeFilter
from app.models.charge_filter_value import ChargeFilterValue
from app.models.customer import Customer
from app.models.event import Event
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.fee_repository import FeeRepository
from app.services.invoice_generation import InvoiceGenerationService


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
    c = Customer(external_id="adv_cust", name="Advanced Customer", email="adv@test.com")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def plan(db_session):
    p = Plan(code="adv_plan", name="Advanced Plan", interval=PlanInterval.MONTHLY.value)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def active_sub(db_session, customer, plan):
    sub = Subscription(
        external_id="adv_sub",
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
def count_metric(db_session):
    m = BillableMetric(
        code="adv_api_calls",
        name="Advanced API Calls",
        aggregation_type=AggregationType.COUNT.value,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def sum_metric(db_session):
    m = BillableMetric(
        code="adv_data_transfer",
        name="Advanced Data Transfer",
        aggregation_type=AggregationType.SUM.value,
        field_name="bytes",
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def billing_period():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 2, 1, tzinfo=UTC)
    return start, end


def _create_events(db_session, customer, metric, start, count=10, properties=None):
    """Helper to create events within the billing period."""
    for i in range(count):
        event = Event(
            external_customer_id=customer.external_id,
            code=metric.code,
            transaction_id=f"txn_{uuid4()}",
            timestamp=start + timedelta(hours=i + 1),
            properties=properties or {},
        )
        db_session.add(event)
    db_session.commit()


class TestGraduatedPercentageCharge:
    """Test graduated_percentage charge model through invoice generation."""

    def test_single_tier_flat_rate(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test graduated_percentage with a single open-ended tier."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "base_amount": "5000",
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": None, "rate": "2", "flat_amount": "0"},
                ],
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=1)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # 5000 * 2% = 100
        assert invoice.total == Decimal("100")

    def test_multiple_tiers_with_flat_amounts(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test graduated_percentage across multiple tiers with flat amounts."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "base_amount": "3000",
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 1000, "rate": "5", "flat_amount": "10"},
                    {"from_value": 1000, "to_value": 2000, "rate": "3", "flat_amount": "5"},
                    {"from_value": 2000, "to_value": None, "rate": "1", "flat_amount": "0"},
                ],
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=1)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # First $1000: 1000 * 5% + $10 = $60
        # Next $1000: 1000 * 3% + $5 = $35
        # Remaining $1000: 1000 * 1% + $0 = $10
        assert invoice.total == Decimal("105")

    def test_boundary_exactly_at_tier_limit(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test graduated_percentage when amount exactly matches first tier boundary."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "base_amount": "1000",
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 1000, "rate": "5", "flat_amount": "0"},
                    {"from_value": 1000, "to_value": None, "rate": "1", "flat_amount": "0"},
                ],
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=1)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # All $1000 in first tier: 1000 * 5% = $50
        assert invoice.total == Decimal("50")

    def test_zero_base_amount(self, db_session, active_sub, count_metric, customer, billing_period):
        """Test graduated_percentage with zero base amount."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "base_amount": "0",
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": None, "rate": "10", "flat_amount": "0"},
                ],
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=1)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # 0 * 10% = 0, but quantity is 1 so not None
        assert invoice.total == Decimal("0")

    def test_defaults_to_usage_when_no_base_amount(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test graduated_percentage defaults to usage when base_amount not provided."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": None, "rate": "20", "flat_amount": "0"},
                ],
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=10)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # usage = 10 (count), no base_amount so defaults to usage=10
        # 10 * 20% = 2
        assert invoice.total == Decimal("2")


class TestCustomCharge:
    """Test custom charge model through invoice generation."""

    def test_custom_with_fixed_amount(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test custom charge with fixed custom_amount."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"custom_amount": "250.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=5)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Fixed amount regardless of usage
        assert invoice.total == Decimal("250")

    def test_custom_with_unit_price(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test custom charge with per-unit pricing."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"unit_price": "7.50"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=4)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # 4 * $7.50 = $30
        assert invoice.total == Decimal("30")

    def test_custom_amount_takes_precedence(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test custom_amount takes precedence over unit_price."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"custom_amount": "99", "unit_price": "5"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=100)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # custom_amount=99 takes precedence over 100 * $5
        assert invoice.total == Decimal("99")

    def test_custom_no_properties(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test custom charge with empty properties returns zero."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=3)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # No price configured: units * 0 = 0, but quantity=3 so fee is created
        assert invoice.total == Decimal("0")


class TestDynamicCharge:
    """Test dynamic charge model through invoice generation."""

    def test_dynamic_from_event_properties(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test dynamic pricing derived from event properties."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={},
        )
        db_session.add(charge)
        db_session.commit()

        # Create events with pricing info
        for i, (price, qty) in enumerate([(10, 2), (5, 3), (20, 1)]):
            event = Event(
                external_customer_id=customer.external_id,
                code=count_metric.code,
                transaction_id=f"txn_dyn_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"unit_price": str(price), "quantity": str(qty)},
            )
            db_session.add(event)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # 10*2 + 5*3 + 20*1 = 20 + 15 + 20 = 55
        assert invoice.total == Decimal("55")

    def test_dynamic_custom_field_names(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test dynamic pricing with custom field name configuration."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={"price_field": "cost", "quantity_field": "qty"},
        )
        db_session.add(charge)
        db_session.commit()

        for i, (cost, qty) in enumerate([(100, 1), (50, 4)]):
            event = Event(
                external_customer_id=customer.external_id,
                code=count_metric.code,
                transaction_id=f"txn_dyn_custom_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"cost": str(cost), "qty": str(qty)},
            )
            db_session.add(event)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # 100*1 + 50*4 = 100 + 200 = 300
        assert invoice.total == Decimal("300")

    def test_dynamic_missing_fields_default_zero(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test dynamic pricing when event properties are missing."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={},
        )
        db_session.add(charge)
        db_session.commit()

        # Missing quantity field
        event1 = Event(
            external_customer_id=customer.external_id,
            code=count_metric.code,
            transaction_id=f"txn_dyn_miss_{uuid4()}",
            timestamp=start + timedelta(hours=1),
            properties={"unit_price": "10"},
        )
        # Missing unit_price field
        event2 = Event(
            external_customer_id=customer.external_id,
            code=count_metric.code,
            transaction_id=f"txn_dyn_miss_{uuid4()}",
            timestamp=start + timedelta(hours=2),
            properties={"quantity": "5"},
        )
        db_session.add_all([event1, event2])
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # 10*0 + 0*5 = 0, but events_count=2 so fee may or may not be created
        # amount=0, quantity=events_count=2, so not None
        assert invoice.total == Decimal("0")

    def test_dynamic_no_events(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test dynamic pricing with no events returns no fees."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={},
        )
        db_session.add(charge)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # No events: amount=0, quantity=0 -> None, no line items
        assert invoice.total == Decimal("0")
        assert invoice.line_items == []


class TestFilteredCharges:
    """Test filtered charge calculation: multiple filters, different pricing, fee per filter."""

    def test_multiple_filters_create_separate_fees(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test that a charge with multiple filters creates separate Fee records."""
        start, end = billing_period

        # Create metric filter
        bmf = BillableMetricFilter(
            billable_metric_id=count_metric.id,
            key="region",
            values=["us-east", "eu-west"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        # Create charge with two filters: different pricing per region
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # Filter 1: us-east at $5/unit
        cf_us = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "5"},
            invoice_display_name="US East API Calls",
        )
        db_session.add(cf_us)
        db_session.commit()
        db_session.refresh(cf_us)
        cfv_us = ChargeFilterValue(
            charge_filter_id=cf_us.id,
            billable_metric_filter_id=bmf.id,
            value="us-east",
        )
        db_session.add(cfv_us)
        db_session.commit()

        # Filter 2: eu-west at $3/unit (new BillableMetricFilter for eu-west)
        bmf2 = BillableMetricFilter(
            billable_metric_id=count_metric.id,
            key="region2",
            values=["eu-west"],
        )
        db_session.add(bmf2)
        db_session.commit()
        db_session.refresh(bmf2)

        cf_eu = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "3"},
            invoice_display_name="EU West API Calls",
        )
        db_session.add(cf_eu)
        db_session.commit()
        db_session.refresh(cf_eu)
        cfv_eu = ChargeFilterValue(
            charge_filter_id=cf_eu.id,
            billable_metric_filter_id=bmf2.id,
            value="eu-west",
        )
        db_session.add(cfv_eu)
        db_session.commit()

        # Create events: 3 us-east, 2 eu-west
        for i in range(3):
            db_session.add(
                Event(
                    external_customer_id=customer.external_id,
                    code=count_metric.code,
                    transaction_id=f"txn_filt_us_{uuid4()}",
                    timestamp=start + timedelta(hours=i + 1),
                    properties={"region": "us-east"},
                )
            )
        for i in range(2):
            db_session.add(
                Event(
                    external_customer_id=customer.external_id,
                    code=count_metric.code,
                    transaction_id=f"txn_filt_eu_{uuid4()}",
                    timestamp=start + timedelta(hours=i + 4),
                    properties={"region2": "eu-west"},
                )
            )
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 2

        fee_amounts = sorted([f.amount_cents for f in fees])
        # us-east: 3 * $5 = $15, eu-west: 2 * $3 = $6
        assert fee_amounts == [Decimal("6"), Decimal("15")]

        descriptions = {f.description for f in fees}
        assert "US East API Calls" in descriptions
        assert "EU West API Calls" in descriptions

    def test_different_pricing_per_filter(
        self, db_session, active_sub, sum_metric, customer, billing_period
    ):
        """Test that each filter can have independent pricing properties."""
        start, end = billing_period

        bmf = BillableMetricFilter(
            billable_metric_id=sum_metric.id,
            key="tier",
            values=["standard", "premium"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=sum_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # Standard tier: $0.01/byte
        cf_std = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "0.01"},
            invoice_display_name="Standard Tier",
        )
        db_session.add(cf_std)
        db_session.commit()
        db_session.refresh(cf_std)

        bmf_std = BillableMetricFilter(
            billable_metric_id=sum_metric.id,
            key="tier_std",
            values=["standard"],
        )
        db_session.add(bmf_std)
        db_session.commit()
        db_session.refresh(bmf_std)

        db_session.add(
            ChargeFilterValue(
                charge_filter_id=cf_std.id,
                billable_metric_filter_id=bmf_std.id,
                value="standard",
            )
        )
        db_session.commit()

        # Premium tier: $0.05/byte
        cf_prem = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "0.05"},
            invoice_display_name="Premium Tier",
        )
        db_session.add(cf_prem)
        db_session.commit()
        db_session.refresh(cf_prem)

        bmf_prem = BillableMetricFilter(
            billable_metric_id=sum_metric.id,
            key="tier_prem",
            values=["premium"],
        )
        db_session.add(bmf_prem)
        db_session.commit()
        db_session.refresh(bmf_prem)

        db_session.add(
            ChargeFilterValue(
                charge_filter_id=cf_prem.id,
                billable_metric_filter_id=bmf_prem.id,
                value="premium",
            )
        )
        db_session.commit()

        # Create events: 1000 bytes standard, 200 bytes premium
        for i in range(2):
            db_session.add(
                Event(
                    external_customer_id=customer.external_id,
                    code=sum_metric.code,
                    transaction_id=f"txn_std_{uuid4()}",
                    timestamp=start + timedelta(hours=i + 1),
                    properties={"bytes": 500, "tier_std": "standard"},
                )
            )
        db_session.add(
            Event(
                external_customer_id=customer.external_id,
                code=sum_metric.code,
                transaction_id=f"txn_prem_{uuid4()}",
                timestamp=start + timedelta(hours=5),
                properties={"bytes": 200, "tier_prem": "premium"},
            )
        )
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 2

        fee_by_desc = {f.description: f for f in fees}
        # Standard: 1000 bytes * $0.01 = $10
        assert fee_by_desc["Standard Tier"].amount_cents == Decimal("10")
        # Premium: 200 bytes * $0.05 = $10
        assert fee_by_desc["Premium Tier"].amount_cents == Decimal("10")

    def test_filter_uses_metric_name_when_no_display_name(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test that filter falls back to metric name when invoice_display_name is None."""
        start, end = billing_period

        bmf = BillableMetricFilter(
            billable_metric_id=count_metric.id,
            key="region",
            values=["us-east"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "10"},
            invoice_display_name=None,  # No custom display name
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)
        db_session.add(
            ChargeFilterValue(
                charge_filter_id=cf.id,
                billable_metric_filter_id=bmf.id,
                value="us-east",
            )
        )
        db_session.commit()

        _create_events(
            db_session, customer, count_metric, start, count=2, properties={"region": "us-east"}
        )

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 1
        assert fees[0].description == "Advanced API Calls"  # metric name fallback

    def test_filter_overrides_base_charge_properties(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test that filter properties override charge base properties."""
        start, end = billing_period

        bmf = BillableMetricFilter(
            billable_metric_id=count_metric.id,
            key="region",
            values=["us-east"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        # Base charge: $1/unit
        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # Filter override: $100/unit
        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "100"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)
        db_session.add(
            ChargeFilterValue(
                charge_filter_id=cf.id,
                billable_metric_filter_id=bmf.id,
                value="us-east",
            )
        )
        db_session.commit()

        _create_events(
            db_session, customer, count_metric, start, count=2, properties={"region": "us-east"}
        )

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        # Should use filter's $100/unit, not charge's $1/unit
        assert invoice.total == Decimal("200")

    def test_charge_without_filters_still_works(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test that charges without filters still generate a single fee."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=4)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice.total == Decimal("20")
        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 1

    def test_filtered_dynamic_charge(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test filtered charge with dynamic pricing from event properties."""
        start, end = billing_period

        bmf = BillableMetricFilter(
            billable_metric_id=count_metric.id,
            key="channel",
            values=["web", "api"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={},
            invoice_display_name="Web Channel",
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)
        db_session.add(
            ChargeFilterValue(
                charge_filter_id=cf.id,
                billable_metric_filter_id=bmf.id,
                value="web",
            )
        )
        db_session.commit()

        # Create web events with pricing and API events (should be filtered out)
        db_session.add(
            Event(
                external_customer_id=customer.external_id,
                code=count_metric.code,
                transaction_id=f"txn_web_{uuid4()}",
                timestamp=start + timedelta(hours=1),
                properties={"channel": "web", "unit_price": "10", "quantity": "2"},
            )
        )
        db_session.add(
            Event(
                external_customer_id=customer.external_id,
                code=count_metric.code,
                transaction_id=f"txn_api_{uuid4()}",
                timestamp=start + timedelta(hours=2),
                properties={"channel": "api", "unit_price": "100", "quantity": "5"},
            )
        )
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 1
        # Only web event: 10 * 2 = 20
        assert fees[0].amount_cents == Decimal("20")
        assert fees[0].description == "Web Channel"

    def test_filtered_charge_empty_filter_values_skipped(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test that a ChargeFilter with no filter values is skipped."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # Create a charge filter without any values
        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "999"},
        )
        db_session.add(cf)
        db_session.commit()

        _create_events(db_session, customer, count_metric, start, count=5)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Filter has no values, so it's skipped; no fees generated
        assert invoice.total == Decimal("0")

    def test_filtered_charge_no_matching_events(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test filtered charge when no events match the filter returns zero fee."""
        start, end = billing_period

        bmf = BillableMetricFilter(
            billable_metric_id=count_metric.id,
            key="region",
            values=["us-east"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "10"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)
        db_session.add(
            ChargeFilterValue(
                charge_filter_id=cf.id,
                billable_metric_filter_id=bmf.id,
                value="us-east",
            )
        )
        db_session.commit()

        # Create events that DON'T match the filter
        _create_events(
            db_session, customer, count_metric, start, count=5, properties={"region": "eu-west"}
        )

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # No matching events for us-east filter, amount=0, quantity=0 -> fee skipped
        assert invoice.total == Decimal("0")

    def test_filtered_graduated_charge(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test filtered charge with graduated pricing model."""
        start, end = billing_period

        bmf = BillableMetricFilter(
            billable_metric_id=count_metric.id,
            key="plan_type",
            values=["enterprise"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "graduated_ranges": [
                    {"from_value": 0, "to_value": 5, "per_unit_amount": "2.00", "flat_amount": "0"},
                    {
                        "from_value": 5,
                        "to_value": None,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={
                "graduated_ranges": [
                    {"from_value": 0, "to_value": 5, "per_unit_amount": "3.00", "flat_amount": "0"},
                    {
                        "from_value": 5,
                        "to_value": None,
                        "per_unit_amount": "1.50",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)
        db_session.add(
            ChargeFilterValue(
                charge_filter_id=cf.id,
                billable_metric_filter_id=bmf.id,
                value="enterprise",
            )
        )
        db_session.commit()

        _create_events(
            db_session,
            customer,
            count_metric,
            start,
            count=10,
            properties={"plan_type": "enterprise"},
        )

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 1
        # Filter overrides graduated_ranges: first 6 at $3 = $18, next 4 at $1.50 = $6
        assert fees[0].amount_cents == Decimal("24.00")

    def test_filtered_charge_no_metric_returns_empty(
        self, db_session, active_sub, customer, billing_period
    ):
        """Test _calculate_filtered_charge_fees returns empty when no metric ID."""
        start, end = billing_period

        mock_charge = MagicMock(spec=Charge)
        mock_charge.billable_metric_id = None

        service = InvoiceGenerationService(db_session)
        fees = service._calculate_filtered_charge_fees(
            charge=mock_charge,
            charge_filters=[MagicMock()],
            customer_id=customer.id,
            subscription_id=active_sub.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fees == []

    def test_filtered_charge_metric_not_found_returns_empty(
        self, db_session, active_sub, customer, billing_period
    ):
        """Test _calculate_filtered_charge_fees returns empty when metric not found."""
        start, end = billing_period

        mock_charge = MagicMock(spec=Charge)
        mock_charge.billable_metric_id = uuid4()

        service = InvoiceGenerationService(db_session)
        fees = service._calculate_filtered_charge_fees(
            charge=mock_charge,
            charge_filters=[MagicMock()],
            customer_id=customer.id,
            subscription_id=active_sub.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fees == []

    def test_filter_line_items_populated_for_backward_compat(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test that line_items JSON is populated for filtered charges."""
        start, end = billing_period

        bmf = BillableMetricFilter(
            billable_metric_id=count_metric.id,
            key="region",
            values=["us-east"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "5"},
            invoice_display_name="US East",
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)
        db_session.add(
            ChargeFilterValue(
                charge_filter_id=cf.id,
                billable_metric_filter_id=bmf.id,
                value="us-east",
            )
        )
        db_session.commit()

        _create_events(
            db_session, customer, count_metric, start, count=3, properties={"region": "us-east"}
        )

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert len(invoice.line_items) == 1
        assert invoice.line_items[0]["description"] == "US East"
        assert Decimal(str(invoice.line_items[0]["amount"])) == Decimal("15")

    def test_filtered_charge_zero_amount_zero_quantity_skipped(
        self, db_session, active_sub, count_metric, customer, billing_period
    ):
        """Test that filtered charge with zero amount and zero quantity is skipped."""
        start, end = billing_period

        bmf = BillableMetricFilter(
            billable_metric_id=count_metric.id,
            key="region",
            values=["us-east"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_sub.plan_id,
            billable_metric_id=count_metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "0"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "0"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)
        db_session.add(
            ChargeFilterValue(
                charge_filter_id=cf.id,
                billable_metric_filter_id=bmf.id,
                value="us-east",
            )
        )
        db_session.commit()

        # No events matching = 0 usage, amount=0, quantity=0 -> skipped
        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 0
