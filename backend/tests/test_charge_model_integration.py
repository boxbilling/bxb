"""Integration tests for end-to-end invoice generation with each charge model.

Each test creates the full chain:
  Customer -> Plan -> BillableMetric -> Charge -> Subscription -> Events -> Invoice
and verifies the invoice totals, line items, and fee calculations.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import Base, engine, get_db
from app.models.billable_metric import BillableMetric
from app.models.charge import Charge, ChargeModel
from app.models.customer import Customer
from app.models.event import Event
from app.models.invoice import InvoiceStatus
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.invoice_generation import InvoiceGenerationService


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
def billing_period():
    """Return a billing period (start, end)."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 2, 1, tzinfo=UTC)
    return start, end


def _create_customer(db_session, external_id="integ_cust"):
    """Create a test customer."""
    c = Customer(external_id=external_id, name="Integration Customer", email="integ@test.com")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def _create_plan(db_session, code="integ_plan"):
    """Create a test plan."""
    p = Plan(code=code, name="Integration Plan", interval=PlanInterval.MONTHLY.value)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


def _create_metric(
    db_session, code="api_calls", name="API Calls", aggregation_type="count", field_name=None
):
    """Create a test billable metric."""
    m = BillableMetric(
        code=code,
        name=name,
        aggregation_type=aggregation_type,
        field_name=field_name,
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


def _create_subscription(db_session, customer, plan, external_id="integ_sub"):
    """Create an active subscription."""
    sub = Subscription(
        external_id=external_id,
        customer_id=customer.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE.value,
        started_at=datetime.now(UTC) - timedelta(days=30),
    )
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)
    return sub


def _create_events(db_session, customer, metric, billing_period, count=10, properties=None):
    """Create events within the billing period."""
    start, end = billing_period
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


class TestGraduatedChargeIntegration:
    """End-to-end tests for graduated charge model invoice generation."""

    def test_graduated_two_tiers(self, db_session, billing_period):
        """Graduated charge: 10 events across two tiers produces correct invoice total."""
        customer = _create_customer(db_session, "grad_cust")
        plan = _create_plan(db_session, "grad_plan")
        metric = _create_metric(db_session, "grad_api_calls", "Graduated API Calls")
        sub = _create_subscription(db_session, customer, plan, "grad_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
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

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert invoice.status == InvoiceStatus.DRAFT.value
        assert len(invoice.line_items) == 1
        # First 6 units (0-5 inclusive) at $2 = $12, remaining 4 at $1 = $4 => $16
        assert invoice.total == Decimal("16.00")
        assert invoice.subtotal == Decimal("16.00")

    def test_graduated_with_flat_fees(self, db_session, billing_period):
        """Graduated charge with flat fees per tier."""
        customer = _create_customer(db_session, "grad_flat_cust")
        plan = _create_plan(db_session, "grad_flat_plan")
        metric = _create_metric(db_session, "grad_flat_calls", "Graduated Flat Calls")
        sub = _create_subscription(db_session, customer, plan, "grad_flat_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "graduated_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 3,
                        "per_unit_amount": "1.00",
                        "flat_amount": "5.00",
                    },
                    {
                        "from_value": 3,
                        "to_value": None,
                        "per_unit_amount": "0.50",
                        "flat_amount": "10.00",
                    },
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=8)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert len(invoice.line_items) == 1
        # Tier 1: 4 units (0-3) * $1 + $5 flat = $9
        # Tier 2: 4 units * $0.50 + $10 flat = $12
        # Total = $21
        assert invoice.total == Decimal("21.00")

    def test_graduated_bxb_format(self, db_session, billing_period):
        """Graduated charge using bxb tier format."""
        customer = _create_customer(db_session, "grad_bxb_cust")
        plan = _create_plan(db_session, "grad_bxb_plan")
        metric = _create_metric(db_session, "grad_bxb_calls", "Graduated bxb Calls")
        sub = _create_subscription(db_session, customer, plan, "grad_bxb_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "tiers": [
                    {"up_to": 5, "unit_price": "3.00"},
                    {"up_to": 10, "unit_price": "2.00"},
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=8)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # First 5 at $3 = $15, next 3 at $2 = $6 => $21
        assert invoice.total == Decimal("21.00")


class TestVolumeChargeIntegration:
    """End-to-end tests for volume charge model invoice generation."""

    def test_volume_falls_in_second_tier(self, db_session, billing_period):
        """Volume charge: 10 events fall in second tier, all priced at that tier."""
        customer = _create_customer(db_session, "vol_cust")
        plan = _create_plan(db_session, "vol_plan")
        metric = _create_metric(db_session, "vol_api_calls", "Volume API Calls")
        sub = _create_subscription(db_session, customer, plan, "vol_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.VOLUME.value,
            properties={
                "volume_ranges": [
                    {"from_value": 0, "to_value": 5, "per_unit_amount": "3.00", "flat_amount": "0"},
                    {
                        "from_value": 6,
                        "to_value": 20,
                        "per_unit_amount": "2.00",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert len(invoice.line_items) == 1
        # All 10 units in second tier at $2 per unit = $20
        assert invoice.total == Decimal("20.00")

    def test_volume_with_flat_amount(self, db_session, billing_period):
        """Volume charge with flat amount per tier."""
        customer = _create_customer(db_session, "vol_flat_cust")
        plan = _create_plan(db_session, "vol_flat_plan")
        metric = _create_metric(db_session, "vol_flat_calls", "Volume Flat Calls")
        sub = _create_subscription(db_session, customer, plan, "vol_flat_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.VOLUME.value,
            properties={
                "volume_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 5,
                        "per_unit_amount": "3.00",
                        "flat_amount": "10.00",
                    },
                    {
                        "from_value": 6,
                        "to_value": None,
                        "per_unit_amount": "1.00",
                        "flat_amount": "5.00",
                    },
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=3)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # 3 units in first tier: 3 * $3 + $10 flat = $19
        assert invoice.total == Decimal("19.00")

    def test_volume_bxb_format(self, db_session, billing_period):
        """Volume charge using bxb tier format."""
        customer = _create_customer(db_session, "vol_bxb_cust")
        plan = _create_plan(db_session, "vol_bxb_plan")
        metric = _create_metric(db_session, "vol_bxb_calls", "Volume bxb Calls")
        sub = _create_subscription(db_session, customer, plan, "vol_bxb_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.VOLUME.value,
            properties={
                "tiers": [
                    {"up_to": 5, "unit_price": "4.00"},
                    {"up_to": 15, "unit_price": "2.50"},
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=7)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # 7 units in second tier (up_to 15): 7 * $2.50 = $17.50
        assert invoice.total == Decimal("17.50")


class TestPackageChargeIntegration:
    """End-to-end tests for package charge model invoice generation."""

    def test_package_rounds_up(self, db_session, billing_period):
        """Package charge: 7 events with package_size=5 rounds up to 2 packages."""
        customer = _create_customer(db_session, "pkg_cust")
        plan = _create_plan(db_session, "pkg_plan")
        metric = _create_metric(db_session, "pkg_api_calls", "Package API Calls")
        sub = _create_subscription(db_session, customer, plan, "pkg_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PACKAGE.value,
            properties={
                "amount": "10.00",
                "package_size": "5",
                "free_units": "0",
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=7)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert len(invoice.line_items) == 1
        # ceil(7 / 5) = 2 packages * $10 = $20
        assert invoice.total == Decimal("20.00")

    def test_package_with_free_units(self, db_session, billing_period):
        """Package charge: free units reduce billable count."""
        customer = _create_customer(db_session, "pkg_free_cust")
        plan = _create_plan(db_session, "pkg_free_plan")
        metric = _create_metric(db_session, "pkg_free_calls", "Package Free Calls")
        sub = _create_subscription(db_session, customer, plan, "pkg_free_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PACKAGE.value,
            properties={
                "amount": "25.00",
                "package_size": "10",
                "free_units": "5",
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=12)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # billable = max(0, 12 - 5) = 7, ceil(7 / 10) = 1 package * $25 = $25
        assert invoice.total == Decimal("25.00")

    def test_package_exact_boundary(self, db_session, billing_period):
        """Package charge: exact package boundary doesn't round up."""
        customer = _create_customer(db_session, "pkg_exact_cust")
        plan = _create_plan(db_session, "pkg_exact_plan")
        metric = _create_metric(db_session, "pkg_exact_calls", "Package Exact Calls")
        sub = _create_subscription(db_session, customer, plan, "pkg_exact_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PACKAGE.value,
            properties={
                "amount": "15.00",
                "package_size": "5",
                "free_units": "0",
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # ceil(10 / 5) = 2 packages * $15 = $30
        assert invoice.total == Decimal("30.00")


class TestPercentageChargeIntegration:
    """End-to-end tests for percentage charge model invoice generation."""

    def test_percentage_basic(self, db_session, billing_period):
        """Percentage charge: 10% of $1000 base amount."""
        customer = _create_customer(db_session, "pct_cust")
        plan = _create_plan(db_session, "pct_plan")
        metric = _create_metric(db_session, "pct_txns", "Percentage Transactions")
        sub = _create_subscription(db_session, customer, plan, "pct_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PERCENTAGE.value,
            properties={
                "rate": "10",
                "fixed_amount": "0",
                "base_amount": "1000",
                "event_count": "5",
                "free_units_per_events": "0",
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert len(invoice.line_items) == 1
        # 10% of $1000 = $100, no fixed fees
        assert invoice.total == Decimal("100")

    def test_percentage_with_fixed_fees(self, db_session, billing_period):
        """Percentage charge with per-event fixed fees."""
        customer = _create_customer(db_session, "pct_fixed_cust")
        plan = _create_plan(db_session, "pct_fixed_plan")
        metric = _create_metric(db_session, "pct_fixed_txns", "Percentage Fixed Txns")
        sub = _create_subscription(db_session, customer, plan, "pct_fixed_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PERCENTAGE.value,
            properties={
                "rate": "5",
                "fixed_amount": "2.00",
                "base_amount": "500",
                "event_count": "10",
                "free_units_per_events": "0",
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=3)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # 5% of $500 = $25, plus 10 events * $2 fixed = $20 => $45
        assert invoice.total == Decimal("45")

    def test_percentage_with_free_events(self, db_session, billing_period):
        """Percentage charge with free events reducing fixed fees."""
        customer = _create_customer(db_session, "pct_free_cust")
        plan = _create_plan(db_session, "pct_free_plan")
        metric = _create_metric(db_session, "pct_free_txns", "Percentage Free Txns")
        sub = _create_subscription(db_session, customer, plan, "pct_free_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PERCENTAGE.value,
            properties={
                "rate": "5",
                "fixed_amount": "3.00",
                "base_amount": "200",
                "event_count": "8",
                "free_units_per_events": "3",
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=4)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # 5% of $200 = $10, billable events = max(0, 8 - 3) = 5, 5 * $3 = $15 => $25
        assert invoice.total == Decimal("25")

    def test_percentage_min_max_bounds(self, db_session, billing_period):
        """Percentage charge with per-transaction min/max bounds."""
        customer = _create_customer(db_session, "pct_bounds_cust")
        plan = _create_plan(db_session, "pct_bounds_plan")
        metric = _create_metric(db_session, "pct_bounds_txns", "Percentage Bounds Txns")
        sub = _create_subscription(db_session, customer, plan, "pct_bounds_sub")

        # Test min bound
        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PERCENTAGE.value,
            properties={
                "rate": "1",
                "fixed_amount": "0",
                "base_amount": "10",
                "event_count": "0",
                "free_units_per_events": "0",
                "per_transaction_min_amount": "5.00",
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=1)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # 1% of $10 = $0.10, but min is $5 => $5
        assert invoice.total == Decimal("5.00")


class TestGraduatedPercentageChargeIntegration:
    """End-to-end tests for graduated percentage charge model invoice generation."""

    def test_graduated_percentage_two_tiers(self, db_session, billing_period):
        """Graduated percentage: $1500 across two tiers."""
        customer = _create_customer(db_session, "gp_cust")
        plan = _create_plan(db_session, "gp_plan")
        metric = _create_metric(db_session, "gp_amount", "GP Amount")
        sub = _create_subscription(db_session, customer, plan, "gp_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "base_amount": "1500",
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 1000, "rate": "5", "flat_amount": "0"},
                    {"from_value": 1000, "to_value": None, "rate": "3", "flat_amount": "0"},
                ],
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=1)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert len(invoice.line_items) == 1
        # First $1000 at 5% = $50, remaining $500 at 3% = $15 => $65
        assert invoice.total == Decimal("65")

    def test_graduated_percentage_with_flat_fees(self, db_session, billing_period):
        """Graduated percentage with flat fees per tier."""
        customer = _create_customer(db_session, "gp_flat_cust")
        plan = _create_plan(db_session, "gp_flat_plan")
        metric = _create_metric(db_session, "gp_flat_amount", "GP Flat Amount")
        sub = _create_subscription(db_session, customer, plan, "gp_flat_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "base_amount": "800",
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 500, "rate": "10", "flat_amount": "20.00"},
                    {"from_value": 500, "to_value": None, "rate": "5", "flat_amount": "10.00"},
                ],
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=1)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # Tier 1: $500 * 10% + $20 flat = $50 + $20 = $70
        # Tier 2: $300 * 5% + $10 flat = $15 + $10 = $25
        # Total: $95
        assert invoice.total == Decimal("95")

    def test_graduated_percentage_falls_back_to_usage(self, db_session, billing_period):
        """Graduated percentage without base_amount falls back to aggregated usage."""
        customer = _create_customer(db_session, "gp_fb_cust")
        plan = _create_plan(db_session, "gp_fb_plan")
        metric = _create_metric(db_session, "gp_fb_calls", "GP Fallback Calls")
        sub = _create_subscription(db_session, customer, plan, "gp_fb_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": None, "rate": "10", "flat_amount": "0"},
                ],
            },
        )
        db_session.add(charge)
        db_session.commit()

        # 5 events => usage = 5 (count aggregation)
        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # No base_amount, so falls back to usage=5, 10% of 5 = 0.5
        assert invoice.total == Decimal("0.5")


class TestMultiChargeModelIntegration:
    """End-to-end tests with multiple charge models on a single plan."""

    def test_plan_with_standard_and_graduated_charges(self, db_session, billing_period):
        """Invoice with both standard and graduated charges on the same plan."""
        customer = _create_customer(db_session, "multi_cust")
        plan = _create_plan(db_session, "multi_plan")
        metric1 = _create_metric(db_session, "multi_std_calls", "Multi Standard Calls")
        metric2 = _create_metric(db_session, "multi_grad_calls", "Multi Graduated Calls")
        sub = _create_subscription(db_session, customer, plan, "multi_sub")

        # Standard charge
        charge1 = Charge(
            plan_id=plan.id,
            billable_metric_id=metric1.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        # Graduated charge
        charge2 = Charge(
            plan_id=plan.id,
            billable_metric_id=metric2.id,
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
        db_session.add_all([charge1, charge2])
        db_session.commit()

        # 5 events for standard metric
        _create_events(db_session, customer, metric1, billing_period, count=5)
        # 10 events for graduated metric
        _create_events(db_session, customer, metric2, billing_period, count=10)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert len(invoice.line_items) == 2
        # Standard: 5 * $1 = $5
        # Graduated: 6 * $2 + 4 * $1 = $16
        # Total: $21
        assert invoice.total == Decimal("21.00")

    def test_plan_with_all_charge_types(self, db_session, billing_period):
        """Invoice with all charge model types on a single plan."""
        customer = _create_customer(db_session, "all_types_cust")
        plan = _create_plan(db_session, "all_types_plan")
        sub = _create_subscription(db_session, customer, plan, "all_types_sub")

        # Standard metric and charge
        metric_std = _create_metric(db_session, "all_std", "All Standard")
        charge_std = Charge(
            plan_id=plan.id,
            billable_metric_id=metric_std.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "2.00"},
        )

        # Graduated metric and charge
        metric_grad = _create_metric(db_session, "all_grad", "All Graduated")
        charge_grad = Charge(
            plan_id=plan.id,
            billable_metric_id=metric_grad.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "graduated_ranges": [
                    {"from_value": 0, "to_value": 5, "per_unit_amount": "3.00", "flat_amount": "0"},
                    {
                        "from_value": 5,
                        "to_value": None,
                        "per_unit_amount": "1.00",
                        "flat_amount": "0",
                    },
                ]
            },
        )

        # Volume metric and charge
        metric_vol = _create_metric(db_session, "all_vol", "All Volume")
        charge_vol = Charge(
            plan_id=plan.id,
            billable_metric_id=metric_vol.id,
            charge_model=ChargeModel.VOLUME.value,
            properties={
                "volume_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 10,
                        "per_unit_amount": "5.00",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 11,
                        "to_value": None,
                        "per_unit_amount": "2.00",
                        "flat_amount": "0",
                    },
                ]
            },
        )

        # Package metric and charge
        metric_pkg = _create_metric(db_session, "all_pkg", "All Package")
        charge_pkg = Charge(
            plan_id=plan.id,
            billable_metric_id=metric_pkg.id,
            charge_model=ChargeModel.PACKAGE.value,
            properties={"amount": "20.00", "package_size": "5", "free_units": "0"},
        )

        # Percentage metric and charge
        metric_pct = _create_metric(db_session, "all_pct", "All Percentage")
        charge_pct = Charge(
            plan_id=plan.id,
            billable_metric_id=metric_pct.id,
            charge_model=ChargeModel.PERCENTAGE.value,
            properties={
                "rate": "10",
                "fixed_amount": "0",
                "base_amount": "100",
                "event_count": "1",
                "free_units_per_events": "0",
            },
        )

        db_session.add_all([charge_std, charge_grad, charge_vol, charge_pkg, charge_pct])
        db_session.commit()

        # Create events for each metric
        _create_events(db_session, customer, metric_std, billing_period, count=3)  # 3 units
        _create_events(db_session, customer, metric_grad, billing_period, count=8)  # 8 units
        _create_events(db_session, customer, metric_vol, billing_period, count=4)  # 4 units
        _create_events(db_session, customer, metric_pkg, billing_period, count=7)  # 7 units
        _create_events(db_session, customer, metric_pct, billing_period, count=1)  # 1 event

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert len(invoice.line_items) == 5

        # Standard: 3 * $2 = $6
        # Graduated: 6 * $3 + 2 * $1 = $20
        # Volume: 4 units in first tier at $5 = $20
        # Package: ceil(7/5) = 2 * $20 = $40
        # Percentage: 10% of $100 = $10
        # Total = $6 + $20 + $20 + $40 + $10 = $96
        assert invoice.total == Decimal("96")


class TestSumAggregationIntegration:
    """Integration tests using SUM aggregation type through invoice generation."""

    def test_standard_charge_with_sum_aggregation(self, db_session, billing_period):
        """Standard charge with SUM aggregation sums event property values."""
        customer = _create_customer(db_session, "sum_cust")
        plan = _create_plan(db_session, "sum_plan")
        metric = _create_metric(
            db_session,
            "data_transfer",
            "Data Transfer (GB)",
            aggregation_type="sum",
            field_name="gb_transferred",
        )
        sub = _create_subscription(db_session, customer, plan, "sum_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "0.50"},
        )
        db_session.add(charge)
        db_session.commit()

        start, end = billing_period
        # Create events with varying gb_transferred values
        values = [10, 20, 5, 15]  # total = 50 GB
        for i, val in enumerate(values):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric.code,
                transaction_id=f"txn_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"gb_transferred": val},
            )
            db_session.add(event)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert len(invoice.line_items) == 1
        # SUM aggregation: 10 + 20 + 5 + 15 = 50 GB, 50 * $0.50 = $25
        assert invoice.total == Decimal("25")

    def test_graduated_charge_with_sum_aggregation(self, db_session, billing_period):
        """Graduated charge with SUM aggregation."""
        customer = _create_customer(db_session, "sum_grad_cust")
        plan = _create_plan(db_session, "sum_grad_plan")
        metric = _create_metric(
            db_session,
            "sum_grad_transfer",
            "Sum Grad Transfer",
            aggregation_type="sum",
            field_name="amount",
        )
        sub = _create_subscription(db_session, customer, plan, "sum_grad_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "graduated_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 100,
                        "per_unit_amount": "0.10",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 100,
                        "to_value": None,
                        "per_unit_amount": "0.05",
                        "flat_amount": "0",
                    },
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()

        start, end = billing_period
        # Create events that sum to 150
        for i, val in enumerate([50, 60, 40]):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric.code,
                transaction_id=f"txn_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"amount": val},
            )
            db_session.add(event)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        # SUM = 150. Graduated: first 101 (0-100) at $0.10 = $10.10, next 49 at $0.05 = $2.45 => $12.55
        assert invoice.total == Decimal("12.55")


class TestInvoiceMetadata:
    """Test that invoices have correct metadata (status, line item details)."""

    def test_invoice_is_draft_status(self, db_session, billing_period):
        """Generated invoices start in DRAFT status."""
        customer = _create_customer(db_session, "meta_cust")
        plan = _create_plan(db_session, "meta_plan")
        metric = _create_metric(db_session, "meta_calls", "Meta Calls")
        sub = _create_subscription(db_session, customer, plan, "meta_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice.status == InvoiceStatus.DRAFT.value
        assert invoice.currency == "USD"
        # SQLite strips timezone info, so compare naive datetimes
        assert invoice.billing_period_start.replace(tzinfo=None) == start.replace(tzinfo=None)
        assert invoice.billing_period_end.replace(tzinfo=None) == end.replace(tzinfo=None)

    def test_line_item_details_correct(self, db_session, billing_period):
        """Line items have correct description and metric_code."""
        customer = _create_customer(db_session, "li_cust")
        plan = _create_plan(db_session, "li_plan")
        metric = _create_metric(db_session, "li_requests", "HTTP Requests")
        sub = _create_subscription(db_session, customer, plan, "li_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "0.01", "unit_price": "0.01"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=100)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert len(invoice.line_items) == 1
        li = invoice.line_items[0]
        # Line items are stored as JSON dicts
        assert li["description"] == "HTTP Requests"
        assert li["metric_code"] == "li_requests"
        assert Decimal(str(li["quantity"])) == Decimal("100")
        assert Decimal(str(li["amount"])) == Decimal("1.00")

    def test_invoice_persisted_in_db(self, db_session, billing_period):
        """Invoice is persisted and retrievable from the database."""
        customer = _create_customer(db_session, "persist_cust")
        plan = _create_plan(db_session, "persist_plan")
        metric = _create_metric(db_session, "persist_calls", "Persist Calls")
        sub = _create_subscription(db_session, customer, plan, "persist_sub")

        charge = Charge(
            plan_id=plan.id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=4)

        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=sub.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        # Retrieve from DB
        from app.repositories.invoice_repository import InvoiceRepository

        repo = InvoiceRepository(db_session)
        retrieved = repo.get_by_id(invoice.id)
        assert retrieved is not None
        assert retrieved.total == Decimal("20")
        assert retrieved.invoice_number is not None
        assert retrieved.invoice_number.startswith("INV-")
