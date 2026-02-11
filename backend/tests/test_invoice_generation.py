"""Unit tests for InvoiceGenerationService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.database import Base, engine, get_db
from app.models.billable_metric import BillableMetric
from app.models.charge import Charge, ChargeModel
from app.models.customer import Customer
from app.models.event import Event
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
