"""Tests for ProgressiveBillingService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.core.database import get_db
from app.models.billable_metric import BillableMetric
from app.models.charge import Charge, ChargeModel
from app.models.customer import Customer
from app.models.event import Event
from app.models.invoice import InvoiceType
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.invoice_repository import InvoiceRepository
from app.services.invoice_generation import InvoiceGenerationService
from app.services.progressive_billing_service import ProgressiveBillingService


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
    c = Customer(
        external_id="prog_bill_cust",
        name="Progressive Billing Customer",
        email="prog@test.com",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    p = Plan(
        code="prog_bill_plan",
        name="Progressive Billing Plan",
        interval=PlanInterval.MONTHLY.value,
    )
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def active_subscription(db_session, customer, plan):
    """Create an active subscription."""
    sub = Subscription(
        external_id="prog_bill_sub",
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
        external_id="prog_bill_sub_pending",
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
        code="prog_bill_api_calls",
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
            transaction_id=f"txn_prog_{uuid4()}",
            timestamp=start + timedelta(hours=i + 1),
            properties={},
        )
        db_session.add(event)
    db_session.commit()


class TestGenerateProgressiveInvoice:
    """Test generate_progressive_invoice method."""

    def test_subscription_not_found(self, db_session, billing_period):
        """Test error when subscription doesn't exist."""
        service = ProgressiveBillingService(db_session)
        start, end = billing_period
        fake_id = uuid4()
        with pytest.raises(ValueError, match=f"Subscription {fake_id} not found"):
            service.generate_progressive_invoice(
                subscription_id=fake_id,
                threshold_id=uuid4(),
                billing_period_start=start,
                billing_period_end=end,
                external_customer_id="test_cust",
            )

    def test_inactive_subscription(self, db_session, pending_subscription, billing_period):
        """Test error when subscription is not active."""
        service = ProgressiveBillingService(db_session)
        start, end = billing_period
        with pytest.raises(
            ValueError,
            match="Can only generate progressive invoices for active subscriptions",
        ):
            service.generate_progressive_invoice(
                subscription_id=pending_subscription.id,
                threshold_id=uuid4(),
                billing_period_start=start,
                billing_period_end=end,
                external_customer_id="prog_bill_cust",
            )

    def test_basic_progressive_invoice(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test generating a progressive invoice when a threshold is crossed."""
        start, end = billing_period

        # Create a standard charge: $5 per unit
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        # Create 10 events => 10 * $5 = $50 usage
        _create_events(db_session, customer, metric, billing_period, count=10)

        service = ProgressiveBillingService(db_session)
        invoice = service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert invoice is not None
        assert invoice.invoice_type == InvoiceType.PROGRESSIVE_BILLING.value
        assert invoice.total == Decimal("50")
        assert invoice.subscription_id == active_subscription.id
        assert len(invoice.line_items) == 1

    def test_progressive_invoice_no_usage(self, db_session, active_subscription, billing_period):
        """Test progressive invoice with no usage results in zero amount."""
        start, end = billing_period
        service = ProgressiveBillingService(db_session)

        invoice = service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id="prog_bill_cust",
        )

        assert invoice is not None
        assert invoice.invoice_type == InvoiceType.PROGRESSIVE_BILLING.value
        assert invoice.total == Decimal("0")
        assert invoice.line_items == []

    def test_multiple_progressive_invoices_incremental(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test multiple progressive invoices produce incremental amounts."""
        start, end = billing_period

        # Create a standard charge: $10 per unit
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        service = ProgressiveBillingService(db_session)

        # Phase 1: 5 events => $50 usage, first progressive invoice = $50
        _create_events(db_session, customer, metric, billing_period, count=5)
        invoice1 = service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert invoice1.total == Decimal("50")

        # Phase 2: 5 more events => $100 total usage
        # Second progressive invoice = $100 - $50 (already billed) = $50
        for i in range(5):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric.code,
                transaction_id=f"txn_prog2_{uuid4()}",
                timestamp=start + timedelta(hours=20 + i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        invoice2 = service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert invoice2.total == Decimal("50")

    def test_progressive_invoice_subtracts_voided(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that voided progressive invoices are not subtracted."""
        start, end = billing_period

        # Create a standard charge: $10 per unit
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = ProgressiveBillingService(db_session)

        # Generate first progressive invoice for $100
        invoice1 = service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert invoice1.total == Decimal("100")

        # Void the first invoice
        invoice_repo = InvoiceRepository(db_session)
        invoice_repo.void(UUID(str(invoice1.id)))

        # Generate second progressive invoice — voided invoice should not be subtracted
        invoice2 = service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert invoice2.total == Decimal("100")


class TestCalculateProgressiveBillingCredit:
    """Test calculate_progressive_billing_credit method."""

    def test_no_progressive_invoices(self, db_session, active_subscription, billing_period):
        """Test credit is zero when no progressive invoices exist."""
        start, end = billing_period
        service = ProgressiveBillingService(db_session)

        credit = service.calculate_progressive_billing_credit(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert credit == Decimal("0")

    def test_credit_sums_progressive_invoices(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test credit correctly sums multiple progressive invoices."""
        start, end = billing_period

        # Create a standard charge: $10 per unit
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        service = ProgressiveBillingService(db_session)

        # Generate first progressive invoice: 5 events => $50
        _create_events(db_session, customer, metric, billing_period, count=5)
        service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        # Generate second progressive invoice: 5 more events => $50 incremental
        for i in range(5):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric.code,
                transaction_id=f"txn_cred_{uuid4()}",
                timestamp=start + timedelta(hours=20 + i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        # Total credit should be $50 + $50 = $100
        credit = service.calculate_progressive_billing_credit(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert credit == Decimal("100")

    def test_credit_excludes_voided_invoices(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that voided progressive invoices are excluded from credit."""
        start, end = billing_period

        # Create a standard charge: $10 per unit
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "10.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = ProgressiveBillingService(db_session)
        invoice = service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        # Void it
        invoice_repo = InvoiceRepository(db_session)
        invoice_repo.void(UUID(str(invoice.id)))

        credit = service.calculate_progressive_billing_credit(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert credit == Decimal("0")

    def test_credit_only_for_matching_period(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that credit only includes invoices matching the billing period."""
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

        service = ProgressiveBillingService(db_session)
        service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        # Query with a different period should return 0
        different_start = datetime(2024, 2, 1, tzinfo=UTC)
        different_end = datetime(2024, 3, 1, tzinfo=UTC)
        credit = service.calculate_progressive_billing_credit(
            subscription_id=active_subscription.id,
            billing_period_start=different_start,
            billing_period_end=different_end,
        )
        assert credit == Decimal("0")


class TestEndOfPeriodInvoiceWithProgressiveCredits:
    """Test that end-of-period invoices correctly subtract progressive billing credits."""

    def test_final_invoice_subtracts_progressive_credits(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that a final end-of-period invoice subtracts progressive billing amounts."""
        start, end = billing_period

        # Create a standard charge: $5 per unit
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        # Create 10 events => $50 total usage
        _create_events(db_session, customer, metric, billing_period, count=10)

        # Generate a progressive invoice for $50 (all current usage)
        prog_service = ProgressiveBillingService(db_session)
        prog_invoice = prog_service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert prog_invoice.total == Decimal("50")

        # Now generate the end-of-period invoice
        # Usage is still $50 but progressive credit is $50, so total = $0
        invoice_service = InvoiceGenerationService(db_session)
        final_invoice = invoice_service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert final_invoice.progressive_billing_credit_amount_cents == Decimal("50")
        assert final_invoice.total == Decimal("0")
        # Subtotal should still reflect the full charge amount
        assert final_invoice.subtotal == Decimal("50")

    def test_final_invoice_partial_progressive_credit(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test final invoice when progressive credits are less than total usage."""
        start, end = billing_period

        # Create a standard charge: $5 per unit
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        # Phase 1: 5 events => $25 progressive invoice
        _create_events(db_session, customer, metric, billing_period, count=5)

        prog_service = ProgressiveBillingService(db_session)
        prog_invoice = prog_service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )
        assert prog_invoice.total == Decimal("25")

        # Phase 2: 5 more events added => $50 total usage
        for i in range(5):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric.code,
                transaction_id=f"txn_final_{uuid4()}",
                timestamp=start + timedelta(hours=20 + i),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        # End-of-period invoice: $50 usage - $25 progressive credit = $25
        invoice_service = InvoiceGenerationService(db_session)
        final_invoice = invoice_service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert final_invoice.progressive_billing_credit_amount_cents == Decimal("25")
        assert final_invoice.total == Decimal("25")
        assert final_invoice.subtotal == Decimal("50")

    def test_final_invoice_no_progressive_credits(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test final invoice with no progressive billing credits is unchanged."""
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

        invoice_service = InvoiceGenerationService(db_session)
        final_invoice = invoice_service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        assert final_invoice.progressive_billing_credit_amount_cents == Decimal("0")
        assert final_invoice.total == Decimal("50")
        assert final_invoice.subtotal == Decimal("50")


class TestInvoiceTypeField:
    """Test that the invoice_type field is correctly set."""

    def test_progressive_billing_invoice_type(
        self, db_session, active_subscription, billing_period
    ):
        """Test that progressive invoices have correct type."""
        start, end = billing_period
        service = ProgressiveBillingService(db_session)

        invoice = service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id="prog_bill_cust",
        )

        assert invoice.invoice_type == InvoiceType.PROGRESSIVE_BILLING.value

    def test_regular_invoice_type(self, db_session, active_subscription, billing_period):
        """Test that regular invoices have subscription type."""
        start, end = billing_period
        service = InvoiceGenerationService(db_session)

        invoice = service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id="prog_bill_cust",
        )

        assert invoice.invoice_type == InvoiceType.SUBSCRIPTION.value


class TestGetProgressiveBillingInvoices:
    """Test the repository method for fetching progressive billing invoices."""

    def test_get_progressive_billing_invoices(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test fetching progressive billing invoices."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        prog_service = ProgressiveBillingService(db_session)
        prog_service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        # Also create a regular invoice
        inv_service = InvoiceGenerationService(db_session)
        inv_service.generate_invoice(
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        invoice_repo = InvoiceRepository(db_session)
        prog_invoices = invoice_repo.get_progressive_billing_invoices(
            subscription_id=UUID(str(active_subscription.id)),
            billing_period_start=start,
            billing_period_end=end,
        )

        # Should only include the progressive invoice, not the regular one
        assert len(prog_invoices) == 1
        assert prog_invoices[0].invoice_type == InvoiceType.PROGRESSIVE_BILLING.value

    def test_get_progressive_billing_invoices_empty(
        self, db_session, active_subscription, billing_period
    ):
        """Test returns empty list when no progressive invoices exist."""
        start, end = billing_period

        invoice_repo = InvoiceRepository(db_session)
        prog_invoices = invoice_repo.get_progressive_billing_invoices(
            subscription_id=UUID(str(active_subscription.id)),
            billing_period_start=start,
            billing_period_end=end,
        )

        assert prog_invoices == []

    def test_get_progressive_billing_invoices_excludes_voided(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that voided progressive invoices are excluded."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        prog_service = ProgressiveBillingService(db_session)
        invoice = prog_service.generate_progressive_invoice(
            subscription_id=active_subscription.id,
            threshold_id=uuid4(),
            billing_period_start=start,
            billing_period_end=end,
            external_customer_id=customer.external_id,
        )

        # Void the invoice
        invoice_repo = InvoiceRepository(db_session)
        invoice_repo.void(UUID(str(invoice.id)))

        prog_invoices = invoice_repo.get_progressive_billing_invoices(
            subscription_id=UUID(str(active_subscription.id)),
            billing_period_start=start,
            billing_period_end=end,
        )

        assert prog_invoices == []
