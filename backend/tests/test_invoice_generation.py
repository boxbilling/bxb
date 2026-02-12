"""Unit tests for InvoiceGenerationService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.database import get_db
from app.models.applied_coupon import AppliedCouponStatus
from app.models.billable_metric import BillableMetric
from app.models.charge import Charge, ChargeModel
from app.models.coupon import CouponFrequency, CouponType
from app.models.customer import Customer
from app.models.event import Event
from app.models.fee import FeeType
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.applied_coupon_repository import AppliedCouponRepository
from app.repositories.applied_tax_repository import AppliedTaxRepository
from app.repositories.coupon_repository import CouponRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.tax_repository import TaxRepository
from app.schemas.coupon import CouponCreate
from app.schemas.tax import TaxCreate
from app.services.coupon_service import CouponApplicationService
from app.services.invoice_generation import InvoiceGenerationService
from app.services.tax_service import TaxCalculationService


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
    c = Customer(external_id="inv_gen_cust", name="Invoice Gen Customer", email="test@example.com")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    p = Plan(code="inv_gen_plan", name="Invoice Gen Plan", interval=PlanInterval.MONTHLY.value)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def active_subscription(db_session, customer, plan):
    """Create an active subscription."""
    sub = Subscription(
        external_id="inv_gen_sub",
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
    """Create a pending subscription."""
    sub = Subscription(
        external_id="inv_gen_sub_pending",
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
    """Create a test billable metric."""
    m = BillableMetric(
        code="api_calls",
        name="API Calls",
        aggregation_type="count",
    )
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def billing_period():
    """Return a billing period (start, end)."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 2, 1, tzinfo=UTC)
    return start, end


def _create_events(db_session, customer, metric, billing_period, count=10):
    """Helper to create events within the billing period."""
    start, end = billing_period
    for i in range(count):
        event = Event(
            external_customer_id=customer.external_id,
            code=metric.code,
            transaction_id=f"txn_{uuid4()}",
            timestamp=start + timedelta(hours=i + 1),
            properties={},
        )
        db_session.add(event)
    db_session.commit()


class TestGenerateInvoice:
    """Test the generate_invoice method."""

    def test_subscription_not_found(self, db_session, billing_period):
        """Test error when subscription doesn't exist."""
        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        fake_id = uuid4()
        with pytest.raises(ValueError, match=f"Subscription {fake_id} not found"):
            service.generate_invoice(
                subscription_id=fake_id,
                billing_period_start=start,
                billing_period_end=end,
                external_customer_id="test_cust",
            )

    def test_inactive_subscription(self, db_session, pending_subscription, billing_period):
        """Test error when subscription is not active."""
        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        with pytest.raises(ValueError, match="Can only generate invoices for active subscriptions"):
            service.generate_invoice(
                subscription_id=pending_subscription.id,
                billing_period_start=start,
                billing_period_end=end,
                external_customer_id="inv_gen_cust",
            )

    def test_no_charges(self, db_session, active_subscription, billing_period):
        """Test invoice generation with no charges on the plan."""
        service = InvoiceGenerationService(db_session)
        start, end = billing_period
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id="inv_gen_cust",
        )
        assert invoice is not None
        assert invoice.line_items == []
        assert invoice.total == Decimal(0)

    def test_standard_charge_with_usage(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test invoice generation with a standard charge and usage events."""
        start, end = billing_period
        # Create a standard charge on the plan
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "2.50"},
        )
        db_session.add(charge)
        db_session.commit()

        # Create 10 usage events
        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert invoice is not None
        assert len(invoice.line_items) == 1
        # 10 units * $2.50 = $25.00
        assert invoice.total == Decimal("25")

    def test_multiple_charges(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test invoice generation with multiple charges on one plan."""
        start, end = billing_period

        # Create a second metric
        metric2 = BillableMetric(
            code="storage_gb",
            name="Storage (GB)",
            aggregation_type="count",
        )
        db_session.add(metric2)
        db_session.commit()
        db_session.refresh(metric2)

        # Create two charges
        charge1 = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        charge2 = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric2.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add_all([charge1, charge2])
        db_session.commit()

        # Create events for both metrics
        _create_events(db_session, customer, metric, billing_period, count=5)
        for i in range(3):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric2.code,
                transaction_id=f"txn_storage_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert len(invoice.line_items) == 2
        # 5 * $1 + 3 * $5 = $20
        assert invoice.total == Decimal("20")


class TestCalculateChargeStandard:
    """Test _calculate_charge with STANDARD charge model."""

    def test_standard_basic(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test standard charge basic calculation."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "3.00", "unit_price": "3.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        assert line_item.amount == Decimal("15.00")
        assert line_item.quantity == Decimal("5")
        assert line_item.description == "API Calls"
        assert line_item.metric_code == "api_calls"

    def test_standard_min_price(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test standard charge with min_price applied."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "0.01", "min_price": "50.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=2)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        # 2 * 0.01 = 0.02, but min_price is 50.00
        assert line_item.amount == Decimal("50.00")

    def test_standard_max_price(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test standard charge with max_price applied."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "100.00", "max_price": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        # 5 * 100 = 500, but max_price is 10.00
        assert line_item.amount == Decimal("10.00")

    def test_standard_no_metric(self, db_session, active_subscription, billing_period):
        """Test standard charge without a billable metric (flat fee)."""
        start, end = billing_period
        # billable_metric_id is NOT NULL in DB, so use an in-memory mock charge
        mock_charge = MagicMock(spec=Charge)
        mock_charge.billable_metric_id = None
        mock_charge.charge_model = ChargeModel.STANDARD.value
        mock_charge.properties = {"amount": "99.00"}
        mock_charge.id = uuid4()

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=mock_charge,
            external_customer_id="inv_gen_cust",
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        # usage=1 (flat fee), 1 * 99 = 99
        assert line_item.amount == Decimal("99.00")
        assert line_item.description == "Subscription Fee"
        assert line_item.metric_code is None

    def test_standard_metric_not_found(self, db_session, active_subscription, billing_period):
        """Test standard charge when the billable metric doesn't exist."""
        start, end = billing_period
        fake_metric_id = uuid4()
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=fake_metric_id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id="inv_gen_cust",
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is None


class TestCalculateChargeGraduated:
    """Test _calculate_charge with GRADUATED charge model."""

    def test_graduated_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test graduated charge calculation."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "graduated_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 5,
                        "per_unit_amount": "2.00",
                        "flat_amount": "0",
                    },
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

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        assert line_item.quantity == Decimal("10")
        # First 6 units (0-5 inclusive) at $2 = $12, remaining 4 at $1 = $4 => $16
        assert line_item.amount == Decimal("16.00")


class TestCalculateChargeVolume:
    """Test _calculate_charge with VOLUME charge model."""

    def test_volume_charge(self, db_session, active_subscription, metric, customer, billing_period):
        """Test volume charge calculation."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.VOLUME.value,
            properties={
                "volume_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 5,
                        "per_unit_amount": "3.00",
                        "flat_amount": "0",
                    },
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
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        assert line_item.quantity == Decimal("10")
        # All 10 units fall in second tier at $2 per unit = $20
        assert line_item.amount == Decimal("20.00")


class TestCalculateChargePackage:
    """Test _calculate_charge with PACKAGE charge model."""

    def test_package_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test package charge calculation."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
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
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=7)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        assert line_item.quantity == Decimal("7")
        # 7 units / 5 per package = ceil(7/5) = 2 packages * $10 = $20
        assert line_item.amount == Decimal("20.00")


class TestCalculateChargePercentage:
    """Test _calculate_charge with PERCENTAGE charge model."""

    def test_percentage_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test percentage charge calculation."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
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
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=3)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        assert line_item.quantity == Decimal("1")
        # 10% of $1000 = $100
        assert line_item.amount == Decimal("100")


class TestCalculateChargeGraduatedPercentage:
    """Test _calculate_charge with GRADUATED_PERCENTAGE charge model."""

    def test_graduated_percentage_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test graduated percentage charge calculation."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "base_amount": "1500",
                "graduated_percentage_ranges": [
                    {
                        "from_value": 0,
                        "to_value": 1000,
                        "rate": "5",
                        "flat_amount": "0",
                    },
                    {
                        "from_value": 1000,
                        "to_value": None,
                        "rate": "3",
                        "flat_amount": "0",
                    },
                ],
            },
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=1)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        assert line_item.quantity == Decimal("1")
        # First $1000 at 5% = $50, remaining $500 at 3% = $15 => $65
        assert line_item.amount == Decimal("65")

    def test_graduated_percentage_defaults_to_usage(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test graduated percentage falls back to usage when base_amount not provided."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "graduated_percentage_ranges": [
                    {
                        "from_value": 0,
                        "to_value": None,
                        "rate": "10",
                        "flat_amount": "0",
                    },
                ],
            },
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # Create 5 events — usage = 5 as it's count aggregation
        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        # usage is 5, no base_amount so falls back to usage=5, 10% of 5 = 0.5
        assert line_item.amount == Decimal("0.5")


class TestCalculateChargeCustom:
    """Test _calculate_charge with CUSTOM charge model."""

    def test_custom_charge_with_unit_price(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test custom charge with unit_price."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"unit_price": "7.50"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=4)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        assert line_item.quantity == Decimal("4")
        # 4 events * $7.50 = $30
        assert line_item.amount == Decimal("30.00")

    def test_custom_charge_with_custom_amount(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test custom charge with fixed custom_amount."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"custom_amount": "99.99"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=1)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        assert line_item.amount == Decimal("99.99")


class TestCalculateChargeDynamic:
    """Test _calculate_charge with DYNAMIC charge model."""

    def test_dynamic_charge_basic(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test dynamic charge calculates from event properties."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={
                "price_field": "unit_price",
                "quantity_field": "quantity",
            },
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # Create events with pricing properties
        for i, (price, qty) in enumerate([(10, 2), (5, 3)]):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric.code,
                transaction_id=f"txn_dyn_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"unit_price": str(price), "quantity": str(qty)},
            )
            db_session.add(event)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        # 10*2 + 5*3 = 35
        assert line_item.amount == Decimal("35")

    def test_dynamic_charge_no_events(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test dynamic charge with no events returns zero."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={"price_field": "unit_price", "quantity_field": "quantity"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        # 0 amount and 0 quantity => None
        assert line_item is None


class TestCalculateChargeEdgeCases:
    """Test edge cases for _calculate_charge."""

    def test_zero_amount_and_zero_quantity_returns_none(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that zero amount and zero quantity returns None."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "0"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # No events = 0 usage
        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        # amount=0 and quantity=0 => None
        assert line_item is None

    def test_zero_amount_nonzero_quantity_returns_line_item(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that zero amount but nonzero quantity returns a line item."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "0"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # Create events so usage > 0
        _create_events(db_session, customer, metric, billing_period, count=3)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        # amount=0 but quantity=3, so it is NOT None
        assert line_item is not None
        assert line_item.amount == Decimal("0")
        assert line_item.quantity == Decimal("3")

    def test_empty_properties(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test charge with empty/None properties."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties=None,
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=2)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        # Properties is None => empty dict => unit_price=0, amount=0
        # amount=0, quantity=2 => not None
        assert line_item is not None
        assert line_item.amount == Decimal("0")

    def test_line_item_charge_id_and_metric_code(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that line item has correct charge_id and metric_code."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=1)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        assert line_item.charge_id == charge.id
        assert line_item.metric_code == "api_calls"

    def test_unit_price_field_in_line_item(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that unit_price in line item comes from properties."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00", "unit_price": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=3)

        service = InvoiceGenerationService(db_session)
        line_item = service._calculate_charge(
            charge=charge,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert line_item is not None
        assert line_item.unit_price == Decimal("5.00")

    def test_calculator_returns_none(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that when get_charge_calculator returns None, _calculate_charge returns None."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=1)

        service = InvoiceGenerationService(db_session)
        with patch("app.services.invoice_generation.get_charge_calculator", return_value=None):
            line_item = service._calculate_charge(
                charge=charge,
                external_customer_id=customer.external_id,
                billing_period_start=start,
                billing_period_end=end,
            )
        assert line_item is None

    def test_unknown_charge_model_returns_none(
        self, db_session, active_subscription, billing_period
    ):
        """Test that an unrecognized charge model in the if/elif chain returns None."""
        start, end = billing_period
        # Create a mock charge with an unrecognized charge_model value
        # that still passes ChargeModel() but isn't handled in the if/elif
        mock_charge = MagicMock(spec=Charge)
        mock_charge.billable_metric_id = None
        mock_charge.charge_model = ChargeModel.STANDARD.value
        mock_charge.properties = {"amount": "10.00"}
        mock_charge.id = uuid4()

        service = InvoiceGenerationService(db_session)

        # Mock ChargeModel to return a value not in the if/elif chain
        fake_model = MagicMock()
        fake_model.__eq__ = lambda self, other: False
        fake_model.__hash__ = lambda self: hash("fake")

        with (
            patch("app.services.invoice_generation.ChargeModel", return_value=fake_model),
            patch(
                "app.services.invoice_generation.get_charge_calculator",
                return_value=lambda **kwargs: Decimal("0"),
            ),
        ):
            line_item = service._calculate_charge(
                charge=mock_charge,
                external_customer_id="test",
                billing_period_start=billing_period[0],
                billing_period_end=billing_period[1],
            )
        assert line_item is None

    def test_generate_invoice_skips_none_line_items(
        self, db_session, active_subscription, billing_period
    ):
        """Test that generate_invoice skips charges that return None line items."""
        start, end = billing_period
        # Create a charge with a non-existent metric to trigger None return
        fake_metric_id = uuid4()
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=fake_metric_id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id="inv_gen_cust",
        )
        # The charge returns None because metric doesn't exist, so no line items
        assert invoice is not None
        assert invoice.line_items == []
        assert invoice.total == Decimal(0)


class TestGenerateInvoiceFeeRecords:
    """Test that generate_invoice creates Fee records in the database."""

    def test_fee_records_created_for_single_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that a Fee record is created when generating an invoice with one charge."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "2.50"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        # Verify Fee records were created
        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 1

        fee = fees[0]
        assert fee.fee_type == FeeType.CHARGE.value
        assert fee.amount_cents == Decimal("25")
        assert fee.total_amount_cents == Decimal("25")
        assert fee.units == Decimal("10")
        assert fee.events_count == 10
        assert fee.customer_id == customer.id
        assert fee.subscription_id == active_subscription.id
        assert fee.charge_id == charge.id
        assert fee.invoice_id == invoice.id
        assert fee.description == "API Calls"
        assert fee.metric_code == "api_calls"

    def test_fee_records_created_for_multiple_charges(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that multiple Fee records are created for multiple charges."""
        start, end = billing_period

        metric2 = BillableMetric(
            code="storage_gb",
            name="Storage (GB)",
            aggregation_type="count",
        )
        db_session.add(metric2)
        db_session.commit()
        db_session.refresh(metric2)

        charge1 = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        charge2 = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric2.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add_all([charge1, charge2])
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)
        for i in range(3):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric2.code,
                transaction_id=f"txn_storage_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 2

        # Verify totals match: 5 * $1 + 3 * $5 = $20
        total_from_fees = sum(f.total_amount_cents for f in fees)
        assert total_from_fees == Decimal("20")
        assert invoice.total == Decimal("20")

    def test_no_fee_records_when_no_charges(
        self, db_session, active_subscription, billing_period
    ):
        """Test that no Fee records are created when there are no charges."""
        start, end = billing_period
        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id="inv_gen_cust",
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 0

    def test_no_fee_records_when_charges_return_none(
        self, db_session, active_subscription, billing_period
    ):
        """Test that no Fee records are created when all charges return None."""
        start, end = billing_period
        fake_metric_id = uuid4()
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=fake_metric_id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id="inv_gen_cust",
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 0

    def test_line_items_json_backward_compatibility(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that line_items JSON is still populated for backward compatibility."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "2.50"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=4)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        # line_items JSON should still be populated
        assert len(invoice.line_items) == 1
        line_item = invoice.line_items[0]
        assert line_item["description"] == "API Calls"
        assert Decimal(str(line_item["amount"])) == Decimal("10")
        assert line_item["metric_code"] == "api_calls"

        # And Fee records should match
        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 1
        assert fees[0].amount_cents == Decimal("10")

    def test_fee_events_count_matches_actual_events(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that events_count on the Fee matches the actual number of events."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=7)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 1
        assert fees[0].events_count == 7

    def test_fee_properties_snapshot(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that Fee stores a snapshot of the charge properties."""
        start, end = billing_period
        charge_props = {"amount": "3.00", "unit_price": "3.00"}
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties=charge_props,
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=2)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 1
        assert fees[0].properties == charge_props


class TestCalculateChargeFee:
    """Test the _calculate_charge_fee method directly."""

    def test_standard_fee_basic(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test standard charge fee calculation."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "3.00", "unit_price": "3.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        assert fee_data.amount_cents == Decimal("15.00")
        assert fee_data.units == Decimal("5")
        assert fee_data.events_count == 5
        assert fee_data.description == "API Calls"
        assert fee_data.metric_code == "api_calls"
        assert fee_data.customer_id == customer.id
        assert fee_data.subscription_id == active_subscription.id
        assert fee_data.charge_id == charge.id

    def test_fee_no_metric(self, db_session, active_subscription, customer, billing_period):
        """Test fee calculation without a billable metric (flat fee)."""
        start, end = billing_period
        mock_charge = MagicMock(spec=Charge)
        mock_charge.billable_metric_id = None
        mock_charge.charge_model = ChargeModel.STANDARD.value
        mock_charge.properties = {"amount": "99.00"}
        mock_charge.id = uuid4()

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=mock_charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id="inv_gen_cust",
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        assert fee_data.amount_cents == Decimal("99.00")
        assert fee_data.description == "Subscription Fee"
        assert fee_data.metric_code is None
        assert fee_data.events_count == 0

    def test_fee_metric_not_found(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test fee calculation when metric doesn't exist."""
        start, end = billing_period
        fake_metric_id = uuid4()
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=fake_metric_id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id="inv_gen_cust",
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is None

    def test_fee_calculator_returns_none(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation when calculator returns None."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=1)

        service = InvoiceGenerationService(db_session)
        with patch("app.services.invoice_generation.get_charge_calculator", return_value=None):
            fee_data = service._calculate_charge_fee(
                charge=charge,
                customer_id=customer.id,
                subscription_id=active_subscription.id,
                external_customer_id=customer.external_id,
                billing_period_start=start,
                billing_period_end=end,
            )
        assert fee_data is None

    def test_fee_zero_amount_and_quantity(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation when both amount and quantity are zero."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "0"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # No events = 0 usage
        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is None

    def test_fee_unknown_charge_model(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test fee calculation with unrecognized charge model."""
        start, end = billing_period
        mock_charge = MagicMock(spec=Charge)
        mock_charge.billable_metric_id = None
        mock_charge.charge_model = ChargeModel.STANDARD.value
        mock_charge.properties = {"amount": "10.00"}
        mock_charge.id = uuid4()

        service = InvoiceGenerationService(db_session)

        fake_model = MagicMock()
        fake_model.__eq__ = lambda self, other: False
        fake_model.__hash__ = lambda self: hash("fake")

        with (
            patch("app.services.invoice_generation.ChargeModel", return_value=fake_model),
            patch(
                "app.services.invoice_generation.get_charge_calculator",
                return_value=lambda **kwargs: Decimal("0"),
            ),
        ):
            fee_data = service._calculate_charge_fee(
                charge=mock_charge,
                customer_id=customer.id,
                subscription_id=active_subscription.id,
                external_customer_id="test",
                billing_period_start=start,
                billing_period_end=end,
            )
        assert fee_data is None

    def test_fee_graduated_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation with graduated charge model."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "graduated_ranges": [
                    {"from_value": 0, "to_value": 5, "per_unit_amount": "2.00", "flat_amount": "0"},
                    {"from_value": 5, "to_value": None, "per_unit_amount": "1.00", "flat_amount": "0"},
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        assert fee_data.units == Decimal("10")
        assert fee_data.amount_cents == Decimal("16.00")
        assert fee_data.events_count == 10

    def test_fee_percentage_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation with percentage charge model."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
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
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=3)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        assert fee_data.units == Decimal("1")
        assert fee_data.amount_cents == Decimal("100")
        assert fee_data.events_count == 3

    def test_fee_graduated_percentage_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation with graduated percentage charge model."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
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
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=1)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        assert fee_data.units == Decimal("1")
        assert fee_data.amount_cents == Decimal("65")

    def test_fee_empty_properties(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation with empty/None properties."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties=None,
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=2)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        assert fee_data.amount_cents == Decimal("0")

    def test_fee_min_price(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation with min_price applied."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "0.01", "min_price": "50.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=2)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        assert fee_data.amount_cents == Decimal("50.00")

    def test_fee_max_price(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation with max_price applied."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "100.00", "max_price": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        assert fee_data.amount_cents == Decimal("10.00")

    def test_fee_custom_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation with custom charge model."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"unit_price": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=3)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        assert fee_data.units == Decimal("3")
        assert fee_data.amount_cents == Decimal("15.00")
        assert fee_data.events_count == 3

    def test_fee_custom_charge_with_custom_amount(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation with custom charge model using custom_amount."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"custom_amount": "42.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=2)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        assert fee_data.amount_cents == Decimal("42.00")

    def test_fee_dynamic_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation with dynamic charge model."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={"price_field": "unit_price", "quantity_field": "quantity"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # Create events with pricing properties
        for i, (price, qty) in enumerate([(20, 1), (10, 3)]):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric.code,
                transaction_id=f"txn_fee_dyn_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"unit_price": str(price), "quantity": str(qty)},
            )
            db_session.add(event)
        db_session.commit()

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert fee_data is not None
        # 20*1 + 10*3 = 50
        assert fee_data.amount_cents == Decimal("50")
        assert fee_data.events_count == 2
        assert fee_data.units == Decimal("2")

    def test_fee_dynamic_charge_no_events(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fee calculation with dynamic charge model and no events."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={"price_field": "unit_price", "quantity_field": "quantity"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        service = InvoiceGenerationService(db_session)
        fee_data = service._calculate_charge_fee(
            charge=charge,
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        # 0 amount and 0 quantity => None
        assert fee_data is None


def _create_coupon(db_session, code, coupon_type, frequency, **kwargs):
    """Helper to create a coupon via repository."""
    repo = CouponRepository(db_session)
    return repo.create(
        CouponCreate(
            code=code,
            name=f"Coupon {code}",
            coupon_type=coupon_type,
            frequency=frequency,
            **kwargs,
        )
    )


def _apply_coupon(db_session, coupon, customer, **overrides):
    """Helper to apply a coupon to a customer."""
    service = CouponApplicationService(db_session)
    return service.apply_coupon_to_customer(
        coupon_code=str(coupon.code),
        customer_id=customer.id,
        **overrides,
    )


class TestCouponDiscountIntegration:
    """Test coupon discount integration in invoice generation."""

    def test_fixed_amount_coupon_deducted_from_total(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that a fixed amount coupon reduces the invoice total."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        # Create and apply a $25 fixed coupon
        coupon = _create_coupon(
            db_session,
            code="FIXED25",
            coupon_type=CouponType.FIXED_AMOUNT,
            frequency=CouponFrequency.FOREVER,
            amount_cents=Decimal("25"),
            amount_currency="USD",
        )
        _apply_coupon(db_session, coupon, customer)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Subtotal: 10 * $10 = $100, coupon: $25, total: $75
        assert invoice.subtotal == Decimal("100")
        assert invoice.coupons_amount_cents == Decimal("25")
        assert invoice.total == Decimal("75")

    def test_percentage_coupon_deducted_from_total(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that a percentage coupon reduces the invoice total."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        # Create and apply a 20% coupon
        coupon = _create_coupon(
            db_session,
            code="PCT20",
            coupon_type=CouponType.PERCENTAGE,
            frequency=CouponFrequency.FOREVER,
            percentage_rate=Decimal("20"),
        )
        _apply_coupon(db_session, coupon, customer)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Subtotal: 10 * $5 = $50, coupon: 20% of $50 = $10, total: $40
        assert invoice.subtotal == Decimal("50")
        assert invoice.coupons_amount_cents == Decimal("10")
        assert invoice.total == Decimal("40")

    def test_fixed_coupon_capped_at_subtotal(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that a fixed coupon cannot exceed the subtotal."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "2.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        # Create and apply a $100 coupon against $10 subtotal
        coupon = _create_coupon(
            db_session,
            code="FIXED100",
            coupon_type=CouponType.FIXED_AMOUNT,
            frequency=CouponFrequency.FOREVER,
            amount_cents=Decimal("100"),
            amount_currency="USD",
        )
        _apply_coupon(db_session, coupon, customer)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Subtotal: 5 * $2 = $10, coupon: $100 capped at $10, total: $0
        assert invoice.subtotal == Decimal("10")
        assert invoice.coupons_amount_cents == Decimal("10")
        assert invoice.total == Decimal("0")

    def test_multiple_coupons_stacked(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that multiple coupons are applied sequentially."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        # Apply a $15 fixed coupon + 10% percentage coupon
        coupon1 = _create_coupon(
            db_session,
            code="FIXED15",
            coupon_type=CouponType.FIXED_AMOUNT,
            frequency=CouponFrequency.FOREVER,
            amount_cents=Decimal("15"),
            amount_currency="USD",
        )
        _apply_coupon(db_session, coupon1, customer)

        coupon2 = _create_coupon(
            db_session,
            code="PCT10",
            coupon_type=CouponType.PERCENTAGE,
            frequency=CouponFrequency.FOREVER,
            percentage_rate=Decimal("10"),
        )
        _apply_coupon(db_session, coupon2, customer)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Subtotal: $100, first coupon: $15, remaining: $85
        # Second coupon: 10% of $85 = $8.50, total discount: $23.50
        assert invoice.subtotal == Decimal("100")
        assert invoice.coupons_amount_cents == Decimal("23.5")
        assert invoice.total == Decimal("76.5")

    def test_once_frequency_coupon_consumed_after_invoice(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that a 'once' frequency coupon is terminated after use."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        coupon = _create_coupon(
            db_session,
            code="ONCE10",
            coupon_type=CouponType.FIXED_AMOUNT,
            frequency=CouponFrequency.ONCE,
            amount_cents=Decimal("10"),
            amount_currency="USD",
        )
        applied = _apply_coupon(db_session, coupon, customer)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert invoice.coupons_amount_cents == Decimal("10")
        assert invoice.total == Decimal("40")

        # Verify the applied coupon was terminated
        applied_coupon_repo = AppliedCouponRepository(db_session)
        updated_applied = applied_coupon_repo.get_by_id(applied.id)
        assert updated_applied is not None
        assert updated_applied.status == AppliedCouponStatus.TERMINATED.value

    def test_recurring_coupon_decremented_after_invoice(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that a 'recurring' frequency coupon is decremented after use."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        coupon = _create_coupon(
            db_session,
            code="RECUR3",
            coupon_type=CouponType.FIXED_AMOUNT,
            frequency=CouponFrequency.RECURRING,
            frequency_duration=3,
            amount_cents=Decimal("5"),
            amount_currency="USD",
        )
        applied = _apply_coupon(db_session, coupon, customer)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert invoice.coupons_amount_cents == Decimal("5")
        assert invoice.total == Decimal("45")

        # Verify remaining decremented from 3 to 2
        applied_coupon_repo = AppliedCouponRepository(db_session)
        updated_applied = applied_coupon_repo.get_by_id(applied.id)
        assert updated_applied is not None
        assert updated_applied.frequency_duration_remaining == 2
        assert updated_applied.status == AppliedCouponStatus.ACTIVE.value

    def test_no_coupon_applied_when_zero_subtotal(
        self, db_session, active_subscription, billing_period, customer
    ):
        """Test that coupon is not applied when invoice subtotal is zero."""
        start, end = billing_period

        # Create and apply a coupon (but no charges = zero subtotal)
        coupon = _create_coupon(
            db_session,
            code="NOOP",
            coupon_type=CouponType.FIXED_AMOUNT,
            frequency=CouponFrequency.ONCE,
            amount_cents=Decimal("50"),
            amount_currency="USD",
        )
        _apply_coupon(db_session, coupon, customer)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert invoice.subtotal == Decimal("0")
        assert invoice.coupons_amount_cents == Decimal("0")
        assert invoice.total == Decimal("0")

        # Verify the coupon was NOT consumed (still active)
        applied_coupon_repo = AppliedCouponRepository(db_session)
        active_coupons = applied_coupon_repo.get_active_by_customer_id(customer.id)
        assert len(active_coupons) == 1

    def test_no_discount_when_no_coupons(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test invoice generation without any coupons applied."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert invoice.subtotal == Decimal("50")
        assert invoice.coupons_amount_cents == Decimal("0")
        assert invoice.total == Decimal("50")

    def test_forever_coupon_remains_active_after_invoice(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that a 'forever' frequency coupon stays active after use."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        coupon = _create_coupon(
            db_session,
            code="FOREVER10",
            coupon_type=CouponType.FIXED_AMOUNT,
            frequency=CouponFrequency.FOREVER,
            amount_cents=Decimal("10"),
            amount_currency="USD",
        )
        applied = _apply_coupon(db_session, coupon, customer)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert invoice.coupons_amount_cents == Decimal("10")
        assert invoice.total == Decimal("40")

        # Forever coupon should remain active
        applied_coupon_repo = AppliedCouponRepository(db_session)
        updated_applied = applied_coupon_repo.get_by_id(applied.id)
        assert updated_applied is not None
        assert updated_applied.status == AppliedCouponStatus.ACTIVE.value


class TestTaxIntegration:
    """Test tax calculation integration in invoice generation."""

    def test_organization_default_tax_applied_to_fees(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that organization default taxes are applied to invoice fees."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        # Create an organization-level tax (10%)
        tax_repo = TaxRepository(db_session)
        tax_repo.create(
            TaxCreate(
                code="ORG_TAX_INV",
                name="Org Tax 10%",
                rate=Decimal("0.1000"),
                applied_to_organization=True,
            )
        )

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Subtotal: 10 * $10 = $100, tax: 10% of $100 = $10
        assert invoice.subtotal == Decimal("100")
        assert invoice.tax_amount == Decimal("10")
        assert invoice.total == Decimal("110")

        # Verify fee-level tax amounts
        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 1
        assert fees[0].taxes_amount_cents == Decimal("10")
        assert fees[0].total_amount_cents == Decimal("110")

    def test_customer_level_tax_applied(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that customer-level taxes override organization defaults."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=4)

        # Create org tax and customer-specific tax
        tax_repo = TaxRepository(db_session)
        tax_repo.create(
            TaxCreate(
                code="ORG_TAX_CUST_OVERRIDE",
                name="Org Default",
                rate=Decimal("0.1000"),
                applied_to_organization=True,
            )
        )
        tax_repo.create(
            TaxCreate(
                code="CUST_TAX_20",
                name="Customer Tax 20%",
                rate=Decimal("0.2000"),
            )
        )

        # Apply the customer tax
        tax_service = TaxCalculationService(db_session)
        tax_service.apply_tax_to_entity("CUST_TAX_20", "customer", customer.id)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Subtotal: 4 * $5 = $20, customer tax: 20% of $20 = $4
        assert invoice.subtotal == Decimal("20")
        assert invoice.tax_amount == Decimal("4")
        assert invoice.total == Decimal("24")

    def test_charge_level_tax_applied(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that charge-level taxes override plan/customer/org defaults."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        _create_events(db_session, customer, metric, billing_period, count=5)

        # Create org tax and charge-specific tax
        tax_repo = TaxRepository(db_session)
        tax_repo.create(
            TaxCreate(
                code="ORG_TAX_CHARGE_OVERRIDE",
                name="Org Default",
                rate=Decimal("0.1000"),
                applied_to_organization=True,
            )
        )
        tax_repo.create(
            TaxCreate(
                code="CHARGE_TAX_5",
                name="Charge Tax 5%",
                rate=Decimal("0.0500"),
            )
        )

        # Apply tax to the specific charge
        tax_service = TaxCalculationService(db_session)
        tax_service.apply_tax_to_entity("CHARGE_TAX_5", "charge", charge.id)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Subtotal: 5 * $10 = $50, charge tax: 5% of $50 = $2.50
        assert invoice.subtotal == Decimal("50")
        assert invoice.tax_amount == Decimal("2.5")
        assert invoice.total == Decimal("52.5")

    def test_multiple_taxes_combined(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that multiple taxes on same entity are summed."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        # Create two customer-level taxes
        tax_repo = TaxRepository(db_session)
        tax_repo.create(
            TaxCreate(
                code="MULTI_TAX_1",
                name="State Tax 5%",
                rate=Decimal("0.0500"),
            )
        )
        tax_repo.create(
            TaxCreate(
                code="MULTI_TAX_2",
                name="City Tax 3%",
                rate=Decimal("0.0300"),
            )
        )

        tax_service = TaxCalculationService(db_session)
        tax_service.apply_tax_to_entity("MULTI_TAX_1", "customer", customer.id)
        tax_service.apply_tax_to_entity("MULTI_TAX_2", "customer", customer.id)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Subtotal: 10 * $10 = $100, taxes: (5% + 3%) of $100 = $8
        assert invoice.subtotal == Decimal("100")
        assert invoice.tax_amount == Decimal("8")
        assert invoice.total == Decimal("108")

        # Verify AppliedTax records were created for the fee
        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 1
        applied_tax_repo = AppliedTaxRepository(db_session)
        applied = applied_tax_repo.get_by_taxable("fee", fees[0].id)
        assert len(applied) == 2

    def test_tax_with_coupon_discount(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test tax calculation combined with coupon discounts."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        # Create a 10% organization tax
        tax_repo = TaxRepository(db_session)
        tax_repo.create(
            TaxCreate(
                code="ORG_TAX_COUPON",
                name="Org Tax 10%",
                rate=Decimal("0.1000"),
                applied_to_organization=True,
            )
        )

        # Create and apply a $20 coupon
        coupon = _create_coupon(
            db_session,
            code="TAXCOUPON20",
            coupon_type=CouponType.FIXED_AMOUNT,
            frequency=CouponFrequency.FOREVER,
            amount_cents=Decimal("20"),
            amount_currency="USD",
        )
        _apply_coupon(db_session, coupon, customer)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Subtotal: 10 * $10 = $100
        # Tax: 10% of $100 = $10 (tax on pre-coupon subtotal)
        # Coupon: $20
        # Total: $100 - $20 + $10 = $90
        assert invoice.subtotal == Decimal("100")
        assert invoice.coupons_amount_cents == Decimal("20")
        assert invoice.tax_amount == Decimal("10")
        assert invoice.total == Decimal("90")

    def test_no_taxes_when_no_taxes_configured(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that invoice works correctly when no taxes are configured."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # No taxes configured, so tax_amount should remain 0
        assert invoice.subtotal == Decimal("50")
        assert invoice.tax_amount == Decimal("0")
        assert invoice.total == Decimal("50")

    def test_tax_on_multiple_fees(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test tax applied across multiple fees on one invoice."""
        start, end = billing_period

        metric2 = BillableMetric(
            code="tax_storage_gb",
            name="Tax Storage (GB)",
            aggregation_type="count",
        )
        db_session.add(metric2)
        db_session.commit()
        db_session.refresh(metric2)

        charge1 = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "2.00"},
        )
        charge2 = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric2.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add_all([charge1, charge2])
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)
        for i in range(4):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric2.code,
                transaction_id=f"txn_tax_storage_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        # Create a 20% organization tax
        tax_repo = TaxRepository(db_session)
        tax_repo.create(
            TaxCreate(
                code="ORG_TAX_MULTI_FEE",
                name="Org Tax 20%",
                rate=Decimal("0.2000"),
                applied_to_organization=True,
            )
        )

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Fee 1: 5 * $2 = $10, tax = $2
        # Fee 2: 4 * $5 = $20, tax = $4
        # Subtotal: $30, total tax: $6, total: $36
        assert invoice.subtotal == Decimal("30")
        assert invoice.tax_amount == Decimal("6")
        assert invoice.total == Decimal("36")

        # Verify each fee has tax applied
        fee_repo = FeeRepository(db_session)
        fees = fee_repo.get_by_invoice_id(UUID(str(invoice.id)))
        assert len(fees) == 2
        fee_taxes = [Decimal(str(f.taxes_amount_cents)) for f in fees]
        assert sorted(fee_taxes) == [Decimal("2"), Decimal("4")]

    def test_plan_level_tax_applied(
        self, db_session, active_subscription, metric, customer, billing_period, plan
    ):
        """Test that plan-level taxes override customer/org defaults."""
        start, end = billing_period
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        # Create org default and plan-specific tax
        tax_repo = TaxRepository(db_session)
        tax_repo.create(
            TaxCreate(
                code="ORG_TAX_PLAN_OVERRIDE",
                name="Org Default 10%",
                rate=Decimal("0.1000"),
                applied_to_organization=True,
            )
        )
        tax_repo.create(
            TaxCreate(
                code="PLAN_TAX_15",
                name="Plan Tax 15%",
                rate=Decimal("0.1500"),
            )
        )

        # Apply tax at plan level
        tax_service = TaxCalculationService(db_session)
        tax_service.apply_tax_to_entity("PLAN_TAX_15", "plan", plan.id)

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        # Subtotal: 10 * $10 = $100, plan tax 15% should override org 10%: $15
        assert invoice.subtotal == Decimal("100")
        assert invoice.tax_amount == Decimal("15")
        assert invoice.total == Decimal("115")

    def test_no_tax_on_zero_subtotal_invoice(
        self, db_session, active_subscription, billing_period
    ):
        """Test that no taxes are applied when invoice has no fees."""
        start, end = billing_period

        # Create org tax but no charges (zero subtotal)
        tax_repo = TaxRepository(db_session)
        tax_repo.create(
            TaxCreate(
                code="ORG_TAX_ZERO",
                name="Org Tax 10%",
                rate=Decimal("0.1000"),
                applied_to_organization=True,
            )
        )

        service = InvoiceGenerationService(db_session)
        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id="inv_gen_cust",
        )
        # No fees, so no taxes
        assert invoice.subtotal == Decimal("0")
        assert invoice.tax_amount == Decimal("0")
        assert invoice.total == Decimal("0")
