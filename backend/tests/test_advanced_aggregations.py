"""Tests for advanced aggregation types, rounding, and filters in UsageAggregationService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.database import get_db
from app.models.billable_metric import AggregationType
from app.models.event import Event
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.event_repository import EventRepository
from app.schemas.billable_metric import BillableMetricCreate
from app.schemas.event import EventCreate
from app.services.usage_aggregation import (
    UsageAggregationService,
    _apply_rounding,
    _evaluate_expression,
    _is_numeric,
)


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
def weighted_sum_metric(db_session):
    repo = BillableMetricRepository(db_session)
    return repo.create(
        BillableMetricCreate(
            code="cpu_usage",
            name="CPU Usage",
            aggregation_type=AggregationType.WEIGHTED_SUM,
            field_name="cpu_percent",
        )
    )


@pytest.fixture
def latest_metric(db_session):
    repo = BillableMetricRepository(db_session)
    return repo.create(
        BillableMetricCreate(
            code="temperature",
            name="Temperature",
            aggregation_type=AggregationType.LATEST,
            field_name="temp_value",
        )
    )


@pytest.fixture
def custom_metric(db_session):
    repo = BillableMetricRepository(db_session)
    return repo.create(
        BillableMetricCreate(
            code="compute_cost",
            name="Compute Cost",
            aggregation_type=AggregationType.CUSTOM,
            expression="cpu * hours + memory * 0.5",
        )
    )


@pytest.fixture
def sum_metric_with_rounding(db_session):
    repo = BillableMetricRepository(db_session)
    return repo.create(
        BillableMetricCreate(
            code="data_rounded",
            name="Data Rounded",
            aggregation_type=AggregationType.SUM,
            field_name="amount",
            rounding_function="round",
            rounding_precision=2,
        )
    )


@pytest.fixture
def count_metric(db_session):
    repo = BillableMetricRepository(db_session)
    return repo.create(
        BillableMetricCreate(
            code="api_calls_adv",
            name="API Calls Adv",
            aggregation_type=AggregationType.COUNT,
        )
    )


@pytest.fixture
def sum_metric(db_session):
    repo = BillableMetricRepository(db_session)
    return repo.create(
        BillableMetricCreate(
            code="data_transfer_adv",
            name="Data Transfer Adv",
            aggregation_type=AggregationType.SUM,
            field_name="bytes",
        )
    )


class TestWeightedSumAggregation:
    def test_weighted_sum_basic(self, db_session, weighted_sum_metric):
        """Test WEIGHTED_SUM with varying time intervals."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        # 24-hour period
        end_time = base_time + timedelta(hours=24)

        # Event at hour 0 with value 50 (holds for 12 hours -> 50 * 12/24 = 25)
        event_repo.create(
            EventCreate(
                transaction_id="ws-1",
                external_customer_id="cust-001",
                code="cpu_usage",
                timestamp=base_time,
                properties={"cpu_percent": 50},
            )
        )
        # Event at hour 12 with value 100 (holds for 12 hours -> 100 * 12/24 = 50)
        event_repo.create(
            EventCreate(
                transaction_id="ws-2",
                external_customer_id="cust-001",
                code="cpu_usage",
                timestamp=base_time + timedelta(hours=12),
                properties={"cpu_percent": 100},
            )
        )

        result = service.aggregate_usage_with_count(
            external_customer_id="cust-001",
            code="cpu_usage",
            from_timestamp=base_time,
            to_timestamp=end_time,
        )

        # 50 * 12/24 + 100 * 12/24 = 25 + 50 = 75
        assert result.value == Decimal(75)
        assert result.events_count == 2

    def test_weighted_sum_single_event(self, db_session, weighted_sum_metric):
        """Test WEIGHTED_SUM with a single event spanning the entire period."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        end_time = base_time + timedelta(hours=24)

        event_repo.create(
            EventCreate(
                transaction_id="ws-single-1",
                external_customer_id="cust-001",
                code="cpu_usage",
                timestamp=base_time,
                properties={"cpu_percent": 80},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="cpu_usage",
            from_timestamp=base_time,
            to_timestamp=end_time,
        )

        # 80 * 24/24 = 80
        assert result == Decimal(80)

    def test_weighted_sum_no_events(self, db_session, weighted_sum_metric):
        """Test WEIGHTED_SUM with no events returns 0."""
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        result = service.aggregate_usage_with_count(
            external_customer_id="cust-001",
            code="cpu_usage",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(hours=24),
        )

        assert result.value == Decimal(0)
        assert result.events_count == 0

    def test_weighted_sum_zero_duration(self, db_session, weighted_sum_metric):
        """Test WEIGHTED_SUM with zero-duration period returns 0."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        event_repo.create(
            EventCreate(
                transaction_id="ws-zero-dur-1",
                external_customer_id="cust-001",
                code="cpu_usage",
                timestamp=base_time,
                properties={"cpu_percent": 50},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="cpu_usage",
            from_timestamp=base_time,
            to_timestamp=base_time,  # same start and end
        )

        assert result == Decimal(0)

    def test_weighted_sum_no_field_name(self, db_session):
        """Test WEIGHTED_SUM requires field_name."""
        repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="ws_no_field",
            name="WS No Field",
            aggregation_type=AggregationType.WEIGHTED_SUM,
            field_name="temp",
        )
        metric = repo.create(data)
        metric.field_name = None
        db_session.commit()

        service = UsageAggregationService(db_session)
        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError, match="requires field_name for WEIGHTED_SUM"):
            service.aggregate_usage(
                external_customer_id="cust-001",
                code="ws_no_field",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(hours=1),
            )

    def test_weighted_sum_three_events(self, db_session, weighted_sum_metric):
        """Test WEIGHTED_SUM with three events at different intervals."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        end_time = base_time + timedelta(hours=10)

        # Value 10 for 2 hours, value 20 for 3 hours, value 30 for 5 hours
        event_repo.create(
            EventCreate(
                transaction_id="ws-three-1",
                external_customer_id="cust-001",
                code="cpu_usage",
                timestamp=base_time,
                properties={"cpu_percent": 10},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="ws-three-2",
                external_customer_id="cust-001",
                code="cpu_usage",
                timestamp=base_time + timedelta(hours=2),
                properties={"cpu_percent": 20},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="ws-three-3",
                external_customer_id="cust-001",
                code="cpu_usage",
                timestamp=base_time + timedelta(hours=5),
                properties={"cpu_percent": 30},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="cpu_usage",
            from_timestamp=base_time,
            to_timestamp=end_time,
        )

        # 10 * 2/10 + 20 * 3/10 + 30 * 5/10 = 2 + 6 + 15 = 23
        assert result == Decimal(23)

    def test_weighted_sum_missing_field_defaults_zero(self, db_session, weighted_sum_metric):
        """Test WEIGHTED_SUM treats missing field values as 0."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        end_time = base_time + timedelta(hours=10)

        event_repo.create(
            EventCreate(
                transaction_id="ws-missing-1",
                external_customer_id="cust-001",
                code="cpu_usage",
                timestamp=base_time,
                properties={},  # missing cpu_percent
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="cpu_usage",
            from_timestamp=base_time,
            to_timestamp=end_time,
        )

        assert result == Decimal(0)


class TestLatestAggregation:
    def test_latest_basic(self, db_session, latest_metric):
        """Test LATEST returns the most recent event's value."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="lat-1",
                external_customer_id="cust-001",
                code="temperature",
                timestamp=base_time,
                properties={"temp_value": 20},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="lat-2",
                external_customer_id="cust-001",
                code="temperature",
                timestamp=base_time + timedelta(hours=1),
                properties={"temp_value": 25},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="lat-3",
                external_customer_id="cust-001",
                code="temperature",
                timestamp=base_time + timedelta(hours=2),
                properties={"temp_value": 30},
            )
        )

        result = service.aggregate_usage_with_count(
            external_customer_id="cust-001",
            code="temperature",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result.value == Decimal(30)  # most recent
        assert result.events_count == 3

    def test_latest_no_events(self, db_session, latest_metric):
        """Test LATEST with no events returns 0."""
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        result = service.aggregate_usage_with_count(
            external_customer_id="cust-001",
            code="temperature",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result.value == Decimal(0)
        assert result.events_count == 0

    def test_latest_missing_field(self, db_session, latest_metric):
        """Test LATEST with missing field defaults to 0."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="lat-miss-1",
                external_customer_id="cust-001",
                code="temperature",
                timestamp=base_time,
                properties={},  # missing temp_value
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="temperature",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(0)

    def test_latest_no_field_name(self, db_session):
        """Test LATEST requires field_name."""
        repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="lat_no_field",
            name="Lat No Field",
            aggregation_type=AggregationType.LATEST,
            field_name="temp",
        )
        metric = repo.create(data)
        metric.field_name = None
        db_session.commit()

        service = UsageAggregationService(db_session)
        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError, match="requires field_name for LATEST"):
            service.aggregate_usage(
                external_customer_id="cust-001",
                code="lat_no_field",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(hours=1),
            )


class TestCustomAggregation:
    def test_custom_basic(self, db_session, custom_metric):
        """Test CUSTOM aggregation evaluates expression per event."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        # expression = "cpu * hours + memory * 0.5"
        event_repo.create(
            EventCreate(
                transaction_id="cust-expr-1",
                external_customer_id="cust-001",
                code="compute_cost",
                timestamp=base_time,
                properties={"cpu": 4, "hours": 10, "memory": 16},
            )
        )
        # 4 * 10 + 16 * 0.5 = 40 + 8 = 48

        event_repo.create(
            EventCreate(
                transaction_id="cust-expr-2",
                external_customer_id="cust-001",
                code="compute_cost",
                timestamp=base_time + timedelta(hours=1),
                properties={"cpu": 2, "hours": 5, "memory": 8},
            )
        )
        # 2 * 5 + 8 * 0.5 = 10 + 4 = 14

        result = service.aggregate_usage_with_count(
            external_customer_id="cust-001",
            code="compute_cost",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result.value == Decimal(62)  # 48 + 14
        assert result.events_count == 2

    def test_custom_no_events(self, db_session, custom_metric):
        """Test CUSTOM with no events returns 0."""
        service = UsageAggregationService(db_session)
        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        result = service.aggregate_usage_with_count(
            external_customer_id="cust-001",
            code="compute_cost",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result.value == Decimal(0)
        assert result.events_count == 0

    def test_custom_no_expression(self, db_session):
        """Test CUSTOM requires expression."""
        repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="cust_no_expr",
            name="Custom No Expr",
            aggregation_type=AggregationType.CUSTOM,
            expression="x + y",
        )
        metric = repo.create(data)
        metric.expression = None
        db_session.commit()

        service = UsageAggregationService(db_session)
        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError, match="requires expression for CUSTOM"):
            service.aggregate_usage(
                external_customer_id="cust-001",
                code="cust_no_expr",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(hours=1),
            )

    def test_custom_with_parentheses(self, db_session):
        """Test CUSTOM expression with parentheses."""
        repo = BillableMetricRepository(db_session)
        repo.create(
            BillableMetricCreate(
                code="paren_expr",
                name="Paren Expr",
                aggregation_type=AggregationType.CUSTOM,
                expression="(a + b) * c",
            )
        )

        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="paren-1",
                external_customer_id="cust-001",
                code="paren_expr",
                timestamp=base_time,
                properties={"a": 2, "b": 3, "c": 4},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="paren_expr",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        # (2 + 3) * 4 = 20
        assert result == Decimal(20)

    def test_custom_ignores_non_numeric_properties(self, db_session):
        """Test CUSTOM aggregation ignores non-numeric event properties."""
        repo = BillableMetricRepository(db_session)
        repo.create(
            BillableMetricCreate(
                code="simple_sum",
                name="Simple Sum",
                aggregation_type=AggregationType.CUSTOM,
                expression="x + y",
            )
        )

        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="nonnumeric-1",
                external_customer_id="cust-001",
                code="simple_sum",
                timestamp=base_time,
                properties={"x": 5, "y": 3, "label": "test"},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="simple_sum",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(8)

    def test_custom_unknown_variable_raises(self, db_session):
        """Test CUSTOM expression with unknown variable raises error."""
        repo = BillableMetricRepository(db_session)
        repo.create(
            BillableMetricCreate(
                code="unknown_var",
                name="Unknown Var",
                aggregation_type=AggregationType.CUSTOM,
                expression="x + missing_var",
            )
        )

        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="unknown-var-1",
                external_customer_id="cust-001",
                code="unknown_var",
                timestamp=base_time,
                properties={"x": 5},
            )
        )

        with pytest.raises(ValueError, match="Unknown variable"):
            service.aggregate_usage(
                external_customer_id="cust-001",
                code="unknown_var",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(days=1),
            )

    def test_custom_division_by_zero(self, db_session):
        """Test CUSTOM expression with division by zero raises error."""
        repo = BillableMetricRepository(db_session)
        repo.create(
            BillableMetricCreate(
                code="div_zero",
                name="Div Zero",
                aggregation_type=AggregationType.CUSTOM,
                expression="x / y",
            )
        )

        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="div-zero-1",
                external_customer_id="cust-001",
                code="div_zero",
                timestamp=base_time,
                properties={"x": 10, "y": 0},
            )
        )

        with pytest.raises(ValueError, match="Division by zero"):
            service.aggregate_usage(
                external_customer_id="cust-001",
                code="div_zero",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(days=1),
            )


class TestRounding:
    def test_round_half_up(self, db_session, sum_metric_with_rounding):
        """Test rounding with round function (half up)."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        # Create events that sum to 10.555
        event_repo.create(
            EventCreate(
                transaction_id="round-1",
                external_customer_id="cust-001",
                code="data_rounded",
                timestamp=base_time,
                properties={"amount": 10.555},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="data_rounded",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        # round(10.555, 2) = 10.56 (half up)
        assert result == Decimal("10.56")

    def test_ceil_rounding(self, db_session):
        """Test ceil rounding function."""
        repo = BillableMetricRepository(db_session)
        repo.create(
            BillableMetricCreate(
                code="ceil_metric",
                name="Ceil Metric",
                aggregation_type=AggregationType.SUM,
                field_name="amount",
                rounding_function="ceil",
                rounding_precision=0,
            )
        )

        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="ceil-1",
                external_customer_id="cust-001",
                code="ceil_metric",
                timestamp=base_time,
                properties={"amount": 10.1},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="ceil_metric",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(11)  # ceil(10.1) = 11

    def test_floor_rounding(self, db_session):
        """Test floor rounding function."""
        repo = BillableMetricRepository(db_session)
        repo.create(
            BillableMetricCreate(
                code="floor_metric",
                name="Floor Metric",
                aggregation_type=AggregationType.SUM,
                field_name="amount",
                rounding_function="floor",
                rounding_precision=0,
            )
        )

        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="floor-1",
                external_customer_id="cust-001",
                code="floor_metric",
                timestamp=base_time,
                properties={"amount": 10.9},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="floor_metric",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(10)  # floor(10.9) = 10

    def test_rounding_with_precision(self, db_session):
        """Test rounding with specific precision."""
        repo = BillableMetricRepository(db_session)
        repo.create(
            BillableMetricCreate(
                code="precision_metric",
                name="Precision Metric",
                aggregation_type=AggregationType.SUM,
                field_name="amount",
                rounding_function="floor",
                rounding_precision=1,
            )
        )

        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="prec-1",
                external_customer_id="cust-001",
                code="precision_metric",
                timestamp=base_time,
                properties={"amount": 10.99},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="precision_metric",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal("10.9")  # floor to 1 decimal: 10.9

    def test_no_rounding_when_not_configured(self, db_session, sum_metric):
        """Test no rounding applied when metric has no rounding config."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="no-round-1",
                external_customer_id="cust-001",
                code="data_transfer_adv",
                timestamp=base_time,
                properties={"bytes": 10.555},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="data_transfer_adv",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal("10.555")

    def test_rounding_function_without_precision_defaults_to_zero(self, db_session):
        """Test rounding_function without precision defaults to 0 decimal places."""
        repo = BillableMetricRepository(db_session)
        data = BillableMetricCreate(
            code="round_no_prec",
            name="Round No Prec",
            aggregation_type=AggregationType.SUM,
            field_name="amount",
            rounding_function="round",
        )
        repo.create(data)

        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="rnp-1",
                external_customer_id="cust-001",
                code="round_no_prec",
                timestamp=base_time,
                properties={"amount": 10.6},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="round_no_prec",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(11)  # round(10.6, 0) = 11


class TestFilterSupport:
    def test_filter_by_single_property(self, db_session, count_metric):
        """Test filtering events by a single property."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        # Create events with different regions
        event_repo.create(
            EventCreate(
                transaction_id="filt-1",
                external_customer_id="cust-001",
                code="api_calls_adv",
                timestamp=base_time,
                properties={"region": "us-east"},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="filt-2",
                external_customer_id="cust-001",
                code="api_calls_adv",
                timestamp=base_time + timedelta(hours=1),
                properties={"region": "eu-west"},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="filt-3",
                external_customer_id="cust-001",
                code="api_calls_adv",
                timestamp=base_time + timedelta(hours=2),
                properties={"region": "us-east"},
            )
        )

        result = service.aggregate_usage_with_count(
            external_customer_id="cust-001",
            code="api_calls_adv",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
            filters={"region": "us-east"},
        )

        assert result.value == Decimal(2)  # only us-east events
        assert result.events_count == 2

    def test_filter_by_multiple_properties(self, db_session, count_metric):
        """Test filtering events by multiple properties."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="multi-filt-1",
                external_customer_id="cust-001",
                code="api_calls_adv",
                timestamp=base_time,
                properties={"region": "us-east", "tier": "premium"},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="multi-filt-2",
                external_customer_id="cust-001",
                code="api_calls_adv",
                timestamp=base_time + timedelta(hours=1),
                properties={"region": "us-east", "tier": "basic"},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="multi-filt-3",
                external_customer_id="cust-001",
                code="api_calls_adv",
                timestamp=base_time + timedelta(hours=2),
                properties={"region": "eu-west", "tier": "premium"},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="api_calls_adv",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
            filters={"region": "us-east", "tier": "premium"},
        )

        assert result == Decimal(1)  # only one matches both

    def test_filter_no_match(self, db_session, count_metric):
        """Test filter with no matching events returns 0."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="no-match-1",
                external_customer_id="cust-001",
                code="api_calls_adv",
                timestamp=base_time,
                properties={"region": "us-east"},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="api_calls_adv",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
            filters={"region": "ap-south"},
        )

        assert result == Decimal(0)

    def test_filter_with_sum_aggregation(self, db_session, sum_metric):
        """Test filter works with SUM aggregation."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="filt-sum-1",
                external_customer_id="cust-001",
                code="data_transfer_adv",
                timestamp=base_time,
                properties={"bytes": 100, "region": "us-east"},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="filt-sum-2",
                external_customer_id="cust-001",
                code="data_transfer_adv",
                timestamp=base_time + timedelta(hours=1),
                properties={"bytes": 200, "region": "eu-west"},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="filt-sum-3",
                external_customer_id="cust-001",
                code="data_transfer_adv",
                timestamp=base_time + timedelta(hours=2),
                properties={"bytes": 300, "region": "us-east"},
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="data_transfer_adv",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
            filters={"region": "us-east"},
        )

        assert result == Decimal(400)  # 100 + 300

    def test_no_filter_returns_all(self, db_session, count_metric):
        """Test no filters returns all events (backward compatible)."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        for i in range(3):
            event_repo.create(
                EventCreate(
                    transaction_id=f"all-{i}",
                    external_customer_id="cust-001",
                    code="api_calls_adv",
                    timestamp=base_time + timedelta(hours=i),
                    properties={"region": f"region-{i}"},
                )
            )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="api_calls_adv",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
        )

        assert result == Decimal(3)

    def test_filter_missing_property_excluded(self, db_session, count_metric):
        """Test events without the filter property are excluded."""
        event_repo = EventRepository(db_session)
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        event_repo.create(
            EventCreate(
                transaction_id="miss-prop-1",
                external_customer_id="cust-001",
                code="api_calls_adv",
                timestamp=base_time,
                properties={"region": "us-east"},
            )
        )
        event_repo.create(
            EventCreate(
                transaction_id="miss-prop-2",
                external_customer_id="cust-001",
                code="api_calls_adv",
                timestamp=base_time + timedelta(hours=1),
                properties={},  # no region property
            )
        )

        result = service.aggregate_usage(
            external_customer_id="cust-001",
            code="api_calls_adv",
            from_timestamp=base_time,
            to_timestamp=base_time + timedelta(days=1),
            filters={"region": "us-east"},
        )

        assert result == Decimal(1)


class TestExpressionEvaluator:
    """Direct tests for the expression evaluator."""

    def test_simple_addition(self):
        result = _evaluate_expression("a + b", {"a": Decimal(3), "b": Decimal(5)})
        assert result == Decimal(8)

    def test_multiplication_before_addition(self):
        result = _evaluate_expression(
            "a + b * c", {"a": Decimal(2), "b": Decimal(3), "c": Decimal(4)}
        )
        # 2 + 3*4 = 14
        assert result == Decimal(14)

    def test_parentheses_override_precedence(self):
        result = _evaluate_expression(
            "(a + b) * c", {"a": Decimal(2), "b": Decimal(3), "c": Decimal(4)}
        )
        assert result == Decimal(20)

    def test_subtraction(self):
        result = _evaluate_expression("a - b", {"a": Decimal(10), "b": Decimal(3)})
        assert result == Decimal(7)

    def test_division(self):
        result = _evaluate_expression("a / b", {"a": Decimal(10), "b": Decimal(4)})
        assert result == Decimal("2.5")

    def test_number_literals(self):
        result = _evaluate_expression("x * 100", {"x": Decimal(5)})
        assert result == Decimal(500)

    def test_decimal_literals(self):
        result = _evaluate_expression("x * 0.5", {"x": Decimal(10)})
        assert result == Decimal(5)

    def test_empty_expression(self):
        with pytest.raises(ValueError, match="Empty expression"):
            _evaluate_expression("", {})

    def test_unexpected_end(self):
        with pytest.raises(ValueError, match="Unexpected end"):
            _evaluate_expression("(a +", {"a": Decimal(1)})

    def test_missing_closing_paren(self):
        with pytest.raises(ValueError, match="Expected '\\)'"):
            _evaluate_expression("(a + b", {"a": Decimal(1), "b": Decimal(2)})

    def test_extra_tokens(self):
        with pytest.raises(ValueError, match="Unexpected tokens"):
            _evaluate_expression("a b", {"a": Decimal(1), "b": Decimal(2)})

    def test_division_by_zero(self):
        with pytest.raises(ValueError, match="Division by zero"):
            _evaluate_expression("a / b", {"a": Decimal(10), "b": Decimal(0)})

    def test_unknown_variable(self):
        with pytest.raises(ValueError, match="Unknown variable"):
            _evaluate_expression("x + y", {"x": Decimal(1)})


class TestApplyRounding:
    """Direct tests for _apply_rounding."""

    def test_no_rounding(self):
        assert _apply_rounding(Decimal("10.555"), None, None) == Decimal("10.555")

    def test_round_half_up(self):
        assert _apply_rounding(Decimal("10.555"), "round", 2) == Decimal("10.56")

    def test_ceil(self):
        assert _apply_rounding(Decimal("10.1"), "ceil", 0) == Decimal("11")

    def test_floor(self):
        assert _apply_rounding(Decimal("10.9"), "floor", 0) == Decimal("10")

    def test_round_default_precision(self):
        assert _apply_rounding(Decimal("10.5"), "round", None) == Decimal("11")

    def test_unknown_rounding_function(self):
        with pytest.raises(ValueError, match="Unknown rounding function"):
            _apply_rounding(Decimal("10.5"), "truncate", 0)


class TestIsNumeric:
    """Direct tests for _is_numeric."""

    def test_integer(self):
        assert _is_numeric(42) is True

    def test_float(self):
        assert _is_numeric(3.14) is True

    def test_numeric_string(self):
        assert _is_numeric("100") is True

    def test_non_numeric_string(self):
        assert _is_numeric("hello") is False

    def test_none(self):
        assert _is_numeric(None) is False


class TestComputeAggregationEdgeCases:
    """Tests for edge cases in _compute_aggregation accessed directly."""

    def test_weighted_sum_zero_duration_with_events(self, db_session, weighted_sum_metric):
        """Test WEIGHTED_SUM with zero-duration period but events present."""
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        # Create a fake event object directly (not via DB) to pass to _compute_aggregation
        fake_event = Event(
            transaction_id="zero-dur-evt",
            external_customer_id="cust-001",
            code="cpu_usage",
            timestamp=base_time,
            properties={"cpu_percent": 50},
        )

        result = service._compute_aggregation(
            aggregation_type=AggregationType.WEIGHTED_SUM,
            metric=weighted_sum_metric,
            events=[fake_event],
            events_count=1,
            code="cpu_usage",
            from_timestamp=base_time,
            to_timestamp=base_time,  # same as from = zero duration
        )

        assert result.value == Decimal(0)
        assert result.events_count == 1

    def test_unknown_aggregation_type_in_compute(self, db_session, count_metric):
        """Test _compute_aggregation raises on unknown aggregation type."""
        service = UsageAggregationService(db_session)

        base_time = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

        with pytest.raises(ValueError, match="Unknown aggregation type"):
            service._compute_aggregation(
                aggregation_type="invalid",  # type: ignore[arg-type]
                metric=count_metric,
                events=[],
                events_count=0,
                code="api_calls_adv",
                from_timestamp=base_time,
                to_timestamp=base_time + timedelta(hours=1),
            )
