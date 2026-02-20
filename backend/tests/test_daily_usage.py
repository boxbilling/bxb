"""Tests for DailyUsage model, repository, service, schema, and background task."""

import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.billable_metric import AggregationType
from app.models.daily_usage import DailyUsage
from app.models.shared import generate_uuid
from app.models.subscription import SubscriptionStatus
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.charge_repository import ChargeRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.daily_usage_repository import DailyUsageRepository
from app.repositories.event_repository import EventRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.billable_metric import BillableMetricCreate
from app.schemas.charge import ChargeCreate
from app.schemas.customer import CustomerCreate
from app.schemas.daily_usage import (
    DailyUsageCreate,
    DailyUsageResponse,
    UsageTrendPoint,
    UsageTrendResponse,
)
from app.schemas.event import EventCreate
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from app.services.daily_usage_service import DailyUsageService
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def db_session():
    """Create a database session for direct testing."""
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
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"du_test_cust_{uuid4()}",
            name="Daily Usage Test Customer",
            email="du@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"du_test_plan_{uuid4()}",
            name="Daily Usage Test Plan",
            interval="monthly",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def billable_metric(db_session):
    """Create a COUNT billable metric."""
    repo = BillableMetricRepository(db_session)
    return repo.create(
        BillableMetricCreate(
            code=f"du_api_calls_{uuid4()}",
            name="API Calls",
            aggregation_type=AggregationType.COUNT,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def sum_metric(db_session):
    """Create a SUM billable metric."""
    repo = BillableMetricRepository(db_session)
    return repo.create(
        BillableMetricCreate(
            code=f"du_data_transfer_{uuid4()}",
            name="Data Transfer",
            aggregation_type=AggregationType.SUM,
            field_name="bytes",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def charge(db_session, plan, billable_metric):
    """Create a charge linking plan to billable metric."""
    repo = ChargeRepository(db_session)
    return repo.create(
        plan.id,
        ChargeCreate(
            billable_metric_id=billable_metric.id,
            charge_model="standard",
            properties={"amount": "0.01"},
        ),
    )


@pytest.fixture
def active_subscription(db_session, customer, plan):
    """Create an active subscription."""
    repo = SubscriptionRepository(db_session)
    sub = repo.create(
        SubscriptionCreate(
            external_id=f"du_test_sub_{uuid4()}",
            customer_id=customer.id,
            plan_id=plan.id,
            started_at=datetime.now(UTC) - timedelta(days=30),
        ),
        DEFAULT_ORG_ID,
    )
    # Ensure it's active
    if sub.status != SubscriptionStatus.ACTIVE.value:
        repo.update(
            sub.id,
            SubscriptionUpdate(status=SubscriptionStatus.ACTIVE),
            DEFAULT_ORG_ID,
        )
        db_session.refresh(sub)
    return sub


@pytest.fixture
def events_for_yesterday(db_session, customer, billable_metric):
    """Create events for yesterday to aggregate."""
    repo = EventRepository(db_session)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    yesterday_start = datetime(yesterday.year, yesterday.month, yesterday.day, 10, 0, 0)
    events = []
    for i in range(3):
        evt = repo.create(
            EventCreate(
                transaction_id=f"du_evt_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(billable_metric.code),
                timestamp=yesterday_start + timedelta(hours=i),
                properties={"count": 1},
            ),
            DEFAULT_ORG_ID,
        )
        events.append(evt)
    return events


class TestDailyUsageModel:
    """Tests for DailyUsage model."""

    def test_generate_uuid(self):
        """Test UUID generation produces unique values."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        assert uuid1 != uuid2
        assert str(uuid1)

    def test_model_creation(self, db_session, active_subscription, billable_metric):
        """Test creating a DailyUsage model instance."""
        record = DailyUsage(
            subscription_id=active_subscription.id,
            billable_metric_id=billable_metric.id,
            external_customer_id="test_cust_123",
            usage_date=date.today(),
            usage_value=Decimal("42.5000"),
            events_count=10,
        )
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)

        assert record.id is not None
        assert record.subscription_id == active_subscription.id
        assert record.billable_metric_id == billable_metric.id
        assert record.external_customer_id == "test_cust_123"
        assert record.usage_date == date.today()
        assert Decimal(str(record.usage_value)) == Decimal("42.5000")
        assert record.events_count == 10
        assert record.created_at is not None
        assert record.updated_at is not None

    def test_model_default_values(self, db_session, active_subscription, billable_metric):
        """Test DailyUsage model default values."""
        record = DailyUsage(
            subscription_id=active_subscription.id,
            billable_metric_id=billable_metric.id,
            external_customer_id="test_cust_456",
            usage_date=date.today() - timedelta(days=1),
        )
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)

        assert Decimal(str(record.usage_value)) == Decimal("0")
        assert record.events_count == 0

    def test_unique_constraint(self, db_session, active_subscription, billable_metric):
        """Test composite unique constraint on (subscription_id, billable_metric_id, usage_date)."""
        today = date.today()
        record1 = DailyUsage(
            subscription_id=active_subscription.id,
            billable_metric_id=billable_metric.id,
            external_customer_id="test_cust",
            usage_date=today,
            usage_value=Decimal("10"),
            events_count=5,
        )
        db_session.add(record1)
        db_session.commit()

        record2 = DailyUsage(
            subscription_id=active_subscription.id,
            billable_metric_id=billable_metric.id,
            external_customer_id="test_cust",
            usage_date=today,
            usage_value=Decimal("20"),
            events_count=10,
        )
        db_session.add(record2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_different_dates_allowed(self, db_session, active_subscription, billable_metric):
        """Test that different dates for same sub/metric are allowed."""
        for i in range(3):
            record = DailyUsage(
                subscription_id=active_subscription.id,
                billable_metric_id=billable_metric.id,
                external_customer_id="test_cust",
                usage_date=date.today() - timedelta(days=i),
                usage_value=Decimal(str(i * 10)),
                events_count=i,
            )
            db_session.add(record)
        db_session.commit()

        records = (
            db_session.query(DailyUsage)
            .filter(DailyUsage.subscription_id == active_subscription.id)
            .all()
        )
        assert len(records) == 3


class TestDailyUsageSchema:
    """Tests for DailyUsage schemas."""

    def test_create_schema(self):
        """Test DailyUsageCreate schema."""
        data = DailyUsageCreate(
            subscription_id=uuid4(),
            billable_metric_id=uuid4(),
            external_customer_id="cust_123",
            usage_date=date.today(),
            usage_value=Decimal("99.5"),
            events_count=42,
        )
        assert data.usage_value == Decimal("99.5")
        assert data.events_count == 42
        assert data.external_customer_id == "cust_123"

    def test_create_schema_defaults(self):
        """Test DailyUsageCreate schema default values."""
        data = DailyUsageCreate(
            subscription_id=uuid4(),
            billable_metric_id=uuid4(),
            external_customer_id="cust_456",
            usage_date=date.today(),
        )
        assert data.usage_value == Decimal("0")
        assert data.events_count == 0

    def test_usage_trend_point_schema(self):
        """Test UsageTrendPoint schema."""
        point = UsageTrendPoint(
            date=date.today(),
            value=Decimal("42.5"),
            events_count=10,
        )
        assert point.value == Decimal("42.5")
        assert point.events_count == 10

    def test_usage_trend_response_schema(self):
        """Test UsageTrendResponse schema."""
        today = date.today()
        resp = UsageTrendResponse(
            subscription_id=uuid4(),
            start_date=today - timedelta(days=7),
            end_date=today,
            data_points=[
                UsageTrendPoint(date=today, value=Decimal("100"), events_count=5),
            ],
        )
        assert len(resp.data_points) == 1
        assert resp.data_points[0].value == Decimal("100")

    def test_response_schema(self, db_session, active_subscription, billable_metric):
        """Test DailyUsageResponse schema with from_attributes."""
        record = DailyUsage()
        record.id = uuid4()
        record.subscription_id = active_subscription.id
        record.billable_metric_id = billable_metric.id
        record.external_customer_id = "cust_resp"
        record.usage_date = date.today()
        record.usage_value = Decimal("55.1234")
        record.events_count = 7
        record.created_at = datetime.now(UTC)
        record.updated_at = datetime.now(UTC)

        response = DailyUsageResponse.model_validate(record)
        assert response.usage_value == Decimal("55.1234")
        assert response.events_count == 7
        assert response.usage_date == date.today()
        assert response.external_customer_id == "cust_resp"


class TestDailyUsageRepository:
    """Tests for DailyUsageRepository."""

    def test_upsert_create(self, db_session, active_subscription, billable_metric):
        """Test upserting a new daily usage record."""
        repo = DailyUsageRepository(db_session)
        data = DailyUsageCreate(
            subscription_id=active_subscription.id,
            billable_metric_id=billable_metric.id,
            external_customer_id="upsert_cust",
            usage_date=date.today(),
            usage_value=Decimal("25.0000"),
            events_count=5,
        )
        record = repo.upsert(data)

        assert record.id is not None
        assert Decimal(str(record.usage_value)) == Decimal("25.0000")
        assert record.events_count == 5

    def test_upsert_update(self, db_session, active_subscription, billable_metric):
        """Test upserting an existing daily usage record updates it."""
        repo = DailyUsageRepository(db_session)
        today = date.today()
        data = DailyUsageCreate(
            subscription_id=active_subscription.id,
            billable_metric_id=billable_metric.id,
            external_customer_id="upsert_cust",
            usage_date=today,
            usage_value=Decimal("10.0000"),
            events_count=3,
        )
        record1 = repo.upsert(data)
        record1_id = record1.id

        # Upsert again with new values
        data2 = DailyUsageCreate(
            subscription_id=active_subscription.id,
            billable_metric_id=billable_metric.id,
            external_customer_id="upsert_cust",
            usage_date=today,
            usage_value=Decimal("50.0000"),
            events_count=15,
        )
        record2 = repo.upsert(data2)

        assert record2.id == record1_id
        assert Decimal(str(record2.usage_value)) == Decimal("50.0000")
        assert record2.events_count == 15

    def test_get_by_id(self, db_session, active_subscription, billable_metric):
        """Test getting a daily usage record by ID."""
        repo = DailyUsageRepository(db_session)
        data = DailyUsageCreate(
            subscription_id=active_subscription.id,
            billable_metric_id=billable_metric.id,
            external_customer_id="get_cust",
            usage_date=date.today(),
            usage_value=Decimal("30.0000"),
            events_count=8,
        )
        created = repo.upsert(data)

        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert Decimal(str(fetched.usage_value)) == Decimal("30.0000")

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent daily usage record."""
        repo = DailyUsageRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_subscription_and_metric(self, db_session, active_subscription, billable_metric):
        """Test lookup by subscription, metric, and date."""
        repo = DailyUsageRepository(db_session)
        today = date.today()
        repo.upsert(
            DailyUsageCreate(
                subscription_id=active_subscription.id,
                billable_metric_id=billable_metric.id,
                external_customer_id="lookup_cust",
                usage_date=today,
                usage_value=Decimal("100.0000"),
                events_count=20,
            )
        )

        result = repo.get_by_subscription_and_metric(
            active_subscription.id, billable_metric.id, today
        )
        assert result is not None
        assert Decimal(str(result.usage_value)) == Decimal("100.0000")

    def test_get_by_subscription_and_metric_not_found(
        self, db_session, active_subscription, billable_metric
    ):
        """Test lookup when no matching record exists."""
        repo = DailyUsageRepository(db_session)
        result = repo.get_by_subscription_and_metric(
            active_subscription.id, billable_metric.id, date.today()
        )
        assert result is None

    def test_get_for_period(self, db_session, active_subscription, billable_metric):
        """Test getting records for a date range."""
        repo = DailyUsageRepository(db_session)
        base_date = date.today() - timedelta(days=10)

        for i in range(5):
            repo.upsert(
                DailyUsageCreate(
                    subscription_id=active_subscription.id,
                    billable_metric_id=billable_metric.id,
                    external_customer_id="period_cust",
                    usage_date=base_date + timedelta(days=i),
                    usage_value=Decimal(str(i * 10)),
                    events_count=i,
                )
            )

        records = repo.get_for_period(
            active_subscription.id,
            billable_metric.id,
            base_date,
            base_date + timedelta(days=4),
        )
        assert len(records) == 5
        # Should be ordered by usage_date
        for i, r in enumerate(records):
            assert r.usage_date == base_date + timedelta(days=i)

    def test_get_for_period_partial(self, db_session, active_subscription, billable_metric):
        """Test getting records for a partial date range."""
        repo = DailyUsageRepository(db_session)
        base_date = date.today() - timedelta(days=10)

        for i in range(5):
            repo.upsert(
                DailyUsageCreate(
                    subscription_id=active_subscription.id,
                    billable_metric_id=billable_metric.id,
                    external_customer_id="period_cust",
                    usage_date=base_date + timedelta(days=i),
                    usage_value=Decimal(str(10)),
                    events_count=1,
                )
            )

        records = repo.get_for_period(
            active_subscription.id,
            billable_metric.id,
            base_date + timedelta(days=1),
            base_date + timedelta(days=3),
        )
        assert len(records) == 3

    def test_get_for_period_empty(self, db_session, active_subscription, billable_metric):
        """Test getting records when no data exists for the range."""
        repo = DailyUsageRepository(db_session)
        records = repo.get_for_period(
            active_subscription.id,
            billable_metric.id,
            date.today() - timedelta(days=30),
            date.today(),
        )
        assert records == []

    def test_sum_for_period(self, db_session, active_subscription, billable_metric):
        """Test summing usage for a date range."""
        repo = DailyUsageRepository(db_session)
        base_date = date.today() - timedelta(days=5)

        for i in range(3):
            repo.upsert(
                DailyUsageCreate(
                    subscription_id=active_subscription.id,
                    billable_metric_id=billable_metric.id,
                    external_customer_id="sum_cust",
                    usage_date=base_date + timedelta(days=i),
                    usage_value=Decimal("10.5000"),
                    events_count=5,
                )
            )

        total = repo.sum_for_period(
            active_subscription.id,
            billable_metric.id,
            base_date,
            base_date + timedelta(days=2),
        )
        assert total == Decimal("31.5000")

    def test_sum_for_period_empty(self, db_session, active_subscription, billable_metric):
        """Test summing usage when no data exists."""
        repo = DailyUsageRepository(db_session)
        total = repo.sum_for_period(
            active_subscription.id,
            billable_metric.id,
            date.today() - timedelta(days=30),
            date.today(),
        )
        assert total == Decimal("0")

    def test_delete(self, db_session, active_subscription, billable_metric):
        """Test deleting a daily usage record."""
        repo = DailyUsageRepository(db_session)
        record = repo.upsert(
            DailyUsageCreate(
                subscription_id=active_subscription.id,
                billable_metric_id=billable_metric.id,
                external_customer_id="del_cust",
                usage_date=date.today(),
                usage_value=Decimal("5.0000"),
                events_count=1,
            )
        )

        assert repo.delete(record.id) is True
        assert repo.get_by_id(record.id) is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent record."""
        repo = DailyUsageRepository(db_session)
        assert repo.delete(uuid4()) is False

    def test_get_trend_for_subscription_empty(self, db_session, active_subscription):
        """Test trend returns empty list when no usage data exists."""
        repo = DailyUsageRepository(db_session)
        result = repo.get_trend_for_subscription(
            active_subscription.id,
            date.today() - timedelta(days=7),
            date.today(),
        )
        assert result == []

    def test_get_trend_for_subscription_single_metric(
        self, db_session, active_subscription, billable_metric
    ):
        """Test trend with a single metric returns daily data points."""
        repo = DailyUsageRepository(db_session)
        base = date.today() - timedelta(days=2)
        for i in range(3):
            repo.upsert(DailyUsageCreate(
                subscription_id=active_subscription.id,
                billable_metric_id=billable_metric.id,
                external_customer_id="trend_cust",
                usage_date=base + timedelta(days=i),
                usage_value=Decimal(str(10 * (i + 1))),
                events_count=i + 1,
            ))

        result = repo.get_trend_for_subscription(active_subscription.id, base, date.today())
        assert len(result) == 3
        # Sorted by date ascending
        assert result[0][0] == base
        assert result[2][0] == base + timedelta(days=2)
        # Values match
        assert result[0][1] == Decimal("10")
        assert result[1][1] == Decimal("20")
        assert result[2][1] == Decimal("30")

    def test_get_trend_for_subscription_multiple_metrics(
        self, db_session, active_subscription, billable_metric, sum_metric
    ):
        """Test trend aggregates across multiple metrics per day."""
        repo = DailyUsageRepository(db_session)
        today = date.today()

        repo.upsert(DailyUsageCreate(
            subscription_id=active_subscription.id,
            billable_metric_id=billable_metric.id,
            external_customer_id="trend_multi",
            usage_date=today,
            usage_value=Decimal("50"),
            events_count=3,
        ))
        repo.upsert(DailyUsageCreate(
            subscription_id=active_subscription.id,
            billable_metric_id=sum_metric.id,
            external_customer_id="trend_multi",
            usage_date=today,
            usage_value=Decimal("75"),
            events_count=5,
        ))

        result = repo.get_trend_for_subscription(active_subscription.id, today, today)
        assert len(result) == 1
        assert result[0][1] == Decimal("125")  # 50 + 75
        assert result[0][2] == 8  # 3 + 5


class TestDailyUsageService:
    """Tests for DailyUsageService."""

    def test_aggregate_daily_usage_no_subscriptions(self, db_session):
        """Test aggregation when no active subscriptions exist."""
        service = DailyUsageService(db_session)
        count = service.aggregate_daily_usage(date.today() - timedelta(days=1))
        assert count == 0

    def test_aggregate_daily_usage_no_charges(self, db_session, active_subscription):
        """Test aggregation when subscription has no charges (no billable metrics)."""
        service = DailyUsageService(db_session)
        count = service.aggregate_daily_usage(date.today() - timedelta(days=1))
        assert count == 0

    def test_aggregate_daily_usage_with_events(
        self,
        db_session,
        active_subscription,
        charge,
        billable_metric,
        customer,
        events_for_yesterday,
    ):
        """Test aggregation with events produces correct daily usage records."""
        service = DailyUsageService(db_session)
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        count = service.aggregate_daily_usage(yesterday)

        assert count == 1  # One charge = one daily usage record

        # Verify the aggregated record
        repo = DailyUsageRepository(db_session)
        record = repo.get_by_subscription_and_metric(
            UUID(str(active_subscription.id)),
            UUID(str(billable_metric.id)),
            yesterday,
        )
        assert record is not None
        assert Decimal(str(record.usage_value)) == Decimal("3")  # COUNT of 3 events
        assert record.events_count == 3
        assert record.external_customer_id == str(customer.external_id)

    def test_aggregate_daily_usage_default_date(
        self,
        db_session,
        active_subscription,
        charge,
        billable_metric,
        customer,
        events_for_yesterday,
    ):
        """Test aggregation defaults to yesterday when no date is given."""
        service = DailyUsageService(db_session)
        count = service.aggregate_daily_usage()  # defaults to yesterday

        assert count == 1

    def test_aggregate_daily_usage_upsert_behavior(
        self,
        db_session,
        active_subscription,
        charge,
        billable_metric,
        customer,
        events_for_yesterday,
    ):
        """Test that re-aggregating the same date updates existing records."""
        service = DailyUsageService(db_session)
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()

        # First aggregation
        count1 = service.aggregate_daily_usage(yesterday)
        assert count1 == 1

        # Second aggregation should upsert (update)
        count2 = service.aggregate_daily_usage(yesterday)
        assert count2 == 1

        # Should still be just one record
        repo = DailyUsageRepository(db_session)
        records = repo.get_for_period(
            UUID(str(active_subscription.id)),
            UUID(str(billable_metric.id)),
            yesterday,
            yesterday,
        )
        assert len(records) == 1

    def test_aggregate_daily_usage_no_events(
        self, db_session, active_subscription, charge, billable_metric, customer
    ):
        """Test aggregation when there are charges but no events for the date."""
        service = DailyUsageService(db_session)
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        count = service.aggregate_daily_usage(yesterday)

        assert count == 1  # Still creates a record with zero values

        repo = DailyUsageRepository(db_session)
        record = repo.get_by_subscription_and_metric(
            UUID(str(active_subscription.id)),
            UUID(str(billable_metric.id)),
            yesterday,
        )
        assert record is not None
        assert Decimal(str(record.usage_value)) == Decimal("0")
        assert record.events_count == 0

    def test_aggregate_skips_subscription_without_customer(self, db_session, plan, billable_metric):
        """Test aggregation skips subscriptions whose customer was deleted."""
        # Create subscription pointing to a non-existent customer
        # Test the _aggregate_for_subscription method directly
        from app.models.subscription import Subscription

        fake_sub = Subscription(
            external_id=f"orphan_sub_{uuid4()}",
            customer_id=uuid4(),  # non-existent customer
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(fake_sub)
        db_session.commit()

        service = DailyUsageService(db_session)
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        from_ts = datetime(yesterday.year, yesterday.month, yesterday.day)
        to_ts = from_ts + timedelta(days=1)
        result = service._aggregate_for_subscription(fake_sub, yesterday, from_ts, to_ts)
        assert result == 0

    def test_aggregate_skips_missing_metric(self, db_session, active_subscription, customer, plan):
        """Test aggregation skips charges whose billable metric doesn't exist."""
        from app.models.charge import Charge

        orphan_charge = Charge(
            plan_id=plan.id,
            billable_metric_id=uuid4(),  # non-existent metric
            charge_model="standard",
            properties={},
            organization_id=DEFAULT_ORG_ID,
        )
        db_session.add(orphan_charge)
        db_session.commit()

        service = DailyUsageService(db_session)
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        from_ts = datetime(yesterday.year, yesterday.month, yesterday.day)
        to_ts = from_ts + timedelta(days=1)
        # Should not raise, just skip
        result = service._aggregate_for_subscription(active_subscription, yesterday, from_ts, to_ts)
        assert result == 0

    def test_get_usage_for_period(
        self,
        db_session,
        active_subscription,
        billable_metric,
    ):
        """Test get_usage_for_period sums pre-aggregated values."""
        repo = DailyUsageRepository(db_session)
        base_date = date.today() - timedelta(days=5)

        for i in range(3):
            repo.upsert(
                DailyUsageCreate(
                    subscription_id=active_subscription.id,
                    billable_metric_id=billable_metric.id,
                    external_customer_id="period_cust",
                    usage_date=base_date + timedelta(days=i),
                    usage_value=Decimal("15.0000"),
                    events_count=5,
                )
            )

        service = DailyUsageService(db_session)
        total = service.get_usage_for_period(
            UUID(str(active_subscription.id)),
            UUID(str(billable_metric.id)),
            base_date,
            base_date + timedelta(days=2),
        )
        assert total == Decimal("45.0000")

    def test_get_usage_for_period_empty(self, db_session, active_subscription, billable_metric):
        """Test get_usage_for_period returns zero when no data exists."""
        service = DailyUsageService(db_session)
        total = service.get_usage_for_period(
            UUID(str(active_subscription.id)),
            UUID(str(billable_metric.id)),
            date.today() - timedelta(days=30),
            date.today(),
        )
        assert total == Decimal("0")

    def test_aggregate_with_sum_metric(
        self,
        db_session,
        customer,
        plan,
        sum_metric,
    ):
        """Test aggregation with a SUM metric type."""
        # Create charge for the sum metric
        charge_repo = ChargeRepository(db_session)
        charge_repo.create(
            plan.id,
            ChargeCreate(
                billable_metric_id=sum_metric.id,
                charge_model="standard",
                properties={},
            ),
        )

        # Create subscription
        sub_repo = SubscriptionRepository(db_session)
        sub = sub_repo.create(
            SubscriptionCreate(
                external_id=f"sum_sub_{uuid4()}",
                customer_id=customer.id,
                plan_id=plan.id,
                started_at=datetime.now(UTC) - timedelta(days=30),
            ),
            DEFAULT_ORG_ID,
        )

        # Create events for yesterday with bytes data
        yesterday = datetime.now(UTC) - timedelta(days=1)
        yesterday_start = datetime(yesterday.year, yesterday.month, yesterday.day, 10, 0)
        event_repo = EventRepository(db_session)
        event_repo.create(
            EventCreate(
                transaction_id=f"sum_evt1_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(sum_metric.code),
                timestamp=yesterday_start,
                properties={"bytes": 100},
            ),
            DEFAULT_ORG_ID,
        )
        event_repo.create(
            EventCreate(
                transaction_id=f"sum_evt2_{uuid4()}",
                external_customer_id=str(customer.external_id),
                code=str(sum_metric.code),
                timestamp=yesterday_start + timedelta(hours=1),
                properties={"bytes": 250},
            ),
            DEFAULT_ORG_ID,
        )

        service = DailyUsageService(db_session)
        target_date = yesterday.date()
        count = service.aggregate_daily_usage(target_date)

        assert count >= 1  # At least one record for our subscription

        repo = DailyUsageRepository(db_session)
        record = repo.get_by_subscription_and_metric(
            UUID(str(sub.id)), UUID(str(sum_metric.id)), target_date
        )
        assert record is not None
        assert Decimal(str(record.usage_value)) == Decimal("350")
        assert record.events_count == 2

    def test_aggregate_handles_aggregation_error(
        self, db_session, active_subscription, customer, plan, billable_metric, charge, monkeypatch
    ):
        """Test that aggregation errors for a metric are logged and skipped."""
        service = DailyUsageService(db_session)

        # Monkeypatch to force an error during aggregation
        def _raise(*args, **kwargs):
            raise ValueError("Simulated aggregation error")

        monkeypatch.setattr(service.usage_service, "aggregate_usage_with_count", _raise)

        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        from_ts = datetime(yesterday.year, yesterday.month, yesterday.day)
        to_ts = from_ts + timedelta(days=1)
        result = service._aggregate_for_subscription(active_subscription, yesterday, from_ts, to_ts)
        assert result == 0


class TestDailyUsageWorkerTask:
    """Tests for the aggregate_daily_usage_task worker function."""

    @pytest.mark.asyncio
    async def test_aggregate_daily_usage_task(self, db_session, monkeypatch):
        """Test the background task function."""
        from app import worker

        calls = []

        class FakeService:
            def __init__(self, db):
                pass

            def aggregate_daily_usage(self):
                calls.append(1)
                return 5

        monkeypatch.setattr(worker, "DailyUsageService", FakeService)

        result = await worker.aggregate_daily_usage_task({})
        assert result == 5
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_aggregate_daily_usage_task_zero(self, db_session, monkeypatch):
        """Test the background task when no records are aggregated."""
        from app import worker

        class FakeService:
            def __init__(self, db):
                pass

            def aggregate_daily_usage(self):
                return 0

        monkeypatch.setattr(worker, "DailyUsageService", FakeService)

        result = await worker.aggregate_daily_usage_task({})
        assert result == 0


class TestDailyUsageTasksEnqueue:
    """Tests for the enqueue helper in tasks.py."""

    def test_enqueue_function_exists(self):
        """Test that enqueue_aggregate_daily_usage function exists."""
        from app.tasks import enqueue_aggregate_daily_usage

        assert callable(enqueue_aggregate_daily_usage)

    def test_worker_settings_includes_task(self):
        """Test that WorkerSettings includes aggregate_daily_usage_task."""
        from app.worker import WorkerSettings, aggregate_daily_usage_task

        assert aggregate_daily_usage_task in WorkerSettings.functions

    def test_worker_cron_includes_task(self):
        """Test that WorkerSettings cron_jobs includes aggregate_daily_usage_task."""
        from app.worker import WorkerSettings

        cron_funcs = [job.coroutine for job in WorkerSettings.cron_jobs]
        from app.worker import aggregate_daily_usage_task

        assert aggregate_daily_usage_task in cron_funcs


class TestDailyUsageMigration:
    """Tests for the Alembic migration file."""

    def test_migration_file_exists(self):
        """Test that the migration file exists."""
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "app",
            "alembic",
            "versions",
            "20260212_a7v9w0x1y2z3_create_daily_usages_table.py",
        )
        assert os.path.exists(migration_path)
