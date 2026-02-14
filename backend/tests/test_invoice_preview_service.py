"""Unit tests for InvoicePreviewService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import get_db
from app.models.applied_coupon import AppliedCouponStatus
from app.models.billable_metric import BillableMetric
from app.models.charge import Charge, ChargeModel
from app.models.commitment import Commitment
from app.models.coupon import CouponFrequency, CouponType
from app.models.customer import Customer
from app.models.event import Event
from app.models.fee import Fee
from app.models.invoice import Invoice
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.coupon_repository import CouponRepository
from app.repositories.tax_repository import TaxRepository
from app.schemas.coupon import CouponCreate
from app.schemas.tax import TaxCreate
from app.services.coupon_service import CouponApplicationService
from app.services.invoice_preview_service import InvoicePreviewService
from tests.conftest import DEFAULT_ORG_ID


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
    c = Customer(external_id="preview_cust", name="Preview Customer", email="preview@example.com")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    p = Plan(code="preview_plan", name="Preview Plan", interval=PlanInterval.MONTHLY.value)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture
def active_subscription(db_session, customer, plan):
    """Create an active subscription."""
    sub = Subscription(
        external_id="preview_sub",
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
        external_id="preview_sub_pending",
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
        code="preview_api_calls",
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
            transaction_id=f"txn_preview_{uuid4()}",
            timestamp=start + timedelta(hours=i + 1),
            properties={},
        )
        db_session.add(event)
    db_session.commit()


class TestPreviewInvoice:
    """Test the preview_invoice method."""

    def test_subscription_not_found(self, db_session, billing_period):
        """Test error when subscription doesn't exist."""
        service = InvoicePreviewService(db_session)
        start, end = billing_period
        fake_id = uuid4()
        with pytest.raises(ValueError, match=f"Subscription {fake_id} not found"):
            service.preview_invoice(
                subscription_id=fake_id,
                external_customer_id="test_cust",
                billing_period_start=start,
                billing_period_end=end,
            )

    def test_inactive_subscription(self, db_session, pending_subscription, billing_period):
        """Test error when subscription is not active."""
        service = InvoicePreviewService(db_session)
        start, end = billing_period
        with pytest.raises(ValueError, match="Can only preview invoices for active subscriptions"):
            service.preview_invoice(
                subscription_id=pending_subscription.id,
                external_customer_id="preview_cust",
                billing_period_start=start,
                billing_period_end=end,
            )

    def test_preview_with_multiple_charges(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test preview with multiple charges on one plan."""
        start, end = billing_period

        metric2 = BillableMetric(
            code="preview_storage_gb",
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

        # Create events for both metrics
        _create_events(db_session, customer, metric, billing_period, count=5)
        for i in range(3):
            event = Event(
                external_customer_id=customer.external_id,
                code=metric2.code,
                transaction_id=f"txn_preview_storage_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={},
            )
            db_session.add(event)
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 2
        # 5 units * $1.00 = $5.00
        # 3 units * $5.00 = $15.00
        assert result.subtotal == Decimal("20")
        assert result.total == Decimal("20")
        assert result.currency == "USD"

        # Verify fee details
        fee_amounts = sorted([f.amount_cents for f in result.fees])
        assert fee_amounts == [Decimal("5"), Decimal("15")]

        # Verify charge_model is populated
        for fee in result.fees:
            assert fee.charge_model == "standard"

    def test_preview_with_coupons(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test preview with coupon discounts applied."""
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

        # Create and apply a coupon
        coupon_repo = CouponRepository(db_session)
        coupon_data = CouponCreate(
            name="Preview Test Coupon",
            code="preview_coupon_10",
            coupon_type=CouponType.FIXED_AMOUNT,
            amount_cents=Decimal("20"),
            amount_currency="USD",
            frequency=CouponFrequency.FOREVER,
        )
        coupon_repo.create(coupon_data, DEFAULT_ORG_ID)

        coupon_service = CouponApplicationService(db_session)
        coupon_service.apply_coupon_to_customer(
            coupon_code="preview_coupon_10",
            customer_id=customer.id,
        )

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # 10 units * $10.00 = $100.00 subtotal, $20 coupon discount
        assert result.subtotal == Decimal("100")
        assert result.coupons_amount == Decimal("20")
        assert result.total == Decimal("80")

        # Verify coupon is NOT consumed (still active) — preview is read-only
        from app.repositories.applied_coupon_repository import AppliedCouponRepository

        applied_repo = AppliedCouponRepository(db_session)
        applied = applied_repo.get_active_by_customer_id(customer.id)
        assert len(applied) == 1
        assert applied[0].status == AppliedCouponStatus.ACTIVE.value

    def test_preview_with_zero_usage(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test preview with zero usage (no events)."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()

        # No events created — zero usage

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert result.subtotal == Decimal("0")
        assert result.total == Decimal("0")
        assert len(result.fees) == 0

    def test_no_records_written_to_db(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Confirm no Invoice or Fee records are created during preview."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "2.50"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        # Count existing records before preview
        invoice_count_before = db_session.query(Invoice).count()
        fee_count_before = db_session.query(Fee).count()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # Preview should return data
        assert result.subtotal == Decimal("25")
        assert len(result.fees) == 1

        # But no DB records should have been created
        invoice_count_after = db_session.query(Invoice).count()
        fee_count_after = db_session.query(Fee).count()
        assert invoice_count_after == invoice_count_before
        assert fee_count_after == fee_count_before

    def test_preview_with_default_billing_period(
        self, db_session, active_subscription, customer
    ):
        """Test preview with default billing period (None for start/end)."""
        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=None,
            billing_period_end=None,
        )

        # Should not error; just returns zero usage
        assert result.subtotal == Decimal("0")
        assert result.total == Decimal("0")
        assert result.currency == "USD"

    def test_preview_with_commitment_true_up(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test preview includes commitment true-up fee."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()

        # Add a minimum commitment of $100
        commitment = Commitment(
            plan_id=active_subscription.plan_id,
            commitment_type="minimum_commitment",
            amount_cents=Decimal("100"),
            invoice_display_name="Min Spend",
        )
        db_session.add(commitment)
        db_session.commit()

        # Create only 5 events = $5 usage, well below $100 commitment
        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # Should have usage fee ($5) + commitment true-up ($95)
        assert len(result.fees) == 2
        assert result.subtotal == Decimal("100")

        # Verify the true-up fee
        true_up = [f for f in result.fees if f.description == "Min Spend"]
        assert len(true_up) == 1
        assert true_up[0].amount_cents == Decimal("95")

    def test_preview_with_taxes(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test preview calculates taxes read-only."""
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
                code="PREV_ORG_TAX",
                name="Preview Org Tax 10%",
                rate=Decimal("0.1000"),
                applied_to_organization=True,
            ),
            DEFAULT_ORG_ID,
        )

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # Subtotal: 10 * $10 = $100, tax: 10% of $100 = $10
        assert result.subtotal == Decimal("100")
        assert result.tax_amount == Decimal("10")
        assert result.total == Decimal("110")

    def test_preview_total_negative_clamped_to_zero(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that total is clamped to zero when discounts exceed subtotal."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=1)

        # Apply a coupon much larger than the subtotal
        coupon_repo = CouponRepository(db_session)
        coupon_data = CouponCreate(
            name="Big Coupon",
            code="preview_big_coupon",
            coupon_type=CouponType.FIXED_AMOUNT,
            amount_cents=Decimal("5000"),
            amount_currency="USD",
            frequency=CouponFrequency.FOREVER,
        )
        coupon_repo.create(coupon_data, DEFAULT_ORG_ID)

        coupon_service = CouponApplicationService(db_session)
        coupon_service.apply_coupon_to_customer(
            coupon_code="preview_big_coupon",
            customer_id=customer.id,
        )

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert result.subtotal == Decimal("1")
        # Coupon capped at subtotal ($1)
        assert result.coupons_amount == Decimal("1")
        assert result.total == Decimal("0")

    def test_preview_with_charge_filters(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test preview with filtered charges creates separate fee previews."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_filtered_calls",
            name="Filtered API Calls",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="region",
            values=["us-east", "eu-west"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf_us = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "3.00"},
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

        cf_eu = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "5.00"},
            invoice_display_name="EU West API Calls",
        )
        db_session.add(cf_eu)
        db_session.commit()
        db_session.refresh(cf_eu)

        cfv_eu = ChargeFilterValue(
            charge_filter_id=cf_eu.id,
            billable_metric_filter_id=bmf.id,
            value="eu-west",
        )
        db_session.add(cfv_eu)
        db_session.commit()

        # Create events with region properties
        for i in range(4):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_filtered_calls",
                transaction_id=f"txn_prev_us_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"region": "us-east"},
            ))
        for i in range(2):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_filtered_calls",
                transaction_id=f"txn_prev_eu_{uuid4()}",
                timestamp=start + timedelta(hours=i + 10),
                properties={"region": "eu-west"},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 2
        fee_map = {f.description: f for f in result.fees}
        # US: 4 units * $3.00 = $12
        assert fee_map["US East API Calls"].amount_cents == Decimal("12")
        # EU: 2 units * $5.00 = $10
        assert fee_map["EU West API Calls"].amount_cents == Decimal("10")
        assert result.subtotal == Decimal("22")

    def test_preview_filtered_charge_no_metric_id(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test _calculate_filtered_charge_fees returns empty when no billable_metric_id."""
        from unittest.mock import MagicMock

        start, end = billing_period

        service = InvoicePreviewService(db_session)

        # Create a mock charge with no billable_metric_id
        mock_charge = MagicMock()
        mock_charge.billable_metric_id = None

        result = service._calculate_filtered_charge_fees(
            charge=mock_charge,
            charge_filters=[MagicMock()],
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )
        assert result == []

    def test_preview_filtered_charge_metric_not_found(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filtered charge when metric is deleted returns no fees."""
        from app.models.charge_filter import ChargeFilter

        start, end = billing_period

        metric = BillableMetric(
            code="preview_deleted_metric",
            name="Deleted Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)
        metric_id = metric.id

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric_id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "2.00"},
        )
        db_session.add(cf)
        db_session.commit()

        # Delete the metric
        db_session.delete(metric)
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 0

    def test_preview_filtered_charge_empty_filter_values(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filtered charge with no filter values is skipped."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter

        start, end = billing_period

        metric = BillableMetric(
            code="preview_empty_filter",
            name="Empty Filter Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="region",
            values=["us-east"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        # ChargeFilter with no ChargeFilterValues
        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "3.00"},
        )
        db_session.add(cf)
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 0

    def test_preview_filtered_charge_orphaned_bmf(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filter with orphaned BMF reference is skipped."""
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_orphan_bmf",
            name="Orphan BMF Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "2.00"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        # Create a filter value pointing to a non-existent BMF
        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=uuid4(),
            value="orphan",
        )
        db_session.add(cfv)
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 0

    def test_preview_filtered_zero_usage(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filter with zero matching events produces no fee."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_filter_zero",
            name="Filter Zero Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="region",
            values=["us-east"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "3.00"},
            invoice_display_name=None,
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=bmf.id,
            value="us-east",
        )
        db_session.add(cfv)
        db_session.commit()

        # No events — zero usage

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 0

    def test_preview_graduated_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test preview with graduated charge model."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "graduated_ranges": [
                    {"from_value": 0, "to_value": 5, "per_unit_amount": "1.00", "flat_amount": "0"},
                    {"from_value": 5, "to_value": None, "per_unit_amount": "0.50", "flat_amount": "0"},
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # Graduated: tier capacity = to_value - from_value + 1
        # First tier (0-5): 6 units * $1.00 = $6.00
        # Second tier (5+): 4 units * $0.50 = $2.00
        assert len(result.fees) == 1
        assert result.subtotal == Decimal("8")
        assert result.fees[0].charge_model == "graduated"

    def test_preview_volume_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test preview with volume charge model."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.VOLUME.value,
            properties={
                "volume_ranges": [
                    {"from_value": 0, "to_value": 5, "per_unit_amount": "2.00", "flat_amount": "0"},
                    {"from_value": 5, "to_value": None, "per_unit_amount": "1.00", "flat_amount": "0"},
                ]
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # Volume: all 10 units in the 5+ tier at $1.00 = $10.00
        assert len(result.fees) == 1
        assert result.subtotal == Decimal("10")
        assert result.fees[0].charge_model == "volume"

    def test_preview_package_charge(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test preview with package charge model."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PACKAGE.value,
            properties={
                "package_size": 5,
                "amount": "10.00",
            },
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=8)

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # 8 units / 5 per package = 2 packages * $10 = $20
        assert len(result.fees) == 1
        assert result.subtotal == Decimal("20")
        assert result.fees[0].charge_model == "package"

    def test_preview_percentage_charge(
        self, db_session, active_subscription, billing_period, customer
    ):
        """Test preview with percentage charge model."""
        start, end = billing_period

        metric = BillableMetric(
            code="preview_pct_metric",
            name="Percentage Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PERCENTAGE.value,
            properties={
                "rate": "0.05",
                "base_amount": "1000",
                "event_count": 10,
            },
        )
        db_session.add(charge)
        db_session.commit()

        for i in range(5):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_pct_metric",
                transaction_id=f"txn_prev_pct_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1
        assert result.fees[0].charge_model == "percentage"

    def test_preview_graduated_percentage_charge(
        self, db_session, active_subscription, billing_period, customer
    ):
        """Test preview with graduated_percentage charge model."""
        start, end = billing_period

        metric = BillableMetric(
            code="preview_gp_metric",
            name="Graduated Pct Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 100, "rate": "0.10", "flat_amount": "0"},
                    {"from_value": 100, "to_value": None, "rate": "0.05", "flat_amount": "0"},
                ],
                "base_amount": "200",
            },
        )
        db_session.add(charge)
        db_session.commit()

        for i in range(3):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_gp_metric",
                transaction_id=f"txn_prev_gp_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1
        assert result.fees[0].charge_model == "graduated_percentage"

    def test_preview_custom_charge(
        self, db_session, active_subscription, billing_period, customer
    ):
        """Test preview with custom charge model."""
        start, end = billing_period

        metric = BillableMetric(
            code="preview_custom_metric",
            name="Custom Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"custom_amount": "7.50"},
        )
        db_session.add(charge)
        db_session.commit()

        for i in range(2):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_custom_metric",
                transaction_id=f"txn_prev_custom_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1
        assert result.fees[0].charge_model == "custom"

    def test_preview_dynamic_charge(
        self, db_session, active_subscription, billing_period, customer
    ):
        """Test preview with dynamic charge model."""
        start, end = billing_period

        metric = BillableMetric(
            code="preview_dynamic_metric",
            name="Dynamic Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={"price_field": "amount"},
        )
        db_session.add(charge)
        db_session.commit()

        for i in range(3):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_dynamic_metric",
                transaction_id=f"txn_prev_dyn_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"amount": "10.00"},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1
        assert result.fees[0].charge_model == "dynamic"

    def test_preview_charge_metric_not_found(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test that a charge with a deleted metric is skipped."""
        start, end = billing_period

        metric = BillableMetric(
            code="preview_gone_metric",
            name="Gone Metric",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)
        metric_id = metric.id

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric_id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()

        # Delete the metric
        db_session.delete(metric)
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 0
        assert result.subtotal == Decimal("0")

    def test_preview_commitment_not_minimum_skipped(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that non-minimum commitments are skipped."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()

        # Add a non-minimum commitment
        commitment = Commitment(
            plan_id=active_subscription.plan_id,
            commitment_type="other_type",
            amount_cents=Decimal("100"),
        )
        db_session.add(commitment)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # Only charge fee, no commitment true-up
        assert len(result.fees) == 1
        assert result.subtotal == Decimal("5")

    def test_preview_commitment_already_met(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test that commitment is skipped when usage exceeds it."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "100.00"},
        )
        db_session.add(charge)
        db_session.commit()

        commitment = Commitment(
            plan_id=active_subscription.plan_id,
            commitment_type="minimum_commitment",
            amount_cents=Decimal("50"),
        )
        db_session.add(commitment)
        db_session.commit()

        # Create 1 event * $100 = $100, exceeds $50 commitment
        _create_events(db_session, customer, metric, billing_period, count=1)

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # No true-up fee needed
        assert len(result.fees) == 1
        assert result.subtotal == Decimal("100")

    def test_preview_standard_charge_min_max_price(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test standard charge with min_price and max_price constraints."""
        start, end = billing_period

        # min_price = 50, max_price = 200
        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00", "min_price": "50", "max_price": "200"},
        )
        db_session.add(charge)
        db_session.commit()

        # 10 units * $1.00 = $10, below min_price of $50
        _create_events(db_session, customer, metric, billing_period, count=10)

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # Should be clamped to min_price of $50
        assert result.subtotal == Decimal("50")

    def test_preview_filtered_graduated_charge(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filtered charge with graduated model."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_filt_grad",
            name="Filtered Graduated",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="tier",
            values=["premium"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED.value,
            properties={
                "graduated_ranges": [
                    {"from_value": 0, "to_value": 5, "per_unit_amount": "2.00", "flat_amount": "0"},
                    {"from_value": 5, "to_value": None, "per_unit_amount": "1.00", "flat_amount": "0"},
                ],
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
                    {"from_value": 5, "to_value": None, "per_unit_amount": "1.50", "flat_amount": "0"},
                ],
            },
            invoice_display_name="Premium Graduated",
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=bmf.id,
            value="premium",
        )
        db_session.add(cfv)
        db_session.commit()

        for i in range(8):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_filt_grad",
                transaction_id=f"txn_prev_fg_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"tier": "premium"},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1
        # Graduated: tier capacity = to_value - from_value + 1
        # First tier (0-5): 6 units * $3.00 = $18.00
        # Second tier (5+): 2 units * $1.50 = $3.00
        assert result.fees[0].amount_cents == Decimal("21")

    def test_preview_filtered_percentage_charge(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filtered charge with percentage model."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_filt_pct",
            name="Filtered Pct",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="channel",
            values=["web"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.PERCENTAGE.value,
            properties={"rate": "0.05", "base_amount": "500", "event_count": 5},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"rate": "0.10", "base_amount": "1000"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=bmf.id,
            value="web",
        )
        db_session.add(cfv)
        db_session.commit()

        for i in range(3):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_filt_pct",
                transaction_id=f"txn_prev_fpct_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"channel": "web"},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1

    def test_preview_filtered_graduated_percentage_charge(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filtered charge with graduated_percentage model."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_filt_gp",
            name="Filtered Grad Pct",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="level",
            values=["gold"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.GRADUATED_PERCENTAGE.value,
            properties={
                "graduated_percentage_ranges": [
                    {"from_value": 0, "to_value": 100, "rate": "0.10", "flat_amount": "0"},
                ],
                "base_amount": "50",
            },
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"base_amount": "100"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=bmf.id,
            value="gold",
        )
        db_session.add(cfv)
        db_session.commit()

        for i in range(2):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_filt_gp",
                transaction_id=f"txn_prev_fgp_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"level": "gold"},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1

    def test_preview_filtered_custom_charge(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filtered charge with custom model."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_filt_custom",
            name="Filtered Custom",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="type",
            values=["api"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.CUSTOM.value,
            properties={"custom_amount": "5.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"custom_amount": "10.00"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=bmf.id,
            value="api",
        )
        db_session.add(cfv)
        db_session.commit()

        for i in range(2):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_filt_custom",
                transaction_id=f"txn_prev_fcustom_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"type": "api"},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1

    def test_preview_filtered_dynamic_charge(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filtered charge with dynamic model."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_filt_dyn",
            name="Filtered Dynamic",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="source",
            values=["app"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.DYNAMIC.value,
            properties={"price_field": "amount"},
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

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=bmf.id,
            value="app",
        )
        db_session.add(cfv)
        db_session.commit()

        for i in range(2):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_filt_dyn",
                transaction_id=f"txn_prev_fdyn_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"source": "app", "amount": "15.00"},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1

    def test_preview_filtered_standard_min_max(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filtered standard charge with min_price and max_price."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_filt_minmax",
            name="Filtered Min Max",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="zone",
            values=["a"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "1.00", "min_price": "50", "max_price": "200"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=bmf.id,
            value="a",
        )
        db_session.add(cfv)
        db_session.commit()

        # 3 events * $1 = $3, below min_price $50
        for i in range(3):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_filt_minmax",
                transaction_id=f"txn_prev_fmm_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"zone": "a"},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1
        assert result.fees[0].amount_cents == Decimal("50")

    def test_preview_filtered_standard_max_price(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filtered standard charge clamped to max_price."""
        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_filt_max",
            name="Filtered Max",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="zone",
            values=["b"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "100.00"},
        )
        db_session.add(charge)
        db_session.commit()
        db_session.refresh(charge)

        cf = ChargeFilter(
            charge_id=charge.id,
            properties={"amount": "100.00", "max_price": "50"},
        )
        db_session.add(cf)
        db_session.commit()
        db_session.refresh(cf)

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=bmf.id,
            value="b",
        )
        db_session.add(cfv)
        db_session.commit()

        # 5 events * $100 = $500, above max_price $50
        for i in range(5):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_filt_max",
                transaction_id=f"txn_prev_fmax_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"zone": "b"},
            ))
        db_session.commit()

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert len(result.fees) == 1
        assert result.fees[0].amount_cents == Decimal("50")

    def test_preview_standard_charge_max_price(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test standard charge clamped to max_price."""
        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "100.00", "max_price": "30"},
        )
        db_session.add(charge)
        db_session.commit()

        # 5 events * $100 = $500, clamped to max_price $30
        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoicePreviewService(db_session)
        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        assert result.subtotal == Decimal("30")

    def test_preview_unknown_charge_model_returns_none(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test _calculate_charge_fee returns None when no calculator and no metric."""
        from unittest.mock import MagicMock, patch

        start, end = billing_period
        service = InvoicePreviewService(db_session)

        mock_charge = MagicMock()
        mock_charge.billable_metric_id = None
        mock_charge.charge_model = ChargeModel.STANDARD.value
        mock_charge.properties = {"amount": "1.00"}

        # Mock get_charge_calculator to return None
        with patch(
            "app.services.invoice_preview_service.get_charge_calculator", return_value=None
        ):
            result = service._calculate_charge_fee(
                charge=mock_charge,
                customer_id=customer.id,
                subscription_id=active_subscription.id,
                external_customer_id=customer.external_id,
                billing_period_start=start,
                billing_period_end=end,
            )

        assert result is None

    def test_preview_filtered_calculator_returns_none(
        self, db_session, active_subscription, customer, billing_period
    ):
        """Test filtered charge skipped when calculator returns None."""
        from unittest.mock import patch

        from app.models.billable_metric_filter import BillableMetricFilter
        from app.models.charge_filter import ChargeFilter
        from app.models.charge_filter_value import ChargeFilterValue

        start, end = billing_period

        metric = BillableMetric(
            code="preview_filt_nocalc",
            name="No Calc Filter",
            aggregation_type="count",
        )
        db_session.add(metric)
        db_session.commit()
        db_session.refresh(metric)

        bmf = BillableMetricFilter(
            billable_metric_id=metric.id,
            key="zone",
            values=["x"],
        )
        db_session.add(bmf)
        db_session.commit()
        db_session.refresh(bmf)

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
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

        cfv = ChargeFilterValue(
            charge_filter_id=cf.id,
            billable_metric_filter_id=bmf.id,
            value="x",
        )
        db_session.add(cfv)
        db_session.commit()

        for i in range(2):
            db_session.add(Event(
                external_customer_id=customer.external_id,
                code="preview_filt_nocalc",
                transaction_id=f"txn_prev_fnc_{uuid4()}",
                timestamp=start + timedelta(hours=i + 1),
                properties={"zone": "x"},
            ))
        db_session.commit()

        with patch(
            "app.services.invoice_preview_service.get_charge_calculator", return_value=None
        ):
            service = InvoicePreviewService(db_session)
            result = service.preview_invoice(
                subscription_id=active_subscription.id,
                external_customer_id=customer.external_id,
                billing_period_start=start,
                billing_period_end=end,
            )

        assert len(result.fees) == 0

    def test_preview_total_negative_from_progressive_credits(
        self, db_session, active_subscription, metric, customer, billing_period
    ):
        """Test total clamped to zero when progressive credits exceed subtotal."""

        start, end = billing_period

        charge = Charge(
            plan_id=active_subscription.plan_id,
            billable_metric_id=metric.id,
            charge_model=ChargeModel.STANDARD.value,
            properties={"amount": "1.00"},
        )
        db_session.add(charge)
        db_session.commit()

        _create_events(db_session, customer, metric, billing_period, count=5)

        service = InvoicePreviewService(db_session)

        # Create a progressive billing invoice with $1000 total for this period
        from app.models.invoice import Invoice, InvoiceType

        progressive_inv = Invoice(
            invoice_number="INV-PROG-TEST-001",
            customer_id=customer.id,
            subscription_id=active_subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            invoice_type=InvoiceType.PROGRESSIVE_BILLING.value,
            subtotal=Decimal("1000"),
            total=Decimal("1000"),
        )
        db_session.add(progressive_inv)
        db_session.commit()

        result = service.preview_invoice(
            subscription_id=active_subscription.id,
            external_customer_id=customer.external_id,
            billing_period_start=start,
            billing_period_end=end,
        )

        # Subtotal $5 minus $1000 progressive credits = clamped to $0
        assert result.subtotal == Decimal("5")
        assert result.prepaid_credit_amount == Decimal("1000")
        assert result.total == Decimal("0")
