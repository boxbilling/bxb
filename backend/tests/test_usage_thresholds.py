"""Tests for UsageThreshold and AppliedUsageThreshold models, repositories, schemas, and API."""

import uuid as uuid_mod
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
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
    CurrentUsageResponse,
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

    def test_creation_with_invoice(self, db_session, plan_threshold, subscription, invoice):
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
            UsageThresholdCreate(subscription_id=subscription.id, amount_cents=Decimal("3000")),
            DEFAULT_ORG_ID,
        )
        repo.create(
            UsageThresholdCreate(subscription_id=subscription.id, amount_cents=Decimal("7000")),
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

    def test_create_with_invoice(self, db_session, plan_threshold, subscription, invoice):
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

    def test_get_by_id_with_organization(self, db_session, plan_threshold, subscription):
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

    def test_get_by_id_wrong_organization(self, db_session, plan_threshold, subscription):
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

    def test_get_by_subscription_id(self, db_session, plan_threshold, subscription):
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

    def test_get_by_subscription_id_multiple(self, db_session, plan_threshold, subscription):
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

    def test_has_been_crossed_true(self, db_session, plan_threshold, subscription):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        period_start = now - timedelta(days=30)
        repo.create(
            usage_threshold_id=plan_threshold.id,
            subscription_id=subscription.id,
            crossed_at=now - timedelta(days=5),
            organization_id=DEFAULT_ORG_ID,
        )
        assert repo.has_been_crossed(plan_threshold.id, subscription.id, period_start) is True

    def test_has_been_crossed_false_no_records(self, db_session, plan_threshold, subscription):
        repo = AppliedUsageThresholdRepository(db_session)
        now = datetime.now(UTC)
        period_start = now - timedelta(days=30)
        assert repo.has_been_crossed(plan_threshold.id, subscription.id, period_start) is False

    def test_has_been_crossed_false_before_period(self, db_session, plan_threshold, subscription):
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
        assert repo.has_been_crossed(plan_threshold.id, subscription.id, period_start) is False

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
        assert repo.has_been_crossed(other_threshold.id, subscription.id, period_start) is False

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
        assert repo.has_been_crossed(plan_threshold.id, other_sub.id, period_start) is False


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

    def test_applied_response_from_model(self, db_session, plan_threshold, subscription):
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

    def test_applied_response_with_invoice(self, db_session, plan_threshold, subscription, invoice):
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

    def test_current_usage_response(self):
        """Test CurrentUsageResponse schema."""
        now = datetime.now(UTC)
        sub_id = uuid4()
        response = CurrentUsageResponse(
            subscription_id=sub_id,
            current_usage_amount_cents=Decimal("5000"),
            billing_period_start=now - timedelta(days=30),
            billing_period_end=now,
        )
        assert response.subscription_id == sub_id
        assert response.current_usage_amount_cents == Decimal("5000")
        assert response.billing_period_start is not None
        assert response.billing_period_end is not None


# ─────────────────────────────────────────────────────────────────────────────
# API Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestUsageThresholdsAPI:
    """Tests for the usage thresholds API endpoints."""

    def _create_plan(self, client: TestClient, code: str | None = None) -> dict:
        """Helper to create a plan via API."""
        plan_code = code or f"ut_api_plan_{uuid4()}"
        response = client.post(
            "/v1/plans/",
            json={
                "code": plan_code,
                "name": "UT API Test Plan",
                "interval": "monthly",
            },
        )
        assert response.status_code == 201
        return response.json()

    def _create_customer(self, client: TestClient, ext_id: str | None = None) -> dict:
        """Helper to create a customer via API."""
        external_id = ext_id or f"ut_api_cust_{uuid4()}"
        response = client.post(
            "/v1/customers/",
            json={
                "external_id": external_id,
                "name": "UT API Test Customer",
            },
        )
        assert response.status_code == 201
        return response.json()

    def _create_subscription(
        self, client: TestClient, customer_id: str, plan_id: str, ext_id: str | None = None
    ) -> dict:
        """Helper to create a subscription via API."""
        external_id = ext_id or f"ut_api_sub_{uuid4()}"
        response = client.post(
            "/v1/subscriptions/",
            json={
                "external_id": external_id,
                "customer_id": customer_id,
                "plan_id": plan_id,
            },
        )
        assert response.status_code == 201
        return response.json()

    def test_create_plan_threshold(self, client: TestClient):
        """Test creating a usage threshold on a plan."""
        plan = self._create_plan(client, "ut_plan_create")
        response = client.post(
            f"/v1/plans/{plan['code']}/usage_thresholds",
            json={
                "amount_cents": 5000,
                "threshold_display_name": "Plan Alert $50",
                "recurring": True,
                "currency": "EUR",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["plan_id"] == plan["id"]
        assert data["subscription_id"] is None
        assert float(data["amount_cents"]) == 5000.0
        assert data["threshold_display_name"] == "Plan Alert $50"
        assert data["recurring"] is True
        assert data["currency"] == "EUR"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_plan_threshold_minimal(self, client: TestClient):
        """Test creating a plan threshold with minimal fields."""
        plan = self._create_plan(client, "ut_plan_create_min")
        response = client.post(
            f"/v1/plans/{plan['code']}/usage_thresholds",
            json={"amount_cents": 3000},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["currency"] == "USD"
        assert data["recurring"] is False
        assert data["threshold_display_name"] is None

    def test_create_plan_threshold_plan_not_found(self, client: TestClient):
        """Test creating a threshold on a non-existent plan."""
        response = client.post(
            "/v1/plans/nonexistent_plan/usage_thresholds",
            json={"amount_cents": 5000},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_create_plan_threshold_invalid_amount(self, client: TestClient):
        """Test creating a threshold with negative amount."""
        plan = self._create_plan(client, "ut_plan_invalid")
        response = client.post(
            f"/v1/plans/{plan['code']}/usage_thresholds",
            json={"amount_cents": -100},
        )
        assert response.status_code == 422

    def test_create_subscription_threshold(self, client: TestClient):
        """Test creating a usage threshold on a subscription."""
        plan = self._create_plan(client, "ut_sub_create_plan")
        customer = self._create_customer(client, "ut_sub_create_cust")
        sub = self._create_subscription(client, customer["id"], plan["id"], "ut_sub_create")
        response = client.post(
            f"/v1/subscriptions/{sub['id']}/usage_thresholds",
            json={
                "amount_cents": 10000,
                "recurring": True,
                "threshold_display_name": "Sub Alert $100",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["subscription_id"] == sub["id"]
        assert data["plan_id"] is None
        assert float(data["amount_cents"]) == 10000.0
        assert data["recurring"] is True
        assert data["threshold_display_name"] == "Sub Alert $100"

    def test_create_subscription_threshold_not_found(self, client: TestClient):
        """Test creating a threshold on a non-existent subscription."""
        fake_id = str(uuid_mod.uuid4())
        response = client.post(
            f"/v1/subscriptions/{fake_id}/usage_thresholds",
            json={"amount_cents": 5000},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_create_subscription_threshold_invalid_uuid(self, client: TestClient):
        """Test creating a threshold with invalid subscription UUID."""
        response = client.post(
            "/v1/subscriptions/not-a-uuid/usage_thresholds",
            json={"amount_cents": 5000},
        )
        assert response.status_code == 422

    def test_list_subscription_thresholds_empty(self, client: TestClient):
        """Test listing thresholds for a subscription with none."""
        plan = self._create_plan(client, "ut_list_empty_plan")
        customer = self._create_customer(client, "ut_list_empty_cust")
        sub = self._create_subscription(client, customer["id"], plan["id"], "ut_list_empty")
        response = client.get(f"/v1/subscriptions/{sub['id']}/usage_thresholds")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_subscription_thresholds(self, client: TestClient):
        """Test listing thresholds for a subscription."""
        plan = self._create_plan(client, "ut_list_plan")
        customer = self._create_customer(client, "ut_list_cust")
        sub = self._create_subscription(client, customer["id"], plan["id"], "ut_list_sub")
        client.post(
            f"/v1/subscriptions/{sub['id']}/usage_thresholds",
            json={"amount_cents": 3000},
        )
        client.post(
            f"/v1/subscriptions/{sub['id']}/usage_thresholds",
            json={"amount_cents": 7000},
        )
        response = client.get(f"/v1/subscriptions/{sub['id']}/usage_thresholds")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_subscription_thresholds_not_found(self, client: TestClient):
        """Test listing thresholds for a non-existent subscription."""
        fake_id = str(uuid_mod.uuid4())
        response = client.get(f"/v1/subscriptions/{fake_id}/usage_thresholds")
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_get_current_usage(self, client: TestClient):
        """Test getting current usage for a subscription."""
        plan = self._create_plan(client, "ut_usage_plan")
        customer = self._create_customer(client, "ut_usage_cust")
        sub = self._create_subscription(client, customer["id"], plan["id"], "ut_usage_sub")
        response = client.get(f"/v1/subscriptions/{sub['id']}/current_usage")
        assert response.status_code == 200
        data = response.json()
        assert data["subscription_id"] == sub["id"]
        assert "current_usage_amount_cents" in data
        assert "billing_period_start" in data
        assert "billing_period_end" in data

    def test_get_current_usage_subscription_not_found(self, client: TestClient):
        """Test getting current usage for a non-existent subscription."""
        fake_id = str(uuid_mod.uuid4())
        response = client.get(f"/v1/subscriptions/{fake_id}/current_usage")
        assert response.status_code == 404
        assert response.json()["detail"] == "Subscription not found"

    def test_get_current_usage_invalid_uuid(self, client: TestClient):
        """Test getting current usage with invalid UUID."""
        response = client.get("/v1/subscriptions/not-a-uuid/current_usage")
        assert response.status_code == 422

    def test_get_current_usage_plan_not_found(self, client: TestClient, db_session):
        """Test getting current usage when subscription's plan is missing."""
        from app.models.subscription import Subscription

        # Create subscription pointing to a non-existent plan
        fake_plan_id = uuid4()
        customer = self._create_customer(client, "ut_usage_no_plan_cust")
        sub = Subscription(
            external_id=f"ut_orphan_plan_{uuid4()}",
            customer_id=customer["id"],
            plan_id=fake_plan_id,
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        response = client.get(f"/v1/subscriptions/{sub.id}/current_usage")
        assert response.status_code == 404
        assert response.json()["detail"] == "Plan not found"

    def test_get_current_usage_customer_not_found(self, client: TestClient, db_session):
        """Test getting current usage when subscription's customer is missing."""
        from app.models.subscription import Subscription

        plan = self._create_plan(client, "ut_usage_no_cust_plan")
        fake_customer_id = uuid4()
        sub = Subscription(
            external_id=f"ut_orphan_cust_{uuid4()}",
            customer_id=fake_customer_id,
            plan_id=plan["id"],
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        response = client.get(f"/v1/subscriptions/{sub.id}/current_usage")
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"

    def test_delete_threshold(self, client: TestClient):
        """Test deleting a usage threshold."""
        plan = self._create_plan(client, "ut_delete_plan")
        response = client.post(
            f"/v1/plans/{plan['code']}/usage_thresholds",
            json={"amount_cents": 5000},
        )
        threshold_id = response.json()["id"]

        del_response = client.delete(f"/v1/usage_thresholds/{threshold_id}")
        assert del_response.status_code == 204

    def test_delete_threshold_not_found(self, client: TestClient):
        """Test deleting a non-existent usage threshold."""
        fake_id = str(uuid_mod.uuid4())
        response = client.delete(f"/v1/usage_thresholds/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Usage threshold not found"

    def test_delete_threshold_invalid_uuid(self, client: TestClient):
        """Test deleting a threshold with invalid UUID."""
        response = client.delete("/v1/usage_thresholds/not-a-uuid")
        assert response.status_code == 422
