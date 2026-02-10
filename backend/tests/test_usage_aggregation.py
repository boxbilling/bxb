"""Usage Aggregation Service tests for bxb."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.database import Base, engine, get_db
from app.models.billable_metric import AggregationType
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.event_repository import EventRepository
from app.schemas.billable_metric import BillableMetricCreate
from app.schemas.event import EventCreate
from app.services.usage_aggregation import UsageAggregationService


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
def count_metric(db_session):
    """Create a COUNT billable metric."""
    repo = BillableMetricRepository(db_session)
    data = BillableMetricCreate(
        code="api_calls",
        name="API Calls",
        aggregation_type=AggregationType.COUNT,
    )
    return repo.create(data)


@pytest.fixture
def sum_metric(db_session):
    """Create a SUM billable metric."""
    repo = BillableMetricRepository(db_session)
    data = BillableMetricCreate(
        code="data_transfer",
        name="Data Transfer",
        aggregation_type=AggregationType.SUM,
        field_name="bytes",
    )
    return repo.create(data)


@pytest.fixture
def max_metric(db_session):
    """Create a MAX billable metric."""
    repo = BillableMetricRepository(db_session)
    data = BillableMetricCreate(
        code="peak_connections",
        name="Peak Connections",
        aggregation_type=AggregationType.MAX,
        field_name="connections",
    )
    return repo.create(data)


@pytest.fixture
def unique_count_metric(db_session):
    """Create a UNIQUE_COUNT billable metric."""
    repo = BillableMetricRepository(db_session)
    data = BillableMetricCreate(
        code="unique_users",
        name="Unique Users",
        aggregation_type=AggregationType.UNIQUE_COUNT,
        field_name="user_id",
    )
    return repo.create(data)


class TestUsageAggregationService:
    def test_aggregate_count(self, db_session, count_metric):
        """Test COUNT aggregation."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create 5 events
        for i in range(5):
            event_repo.create(
                EventCreate(
                    transaction_id=f"count-test-{i}",
                    external_customer_id="cust-001",
                    code="api_calls",
                    timestamp=base_time + timedelta(hours=i),
                )
            )

        # Aggregate
        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="api_calls",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(5)

    def test_aggregate_sum(self, db_session, sum_metric):
        """Test SUM aggregation."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create events with different byte values
        bytes_values = [100, 200, 150, 50]
        for i, bytes_val in enumerate(bytes_values):
            event_repo.create(
                EventCreate(
                    transaction_id=f"sum-test-{i}",
                    external_customer_id="cust-001",
                    code="data_transfer",
                    timestamp=base_time + timedelta(hours=i),
                    properties={"bytes": bytes_val},
                )
            )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="data_transfer",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(500)  # 100 + 200 + 150 + 50

    def test_aggregate_max(self, db_session, max_metric):
        """Test MAX aggregation."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create events with different connection values
        connection_values = [10, 50, 30, 25]
        for i, conn_val in enumerate(connection_values):
            event_repo.create(
                EventCreate(
                    transaction_id=f"max-test-{i}",
                    external_customer_id="cust-001",
                    code="peak_connections",
                    timestamp=base_time + timedelta(hours=i),
                    properties={"connections": conn_val},
                )
            )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="peak_connections",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(50)  # max value

    def test_aggregate_unique_count(self, db_session, unique_count_metric):
        """Test UNIQUE_COUNT aggregation."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create events with some duplicate user_ids
        user_ids = ["user-1", "user-2", "user-1", "user-3", "user-2"]
        for i, user_id in enumerate(user_ids):
            event_repo.create(
                EventCreate(
                    transaction_id=f"unique-test-{i}",
                    external_customer_id="cust-001",
                    code="unique_users",
                    timestamp=base_time + timedelta(hours=i),
                    properties={"user_id": user_id},
                )
            )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="unique_users",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(3)  # 3 unique users

    def test_aggregate_filters_by_time_range(self, db_session, count_metric):
        """Test that aggregation filters by time range."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create events at different times
        # 2 inside range, 2 outside
        event_repo.create(
            EventCreate(
                transaction_id="time-test-1",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=base_time + timedelta(hours=1),  # inside
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="time-test-2",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=base_time + timedelta(hours=2),  # inside
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="time-test-3",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=base_time - timedelta(hours=1),  # before range
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="time-test-4",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=base_time + timedelta(days=2),  # after range
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="api_calls",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(2)  # only 2 inside range

    def test_aggregate_filters_by_customer(self, db_session, count_metric):
        """Test that aggregation filters by customer."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create events for different customers
        for i in range(3):
            event_repo.create(
                EventCreate(
                    transaction_id=f"cust1-test-{i}",
                    external_customer_id="cust-001",
                    code="api_calls",
                    timestamp=base_time + timedelta(hours=i),
                )
            )
        for i in range(2):
            event_repo.create(
                EventCreate(
                    transaction_id=f"cust2-test-{i}",
                    external_customer_id="cust-002",
                    code="api_calls",
                    timestamp=base_time + timedelta(hours=i),
                )
            )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="api_calls",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(3)  # only cust-001's events

    def test_aggregate_no_events(self, db_session, count_metric):
        """Test aggregation with no matching events."""
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="api_calls",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(0)

    def test_aggregate_max_no_events(self, db_session, max_metric):
        """Test MAX aggregation with no events returns 0."""
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="peak_connections",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(0)

    def test_aggregate_unique_count_no_events(self, db_session, unique_count_metric):
        """Test UNIQUE_COUNT aggregation with no events."""
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="unique_users",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(0)

    def test_aggregate_unknown_metric(self, db_session):
        """Test aggregation with unknown metric code."""
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError, match="not found"):
            service.aggregate_usage(
                external_customer_id="cust-001",
                code="nonexistent",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(days=1),
            )

    def test_aggregate_sum_missing_field(self, db_session, sum_metric):
        """Test SUM aggregation handles missing field values."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create event without the bytes field
        event_repo.create(
            EventCreate(
                transaction_id="missing-field-test",
                external_customer_id="cust-001",
                code="data_transfer",
                timestamp=base_time,
                properties={"other_field": "value"},  # missing bytes
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="data_transfer",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(0)  # defaults to 0 for missing field

    def test_get_customer_usage_summary(self, db_session, count_metric, sum_metric, max_metric):
        """Test getting usage summary for all metrics."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create events for different metrics
        for i in range(3):
            event_repo.create(
                EventCreate(
                    transaction_id=f"summary-api-{i}",
                    external_customer_id="cust-001",
                    code="api_calls",
                    timestamp=base_time + timedelta(hours=i),
                )
            )

        for i in range(2):
            event_repo.create(
                EventCreate(
                    transaction_id=f"summary-data-{i}",
                    external_customer_id="cust-001",
                    code="data_transfer",
                    timestamp=base_time + timedelta(hours=i),
                    properties={"bytes": 100 * (i + 1)},
                )
            )

        summary = service.get_customer_usage_summary(
            external_customer_id="cust-001",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert "api_calls" in summary
        assert summary["api_calls"] == Decimal(3)
        assert "data_transfer" in summary
        assert summary["data_transfer"] == Decimal(300)  # 100 + 200
        assert "peak_connections" not in summary  # no events for this

    def test_get_customer_usage_summary_empty(self, db_session, count_metric):
        """Test usage summary with no events."""
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        summary = service.get_customer_usage_summary(
            external_customer_id="cust-001",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert summary == {}

    def test_aggregate_unique_count_with_none_values(self, db_session, unique_count_metric):
        """Test UNIQUE_COUNT skips None values."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create events with some None user_ids
        event_repo.create(
            EventCreate(
                transaction_id="unique-none-1",
                external_customer_id="cust-001",
                code="unique_users",
                timestamp=base_time,
                properties={"user_id": "user-1"},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="unique-none-2",
                external_customer_id="cust-001",
                code="unique_users",
                timestamp=base_time + timedelta(hours=1),
                properties={},  # missing user_id
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="unique-none-3",
                external_customer_id="cust-001",
                code="unique_users",
                timestamp=base_time + timedelta(hours=2),
                properties={"user_id": "user-2"},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="unique_users",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(2)  # only user-1 and user-2

    def test_aggregate_sum_no_field_name(self, db_session):
        """Test SUM aggregation requires field_name."""
        # Create a SUM metric without field_name (invalid but possible in DB)
        metric_repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="sum_no_field",
            name="Sum No Field",
            aggregation_type=AggregationType.SUM,
            field_name="temp",  # Create with field_name first
        )
        metric = metric_repo.create(data)

        # Manually remove field_name
        metric.field_name = None
        db_session.commit()

        service = UsageAggregationService(db_session)
        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError, match="requires field_name for SUM"):
            service.aggregate_usage(
                external_customer_id="cust-001",
                code="sum_no_field",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(days=1),
            )

    def test_aggregate_max_no_field_name(self, db_session):
        """Test MAX aggregation requires field_name."""
        metric_repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="max_no_field",
            name="Max No Field",
            aggregation_type=AggregationType.MAX,
            field_name="temp",
        )
        metric = metric_repo.create(data)

        # Manually remove field_name
        metric.field_name = None
        db_session.commit()

        service = UsageAggregationService(db_session)
        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError, match="requires field_name for MAX"):
            service.aggregate_usage(
                external_customer_id="cust-001",
                code="max_no_field",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(days=1),
            )

    def test_aggregate_unique_count_no_field_name(self, db_session):
        """Test UNIQUE_COUNT aggregation requires field_name."""
        metric_repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="unique_no_field",
            name="Unique No Field",
            aggregation_type=AggregationType.UNIQUE_COUNT,
            field_name="temp",
        )
        metric = metric_repo.create(data)

        # Manually remove field_name
        metric.field_name = None
        db_session.commit()

        service = UsageAggregationService(db_session)
        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError, match="requires field_name for UNIQUE_COUNT"):
            service.aggregate_usage(
                external_customer_id="cust-001",
                code="unique_no_field",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(days=1),
            )

    def test_aggregate_unknown_aggregation_type(self, db_session):
        """Test unknown aggregation type raises error."""
        metric_repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="unknown_agg",
            name="Unknown Agg",
            aggregation_type=AggregationType.COUNT,
        )
        metric = metric_repo.create(data)

        # Manually set an invalid aggregation type
        metric.aggregation_type = "invalid_type"
        db_session.commit()

        service = UsageAggregationService(db_session)
        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError, match="invalid_type"):
            service.aggregate_usage(
                external_customer_id="cust-001",
                code="unknown_agg",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(days=1),
            )

    def test_get_customer_usage_summary_skips_missing_metrics(self, db_session, count_metric):
        """Test usage summary skips events for deleted metrics."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)

        # Create events for the existing metric
        event_repo.create(
            EventCreate(
                transaction_id="summary-skip-1",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=base_time,
            )
        )

        # Create an event for a metric code that doesn't exist
        # We'll manually insert an event with a non-existent metric code
        from app.models.event import Event

        orphan_event = Event(
            transaction_id="orphan-event",
            external_customer_id="cust-001",
            code="deleted_metric",
            timestamp=base_time,
            properties={},
        )
        db_session.add(orphan_event)
        db_session.commit()

        summary = service.get_customer_usage_summary(
            external_customer_id="cust-001",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        # Should only include api_calls, not deleted_metric
        assert "api_calls" in summary
        assert summary["api_calls"] == Decimal(1)
        assert "deleted_metric" not in summary
