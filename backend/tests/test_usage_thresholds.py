"""Tests for UsageThreshold and AppliedUsageThreshold models, repositories, and schemas."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import get_db
from app.models.applied_usage_threshold import AppliedUsageThreshold
from app.models.usage_threshold import UsageThreshold
from app.repositories.applied_usage_threshold_repository import (
    AppliedUsageThresholdRepository,
)
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_threshold_repository import UsageThresholdRepository
from app.schemas.customer import CustomerCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
from app.schemas.usage_threshold import (
    AppliedUsageThresholdResponse,
    UsageThresholdCreate,
    UsageThresholdResponse,
)
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
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"ut_test_plan_{uuid4()}",
            name="Usage Threshold Test Plan",
            interval="monthly",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def customer(db_session):
    """Create a test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"ut_test_cust_{uuid4()}",
            name="Usage Threshold Test Customer",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def subscription(db_session, customer, plan):
    """Create a test subscription."""
    repo = SubscriptionRepository(db_session)
    return repo.create(
        SubscriptionCreate(
            external_id=f"ut_test_sub_{uuid4()}",
            customer_id=customer.id,
            plan_id=plan.id,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def plan_threshold(db_session, plan):
    """Create a test usage threshold on a plan."""
    repo = UsageThresholdRepository(db_session)
    return repo.create(
        UsageThresholdCreate(
            plan_id=plan.id,
            amount_cents=Decimal("5000"),
            threshold_display_name="Plan Threshold $50",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def subscription_threshold(db_session, subscription):
    """Create a test usage threshold on a subscription."""
    repo = UsageThresholdRepository(db_session)
    return repo.create(
        UsageThresholdCreate(
            subscription_id=subscription.id,
            amount_cents=Decimal("10000"),
            recurring=True,
            threshold_display_name="Subscription Threshold $100",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def invoice(db_session, customer, subscription):
    """Create a test invoice."""
    now = datetime.now(UTC)
    repo = InvoiceRepository(db_session)
    return repo.create(
        InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            invoice_number=f"INV-UT-{uuid4()}",
            billing_period_start=now - timedelta(days=30),
            billing_period_end=now,
            subtotal=Decimal("5000"),
            total=Decimal("5000"),
            line_items=[
                InvoiceLineItem(
                    description="Test line item",
                    quantity=Decimal("1"),
                    unit_price=Decimal("5000"),
                    amount=Decimal("5000"),
                )
            ],
        ),
        DEFAULT_ORG_ID,
    )


# ─────────────────────────────────────────────────────────────────────────────
# UsageThreshold Model Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUsageThresholdModel:
    """Tests for the UsageThreshold model."""

    def test_table_name(self):
        assert UsageThreshold.__tablename__ == "usage_thresholds"

    def test_creation_with_plan(self, db_session, plan):
        threshold = UsageThreshold(
            plan_id=plan.id,
            amount_cents=Decimal("5000"),
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(threshold)
        db_session.commit()
        db_session.refresh(threshold)

        assert threshold.id is not None
        assert threshold.plan_id == plan.id
        assert threshold.subscription_id is None
        assert threshold.amount_cents == Decimal("5000")
        assert threshold.currency == "USD"
        assert threshold.recurring is False
        assert threshold.threshold_display_name is None
        assert threshold.created_at is not None
        assert threshold.updated_at is not None

    def test_creation_with_subscription(self, db_session, subscription):
        threshold = UsageThreshold(
            subscription_id=subscription.id,
            amount_cents=Decimal("10000"),
            currency="EUR",
            recurring=True,
            threshold_display_name="High usage alert",
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(threshold)
        db_session.commit()
        db_session.refresh(threshold)

        assert threshold.id is not None
        assert threshold.plan_id is None
        assert threshold.subscription_id == subscription.id
        assert threshold.amount_cents == Decimal("10000")
        assert threshold.currency == "EUR"
        assert threshold.recurring is True
        assert threshold.threshold_display_name == "High usage alert"


# ─────────────────────────────────────────────────────────────────────────────
# AppliedUsageThreshold Model Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAppliedUsageThresholdModel:
    """Tests for the AppliedUsageThreshold model."""

    def test_table_name(self):
        assert AppliedUsageThreshold.__tablename__ == "applied_usage_thresholds"

    def test_creation(self, db_session, plan_threshold, subscription):
        now = datetime.now(UTC)
        record = AppliedUsageThreshold(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            lifetime_usage_amount_cents=Decimal("6000"),
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)

        assert record.id is not None
        assert record.usage_threshold_id == plan_threshold.id
        assert record.subscription_id == subscription.id
        assert record.invoice_id is None
        assert record.crossed_at.replace(tzinfo=None) == now.replace(tzinfo=None)
        assert record.lifetime_usage_amount_cents == Decimal("6000")
        assert record.created_at is not None

    def test_creation_with_invoice(
        self, db_session, plan_threshold, subscription, invoice
    ):
        now = datetime.now(UTC)
        record = AppliedUsageThreshold(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            invoice_id=invoice.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)

        assert record.invoice_id == invoice.id
        assert record.lifetime_usage_amount_cents is None


# ─────────────────────────────────────────────────────────────────────────────
# UsageThresholdRepository Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUsageThresholdRepository:
    """Tests for UsageThresholdRepository CRUD and query methods."""

    def test_create_plan_threshold(self, db_session, plan):
        repo = UsageThresholdRepository(db_session)
        threshold = repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("5000"),
                threshold_display_name="Plan Alert",
            ),
            DEFAULT_ORG_ID,
        )
        assert threshold.id is not None
        assert threshold.plan_id == plan.id
        assert threshold.subscription_id is None
        assert threshold.amount_cents == Decimal("5000")
        assert threshold.threshold_display_name == "Plan Alert"
        assert threshold.recurring is False
        assert threshold.currency == "USD"

    def test_create_subscription_threshold(self, db_session, subscription):
        repo = UsageThresholdRepository(db_session)
        threshold = repo.create(
            UsageThresholdCreate(
                subscription_id=subscription.id,
                amount_cents=Decimal("10000"),
                currency="EUR",
                recurring=True,
            ),
            DEFAULT_ORG_ID,
        )
        assert threshold.id is not None
        assert threshold.subscription_id == subscription.id
        assert threshold.plan_id is None
        assert threshold.recurring is True
        assert threshold.currency == "EUR"

    def test_create_minimal(self, db_session, plan):
        """Test creating with only required fields."""
        repo = UsageThresholdRepository(db_session)
        threshold = repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("3000"),
            ),
            DEFAULT_ORG_ID,
        )
        assert threshold.id is not None
        assert threshold.currency == "USD"
        assert threshold.recurring is False
        assert threshold.threshold_display_name is None

    def test_get_by_id(self, db_session, plan_threshold):
        repo = UsageThresholdRepository(db_session)
        fetched = repo.get_by_id(plan_threshold.id)
        assert fetched is not None
        assert fetched.id == plan_threshold.id
        assert fetched.amount_cents == Decimal("5000")

    def test_get_by_id_with_organization(self, db_session, plan_threshold):
        repo = UsageThresholdRepository(db_session)
        fetched = repo.get_by_id(plan_threshold.id, DEFAULT_ORG_ID)
        assert fetched is not None
        assert fetched.id == plan_threshold.id

    def test_get_by_id_wrong_organization(self, db_session, plan_threshold):
        repo = UsageThresholdRepository(db_session)
        fetched = repo.get_by_id(plan_threshold.id, uuid4())
        assert fetched is None

    def test_get_by_id_not_found(self, db_session):
        repo = UsageThresholdRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_plan_id(self, db_session, plan, plan_threshold):
        repo = UsageThresholdRepository(db_session)
        thresholds = repo.get_by_plan_id(plan.id)
        assert len(thresholds) == 1
        assert thresholds[0].id == plan_threshold.id

    def test_get_by_plan_id_multiple(self, db_session, plan):
        repo = UsageThresholdRepository(db_session)
        repo.create(
            UsageThresholdCreate(plan_id=plan.id, amount_cents=Decimal("3000")),
            DEFAULT_ORG_ID,
        )
        repo.create(
            UsageThresholdCreate(plan_id=plan.id, amount_cents=Decimal("7000")),
            DEFAULT_ORG_ID,
        )
        thresholds = repo.get_by_plan_id(plan.id)
        assert len(thresholds) == 2

    def test_get_by_plan_id_empty(self, db_session):
        repo = UsageThresholdRepository(db_session)
        thresholds = repo.get_by_plan_id(uuid4())
        assert len(thresholds) == 0

    def test_get_by_subscription_id(self, db_session, subscription, subscription_threshold):
        repo = UsageThresholdRepository(db_session)
        thresholds = repo.get_by_subscription_id(subscription.id)
        assert len(thresholds) == 1
        assert thresholds[0].id == subscription_threshold.id

    def test_get_by_subscription_id_multiple(self, db_session, subscription):
        repo = UsageThresholdRepository(db_session)
        repo.create(
            UsageThresholdCreate(
                subscription_id=subscription.id, amount_cents=Decimal("3000")
            ),
            DEFAULT_ORG_ID,
        )
        repo.create(
            UsageThresholdCreate(
                subscription_id=subscription.id, amount_cents=Decimal("7000")
            ),
            DEFAULT_ORG_ID,
        )
        thresholds = repo.get_by_subscription_id(subscription.id)
        assert len(thresholds) == 2

    def test_get_by_subscription_id_empty(self, db_session):
        repo = UsageThresholdRepository(db_session)
        thresholds = repo.get_by_subscription_id(uuid4())
        assert len(thresholds) == 0

    def test_get_all(self, db_session, plan_threshold):
        repo = UsageThresholdRepository(db_session)
        thresholds = repo.get_all(DEFAULT_ORG_ID)
        assert len(thresholds) == 1
        assert thresholds[0].id == plan_threshold.id

    def test_get_all_pagination(self, db_session, plan):
        repo = UsageThresholdRepository(db_session)
        for i in range(5):
            repo.create(
                UsageThresholdCreate(
                    plan_id=plan.id,
                    amount_cents=Decimal(str((i + 1) * 1000)),
                ),
                DEFAULT_ORG_ID,
            )
        thresholds = repo.get_all(DEFAULT_ORG_ID, skip=2, limit=2)
        assert len(thresholds) == 2

    def test_delete(self, db_session, plan_threshold):
        repo = UsageThresholdRepository(db_session)
        assert repo.delete(plan_threshold.id, DEFAULT_ORG_ID) is True
        assert repo.get_by_id(plan_threshold.id) is None

    def test_delete_not_found(self, db_session):
        repo = UsageThresholdRepository(db_session)
        assert repo.delete(uuid4(), DEFAULT_ORG_ID) is False

    def test_delete_wrong_organization(self, db_session, plan_threshold):
        repo = UsageThresholdRepository(db_session)
        assert repo.delete(plan_threshold.id, uuid4()) is False
        # Verify still exists
        assert repo.get_by_id(plan_threshold.id) is not None


# ─────────────────────────────────────────────────────────────────────────────
# AppliedUsageThresholdRepository Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAppliedUsageThresholdRepository:
    """Tests for AppliedUsageThresholdRepository CRUD and query methods."""

    def test_create(self, db_session, plan_threshold, subscription):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        record = repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
            lifetime_usage_amount_cents=Decimal("6000"),
        )
        assert record.id is not None
        assert record.usage_threshold_id == plan_threshold.id
        assert record.subscription_id == subscription.id
        assert record.crossed_at.replace(tzinfo=None) == now.replace(tzinfo=None)
        assert record.invoice_id is None
        assert record.lifetime_usage_amount_cents == Decimal("6000")
        assert record.created_at is not None

    def test_create_with_invoice(
        self, db_session, plan_threshold, subscription, invoice
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        record = repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
            invoice_id=invoice.id,
        )
        assert record.invoice_id == invoice.id
        assert record.lifetime_usage_amount_cents is None

    def test_get_by_id(self, db_session, plan_threshold, subscription):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        created = repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
        )
        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_by_id_with_organization(
        self, db_session, plan_threshold, subscription
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        created = repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
        )
        fetched = repo.get_by_id(created.id, DEFAULT_ORG_ID)
        assert fetched is not None

    def test_get_by_id_wrong_organization(
        self, db_session, plan_threshold, subscription
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        created = repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
        )
        fetched = repo.get_by_id(created.id, uuid4())
        assert fetched is None

    def test_get_by_id_not_found(self, db_session):
        repo = AppliedUsageThresholdRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_subscription_id(
        self, db_session, plan_threshold, subscription
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        created = repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
        )
        records = repo.get_by_subscription_id(subscription.id)
        assert len(records) == 1
        assert records[0].id == created.id

    def test_get_by_subscription_id_multiple(
        self, db_session, plan_threshold, subscription
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now - timedelta(hours=2),
            organization_id=DEFAULT_ORG_ID,
        )
        repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
        )
        records = repo.get_by_subscription_id(subscription.id)
        assert len(records) == 2

    def test_get_by_subscription_id_empty(self, db_session):
        repo = AppliedUsageThresholdRepository(db_session)
        records = repo.get_by_subscription_id(uuid4())
        assert len(records) == 0

    def test_get_all(self, db_session, plan_threshold, subscription):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
        )
        records = repo.get_all(DEFAULT_ORG_ID)
        assert len(records) == 1

    def test_get_all_pagination(self, db_session, plan_threshold, subscription):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        for i in range(5):
            repo.create(
                usage_threshold_id=plan_threshold.id,
                subscription_id=subscription.id,
                crossed_at=now - timedelta(hours=i),
                organization_id=DEFAULT_ORG_ID,
            )
        records = repo.get_all(DEFAULT_ORG_ID, skip=2, limit=2)
        assert len(records) == 2

    def test_has_been_crossed_true(
        self, db_session, plan_threshold, subscription
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        period_start = now - timedelta(days=30)
        repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now - timedelta(days=5),
            organization_id=DEFAULT_ORG_ID,
        )
        assert (
            repo.has_been_crossed(plan_threshold.id, subscription.id, period_start)
            is True
        )

    def test_has_been_crossed_false_no_records(
        self, db_session, plan_threshold, subscription
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        period_start = now - timedelta(days=30)
        assert (
            repo.has_been_crossed(plan_threshold.id, subscription.id, period_start)
            is False
        )

    def test_has_been_crossed_false_before_period(
        self, db_session, plan_threshold, subscription
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        period_start = now - timedelta(days=5)
        # Create a crossing from before the period
        repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now - timedelta(days=10),
            organization_id=DEFAULT_ORG_ID,
        )
        assert (
            repo.has_been_crossed(plan_threshold.id, subscription.id, period_start)
            is False
        )

    def test_has_been_crossed_different_threshold(
        self, db_session, plan, plan_threshold, subscription
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        ut_repo = UsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        period_start = now - timedelta(days=30)
        # Create a second threshold
        other_threshold = ut_repo.create(
            UsageThresholdCreate(
                plan_id=plan.id,
                amount_cents=Decimal("20000"),
            ),
            DEFAULT_ORG_ID,
        )
        # Cross the first threshold
        repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
        )
        # The second threshold should not be considered crossed
        assert (
            repo.has_been_crossed(other_threshold.id, subscription.id, period_start)
            is False
        )

    def test_has_been_crossed_different_subscription(
        self, db_session, plan_threshold, subscription, customer
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        sub_repo = SubscriptionRepository(db_session)
        now = datetime.now(UTC)
        period_start = now - timedelta(days=30)
        # Create second subscription
        other_sub = sub_repo.create(
            SubscriptionCreate(
                external_id=f"other_sub_{uuid4()}",
                customer_id=customer.id,
                plan_id=subscription.plan_id,
            ),
            DEFAULT_ORG_ID,
        )
        # Cross the threshold for the first subscription
        repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
        )
        # The second subscription should not see it as crossed
        assert (
            repo.has_been_crossed(plan_threshold.id, other_sub.id, period_start)
            is False
        )


# ─────────────────────────────────────────────────────────────────────────────
# Schema Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUsageThresholdSchemas:
    """Tests for Pydantic schemas."""

    def test_create_with_plan_id(self):
        schema = UsageThresholdCreate(
            plan_id=uuid4(),
            amount_cents=Decimal("5000"),
        )
        assert schema.plan_id is not None
        assert schema.subscription_id is None
        assert schema.currency == "USD"
        assert schema.recurring is False

    def test_create_with_subscription_id(self):
        schema = UsageThresholdCreate(
            subscription_id=uuid4(),
            amount_cents=Decimal("10000"),
            currency="EUR",
            recurring=True,
            threshold_display_name="High usage",
        )
        assert schema.subscription_id is not None
        assert schema.plan_id is None
        assert schema.currency == "EUR"
        assert schema.recurring is True
        assert schema.threshold_display_name == "High usage"

    def test_create_defaults(self):
        schema = UsageThresholdCreate(
            plan_id=uuid4(),
            amount_cents=Decimal("1000"),
        )
        assert schema.currency == "USD"
        assert schema.recurring is False
        assert schema.threshold_display_name is None

    def test_response_from_model(self, db_session, plan_threshold):
        response = UsageThresholdResponse.model_validate(plan_threshold)
        assert response.id == plan_threshold.id
        assert response.plan_id == plan_threshold.plan_id
        assert response.subscription_id is None
        assert response.amount_cents == Decimal("5000")
        assert response.threshold_display_name == "Plan Threshold $50"

    def test_response_subscription_threshold(self, db_session, subscription_threshold):
        response = UsageThresholdResponse.model_validate(subscription_threshold)
        assert response.subscription_id == subscription_threshold.subscription_id
        assert response.plan_id is None
        assert response.recurring is True

    def test_applied_response_from_model(
        self, db_session, plan_threshold, subscription
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        record = repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
            lifetime_usage_amount_cents=Decimal("7500"),
        )
        response = AppliedUsageThresholdResponse.model_validate(record)
        assert response.id == record.id
        assert response.usage_threshold_id == plan_threshold.id
        assert response.subscription_id == subscription.id
        assert response.invoice_id is None
        assert response.lifetime_usage_amount_cents == Decimal("7500")

    def test_applied_response_with_invoice(
        self, db_session, plan_threshold, subscription, invoice
    ):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        record = repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now,
            organization_id=DEFAULT_ORG_ID,
            invoice_id=invoice.id,
        )
        response = AppliedUsageThresholdResponse.model_validate(record)
        assert response.invoice_id == invoice.id
