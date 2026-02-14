"""Tests for ClickHouse integration: client, event store, aggregation, events_query, and dual-write."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.core.clickhouse import (
    CREATE_EVENTS_RAW_TABLE,
    _parse_clickhouse_url,
    get_clickhouse_client,
    reset_client,
)
from app.core.config import Settings
from app.models.billable_metric import AggregationType
from app.schemas.event import EventCreate
from app.services.clickhouse_aggregation import (
    _build_filter_clause,
    _build_filter_params,
    aggregate_count,
    aggregate_custom,
    aggregate_latest,
    aggregate_max,
    aggregate_sum,
    aggregate_unique_count,
    aggregate_weighted_sum,
    clickhouse_aggregate,
    fetch_events_for_custom,
    fetch_raw_event_properties,
)
from app.services.clickhouse_event_store import (
    _build_row,
    _extract_value,
    insert_event,
    insert_events_batch,
)
from app.services.events_query import fetch_event_properties
from app.services.usage_aggregation import UsageResult

ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# core/clickhouse.py
# ---------------------------------------------------------------------------
class TestParseClickhouseUrl:
    def test_full_url(self):
        params = _parse_clickhouse_url("clickhouse://user:pass@host:9000/mydb")
        assert params["host"] == "host"
        assert params["port"] == 9000
        assert params["username"] == "user"
        assert params["password"] == "pass"
        assert params["database"] == "mydb"

    def test_minimal_url(self):
        params = _parse_clickhouse_url("clickhouse://localhost")
        assert params["host"] == "localhost"
        assert params["port"] == 8123
        assert params["username"] == "default"
        assert params["password"] == ""
        assert params["database"] == "default"

    def test_empty_path(self):
        params = _parse_clickhouse_url("clickhouse://localhost/")
        assert params["database"] == "default"


class TestGetClickhouseClient:
    def setup_method(self):
        reset_client()

    def teardown_method(self):
        reset_client()

    def test_returns_none_when_disabled(self):
        with patch("app.core.clickhouse.settings") as mock_settings:
            mock_settings.clickhouse_enabled = False
            assert get_clickhouse_client() is None

    def test_creates_client_and_ensures_table(self):
        mock_client = MagicMock()
        with (
            patch("app.core.clickhouse.settings") as mock_settings,
            patch("app.core.clickhouse.clickhouse_connect") as mock_cc,
        ):
            mock_settings.clickhouse_enabled = True
            mock_settings.CLICKHOUSE_URL = "clickhouse://localhost/testdb"
            mock_cc.get_client.return_value = mock_client

            client = get_clickhouse_client()

            assert client is mock_client
            mock_client.command.assert_called_once_with(CREATE_EVENTS_RAW_TABLE)

    def test_returns_cached_client(self):
        mock_client = MagicMock()
        with (
            patch("app.core.clickhouse.settings") as mock_settings,
            patch("app.core.clickhouse.clickhouse_connect") as mock_cc,
        ):
            mock_settings.clickhouse_enabled = True
            mock_settings.CLICKHOUSE_URL = "clickhouse://localhost/testdb"
            mock_cc.get_client.return_value = mock_client

            client1 = get_clickhouse_client()
            client2 = get_clickhouse_client()

            assert client1 is client2
            # Only called once for table creation
            assert mock_client.command.call_count == 1

    def test_skips_table_creation_when_already_initialized(self):
        """When _initialized is True but _client is None, skips CREATE TABLE."""
        import app.core.clickhouse as ch_mod

        reset_client()
        ch_mod._initialized = True

        mock_client = MagicMock()
        with (
            patch("app.core.clickhouse.settings") as mock_settings,
            patch("app.core.clickhouse.clickhouse_connect") as mock_cc,
        ):
            mock_settings.clickhouse_enabled = True
            mock_settings.CLICKHOUSE_URL = "clickhouse://localhost/testdb"
            mock_cc.get_client.return_value = mock_client

            client = get_clickhouse_client()

            assert client is mock_client
            mock_client.command.assert_not_called()

        reset_client()


class TestResetClient:
    def test_reset_clears_state(self):
        reset_client()
        # Should not raise
        reset_client()


# ---------------------------------------------------------------------------
# services/clickhouse_event_store.py
# ---------------------------------------------------------------------------
class TestExtractValue:
    def test_no_field_name(self):
        assert _extract_value({"bytes": 100}, None) == (None, None)

    def test_field_present(self):
        value_str, decimal_val = _extract_value({"bytes": 100}, "bytes")
        assert value_str == "100"
        assert decimal_val == Decimal("100")

    def test_field_missing(self):
        assert _extract_value({"other": 1}, "bytes") == (None, None)

    def test_non_numeric_field(self):
        value_str, decimal_val = _extract_value({"status": "active"}, "status")
        assert value_str == "active"
        assert decimal_val is None


class TestBuildRow:
    def test_builds_correct_row(self):
        event = EventCreate(
            transaction_id="tx-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=NOW,
            properties={"bytes": 1024},
        )
        row = _build_row(event, ORG_ID, "bytes")
        assert row[0] == str(ORG_ID)
        assert row[1] == "tx-001"
        assert row[2] == "cust-001"
        assert row[3] == "api_calls"
        assert row[4] == NOW
        assert json.loads(row[5]) == {"bytes": 1024}
        assert row[6] == "1024"
        assert row[7] == Decimal("1024")

    def test_builds_row_without_field_name(self):
        event = EventCreate(
            transaction_id="tx-002",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=NOW,
        )
        row = _build_row(event, ORG_ID, None)
        assert row[6] is None
        assert row[7] is None


class TestInsertEvent:
    def test_noop_when_disabled(self):
        with patch("app.services.clickhouse_event_store.get_clickhouse_client", return_value=None):
            event = EventCreate(
                transaction_id="tx-001",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=NOW,
            )
            insert_event(event, ORG_ID)  # Should not raise

    def test_inserts_to_clickhouse(self):
        mock_client = MagicMock()
        with patch(
            "app.services.clickhouse_event_store.get_clickhouse_client", return_value=mock_client
        ):
            event = EventCreate(
                transaction_id="tx-001",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=NOW,
            )
            insert_event(event, ORG_ID, field_name="bytes")

            mock_client.insert.assert_called_once()
            args = mock_client.insert.call_args
            assert args[0][0] == "events_raw"  # table name
            assert len(args[0][1]) == 1  # 1 row
            assert len(args[0][1][0]) == 8  # 8 columns

    def test_logs_on_failure(self):
        mock_client = MagicMock()
        mock_client.insert.side_effect = Exception("Connection failed")
        with patch(
            "app.services.clickhouse_event_store.get_clickhouse_client", return_value=mock_client
        ):
            event = EventCreate(
                transaction_id="tx-fail",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=NOW,
            )
            insert_event(event, ORG_ID)  # Should not raise


class TestInsertEventsBatch:
    def test_noop_when_disabled(self):
        with patch("app.services.clickhouse_event_store.get_clickhouse_client", return_value=None):
            insert_events_batch([], ORG_ID)

    def test_inserts_batch(self):
        mock_client = MagicMock()
        with patch(
            "app.services.clickhouse_event_store.get_clickhouse_client", return_value=mock_client
        ):
            events = [
                EventCreate(
                    transaction_id=f"tx-{i}",
                    external_customer_id="cust-001",
                    code="api_calls",
                    timestamp=NOW,
                )
                for i in range(3)
            ]
            insert_events_batch(events, ORG_ID, field_names={"api_calls": None})

            mock_client.insert.assert_called_once()
            args = mock_client.insert.call_args
            assert len(args[0][1]) == 3

    def test_logs_on_failure(self):
        mock_client = MagicMock()
        mock_client.insert.side_effect = Exception("Batch insert failed")
        with patch(
            "app.services.clickhouse_event_store.get_clickhouse_client", return_value=mock_client
        ):
            events = [
                EventCreate(
                    transaction_id="tx-fail", external_customer_id="c", code="x", timestamp=NOW
                )
            ]
            insert_events_batch(events, ORG_ID)


# ---------------------------------------------------------------------------
# services/clickhouse_aggregation.py
# ---------------------------------------------------------------------------
class TestBuildFilterClause:
    def test_no_filters(self):
        assert _build_filter_clause(None) == ""
        assert _build_filter_clause({}) == ""

    def test_with_filters(self):
        clause = _build_filter_clause({"region": "us"})
        assert "JSONExtractString" in clause
        assert "fk0" in clause


class TestBuildFilterParams:
    def test_no_filters(self):
        assert _build_filter_params(None) == {}

    def test_with_filters(self):
        params = _build_filter_params({"region": "us", "tier": "premium"})
        assert params == {"fk0": "region", "fv0": "us", "fk1": "tier", "fv1": "premium"}


def _mock_query_result(rows):
    """Create a mock QueryResult."""
    result = MagicMock()
    result.first_row = rows[0] if rows else []
    result.result_rows = rows
    return result


class TestAggregateCount:
    def test_count(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result([(5,)])
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_count(ORG_ID, "api_calls", "cust-001", NOW, NOW + timedelta(days=1))
            assert result == UsageResult(value=Decimal(5), events_count=5)


class TestAggregateSum:
    def test_sum(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result([(Decimal("150.5"), 3)])
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_sum(
                ORG_ID, "data_transfer", "cust-001", NOW, NOW + timedelta(days=1)
            )
            assert result.value == Decimal("150.5")
            assert result.events_count == 3


class TestAggregateMax:
    def test_max(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result([(Decimal("99.9"), 3)])
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_max(ORG_ID, "cpu_usage", "cust-001", NOW, NOW + timedelta(days=1))
            assert result.value == Decimal("99.9")
            assert result.events_count == 3


class TestAggregateUniqueCount:
    def test_unique_count(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result([(7, 20)])
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_unique_count(
                ORG_ID, "users", "cust-001", NOW, NOW + timedelta(days=1), "user_id"
            )
            assert result.value == Decimal(7)
            assert result.events_count == 20


class TestAggregateLatest:
    def test_latest_with_events(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result([(Decimal("42.0"), 5)])
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_latest(
                ORG_ID, "temperature", "cust-001", NOW, NOW + timedelta(days=1)
            )
            assert result.value == Decimal("42.0")
            assert result.events_count == 5

    def test_latest_no_events(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result([(None, 0)])
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_latest(
                ORG_ID, "temperature", "cust-001", NOW, NOW + timedelta(days=1)
            )
            assert result.value == Decimal(0)
            assert result.events_count == 0


class TestAggregateWeightedSum:
    def test_zero_duration(self):
        mock_client = MagicMock()
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_weighted_sum(ORG_ID, "usage", "cust-001", NOW, NOW)
            assert result == UsageResult(value=Decimal(0), events_count=0)
            mock_client.query.assert_not_called()

    def test_no_events(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result([(0,)])
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_weighted_sum(
                ORG_ID, "usage", "cust-001", NOW, NOW + timedelta(hours=1)
            )
            assert result == UsageResult(value=Decimal(0), events_count=0)

    def test_with_events(self):
        mock_client = MagicMock()
        # First query: count = 2, Second query: weighted sum
        mock_client.query.side_effect = [
            _mock_query_result([(2,)]),
            _mock_query_result([(Decimal("1.5"),)]),
        ]
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_weighted_sum(
                ORG_ID, "usage", "cust-001", NOW, NOW + timedelta(hours=1)
            )
            assert result.value == Decimal("1.5")
            assert result.events_count == 2

    def test_with_events_none_result(self):
        mock_client = MagicMock()
        mock_client.query.side_effect = [
            _mock_query_result([(1,)]),
            _mock_query_result([(None,)]),
        ]
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_weighted_sum(
                ORG_ID, "usage", "cust-001", NOW, NOW + timedelta(hours=1)
            )
            assert result.value == Decimal(0)


class TestFetchEventsForCustom:
    def test_fetches_and_parses(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result(
            [
                ('{"a": 1, "b": 2}',),
                ('{"a": 3, "b": 4}',),
            ]
        )
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = fetch_events_for_custom(ORG_ID, "metric", "cust", NOW, NOW + timedelta(days=1))
            assert result == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


class TestAggregateCustom:
    def test_empty_events(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result([])
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_custom(
                ORG_ID, "metric", "cust", NOW, NOW + timedelta(days=1), "a + b"
            )
            assert result == UsageResult(value=Decimal(0), events_count=0)

    def test_with_expression(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result(
            [
                ('{"x": 10, "y": 5}',),
                ('{"x": 20, "y": 3}',),
            ]
        )
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = aggregate_custom(
                ORG_ID, "metric", "cust", NOW, NOW + timedelta(days=1), "x + y"
            )
            assert result.value == Decimal(38)  # (10+5) + (20+3)
            assert result.events_count == 2


class TestFetchRawEventProperties:
    def test_delegates_to_fetch_events_for_custom(self):
        mock_client = MagicMock()
        mock_client.query.return_value = _mock_query_result([('{"k": "v"}',)])
        with patch(
            "app.services.clickhouse_aggregation.get_clickhouse_client", return_value=mock_client
        ):
            result = fetch_raw_event_properties(
                ORG_ID, "code", "cust", NOW, NOW + timedelta(days=1)
            )
            assert result == [{"k": "v"}]


class TestClickhouseAggregate:
    def test_dispatches_count(self):
        with patch("app.services.clickhouse_aggregation.aggregate_count") as mock_fn:
            mock_fn.return_value = UsageResult(value=Decimal(5), events_count=5)
            result = clickhouse_aggregate(
                ORG_ID, "c", "cust", NOW, NOW + timedelta(days=1), AggregationType.COUNT
            )
            assert result.value == Decimal(5)

    def test_dispatches_sum(self):
        with patch("app.services.clickhouse_aggregation.aggregate_sum") as mock_fn:
            mock_fn.return_value = UsageResult(value=Decimal(100), events_count=3)
            result = clickhouse_aggregate(
                ORG_ID, "c", "cust", NOW, NOW + timedelta(days=1), AggregationType.SUM
            )
            assert result.value == Decimal(100)

    def test_dispatches_max(self):
        with patch("app.services.clickhouse_aggregation.aggregate_max") as mock_fn:
            mock_fn.return_value = UsageResult(value=Decimal(50), events_count=2)
            result = clickhouse_aggregate(
                ORG_ID, "c", "cust", NOW, NOW + timedelta(days=1), AggregationType.MAX
            )
            assert result.value == Decimal(50)

    def test_dispatches_unique_count(self):
        with patch("app.services.clickhouse_aggregation.aggregate_unique_count") as mock_fn:
            mock_fn.return_value = UsageResult(value=Decimal(7), events_count=20)
            result = clickhouse_aggregate(
                ORG_ID,
                "c",
                "cust",
                NOW,
                NOW + timedelta(days=1),
                AggregationType.UNIQUE_COUNT,
                field_name="user_id",
            )
            assert result.value == Decimal(7)

    def test_dispatches_latest(self):
        with patch("app.services.clickhouse_aggregation.aggregate_latest") as mock_fn:
            mock_fn.return_value = UsageResult(value=Decimal(42), events_count=5)
            result = clickhouse_aggregate(
                ORG_ID, "c", "cust", NOW, NOW + timedelta(days=1), AggregationType.LATEST
            )
            assert result.value == Decimal(42)

    def test_dispatches_weighted_sum(self):
        with patch("app.services.clickhouse_aggregation.aggregate_weighted_sum") as mock_fn:
            mock_fn.return_value = UsageResult(value=Decimal("1.5"), events_count=2)
            result = clickhouse_aggregate(
                ORG_ID, "c", "cust", NOW, NOW + timedelta(days=1), AggregationType.WEIGHTED_SUM
            )
            assert result.value == Decimal("1.5")

    def test_dispatches_custom(self):
        with patch("app.services.clickhouse_aggregation.aggregate_custom") as mock_fn:
            mock_fn.return_value = UsageResult(value=Decimal(38), events_count=2)
            result = clickhouse_aggregate(
                ORG_ID,
                "c",
                "cust",
                NOW,
                NOW + timedelta(days=1),
                AggregationType.CUSTOM,
                expression="x + y",
            )
            assert result.value == Decimal(38)

    def test_raises_for_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown aggregation type"):
            clickhouse_aggregate(ORG_ID, "c", "cust", NOW, NOW + timedelta(days=1), "invalid_type")


# ---------------------------------------------------------------------------
# services/events_query.py
# ---------------------------------------------------------------------------
class TestFetchEventProperties:
    def test_sql_path_when_disabled(self, db_session):
        """Uses SQL Event model when ClickHouse is not configured."""
        from app.models.event import Event

        event = Event(
            transaction_id="eq-tx-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=NOW,
            properties={"endpoint": "/api/users"},
        )
        db_session.add(event)
        db_session.commit()

        with patch("app.services.events_query.settings") as mock_settings:
            mock_settings.clickhouse_enabled = False
            result = fetch_event_properties(
                db_session,
                "cust-001",
                "api_calls",
                NOW - timedelta(hours=1),
                NOW + timedelta(hours=1),
            )

        assert len(result) == 1
        assert result[0]["endpoint"] == "/api/users"

    def test_sql_path_with_filters(self, db_session):
        """Applies property filters in SQL path."""
        from app.models.event import Event

        e1 = Event(
            transaction_id="eq-f-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=NOW,
            properties={"region": "us"},
        )
        e2 = Event(
            transaction_id="eq-f-002",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=NOW,
            properties={"region": "eu"},
        )
        db_session.add_all([e1, e2])
        db_session.commit()

        with patch("app.services.events_query.settings") as mock_settings:
            mock_settings.clickhouse_enabled = False
            result = fetch_event_properties(
                db_session,
                "cust-001",
                "api_calls",
                NOW - timedelta(hours=1),
                NOW + timedelta(hours=1),
                filters={"region": "us"},
            )

        assert len(result) == 1
        assert result[0]["region"] == "us"

    def test_clickhouse_path_when_enabled(self, db_session):
        """Delegates to ClickHouse when enabled."""
        from app.core.config import settings as _settings

        with (
            patch.object(
                type(_settings),
                "clickhouse_enabled",
                new_callable=lambda: property(lambda self: True),
            ),
            patch(
                "app.services.clickhouse_aggregation.fetch_raw_event_properties",
            ) as mock_ch,
        ):
            mock_ch.return_value = [{"key": "val"}]

            result = fetch_event_properties(
                db_session,
                "cust-001",
                "api_calls",
                NOW - timedelta(hours=1),
                NOW + timedelta(hours=1),
                organization_id=ORG_ID,
            )

        assert result == [{"key": "val"}]
        mock_ch.assert_called_once()

    def test_clickhouse_path_with_filters(self, db_session):
        """Applies property filters to ClickHouse results."""
        from app.core.config import settings as _settings

        with (
            patch.object(
                type(_settings),
                "clickhouse_enabled",
                new_callable=lambda: property(lambda self: True),
            ),
            patch(
                "app.services.clickhouse_aggregation.fetch_raw_event_properties",
            ) as mock_ch,
        ):
            mock_ch.return_value = [
                {"region": "us", "val": 1},
                {"region": "eu", "val": 2},
            ]

            result = fetch_event_properties(
                db_session,
                "cust-001",
                "api_calls",
                NOW - timedelta(hours=1),
                NOW + timedelta(hours=1),
                organization_id=ORG_ID,
                filters={"region": "us"},
            )

        assert len(result) == 1
        assert result[0]["region"] == "us"

    def test_sql_fallback_when_no_org_id(self, db_session):
        """Falls back to SQL when organization_id is None even if CH enabled."""
        from app.core.config import settings as _settings
        from app.models.event import Event

        event = Event(
            transaction_id="eq-no-org",
            external_customer_id="c",
            code="x",
            timestamp=NOW,
            properties={"a": 1},
        )
        db_session.add(event)
        db_session.commit()

        with patch.object(
            type(_settings),
            "clickhouse_enabled",
            new_callable=lambda: property(lambda self: True),
        ):
            result = fetch_event_properties(
                db_session,
                "c",
                "x",
                NOW - timedelta(hours=1),
                NOW + timedelta(hours=1),
                organization_id=None,
            )

        assert len(result) == 1


# ---------------------------------------------------------------------------
# UsageAggregationService delegation
# ---------------------------------------------------------------------------
class TestUsageAggregationClickhouseDelegation:
    def test_delegates_when_enabled(self, db_session):
        """When ClickHouse is enabled, aggregation delegates to ClickHouse."""
        from app.repositories.billable_metric_repository import BillableMetricRepository
        from app.schemas.billable_metric import BillableMetricCreate
        from app.services.usage_aggregation import UsageAggregationService

        metric_repo = BillableMetricRepository(db_session)
        metric_repo.create(
            BillableMetricCreate(
                code="ch_test",
                name="CH Test",
                aggregation_type=AggregationType.COUNT,
            ),
            ORG_ID,
        )

        service = UsageAggregationService(db_session)

        with (
            patch("app.core.config.settings") as mock_settings,
            patch(
                "app.services.clickhouse_aggregation.clickhouse_aggregate",
            ) as mock_ch,
        ):
            mock_settings.clickhouse_enabled = True
            mock_ch.return_value = UsageResult(
                value=Decimal(10),
                events_count=10,
            )

            result = service.aggregate_usage_with_count(
                external_customer_id="cust-001",
                code="ch_test",
                from_timestamp=NOW,
                to_timestamp=NOW + timedelta(days=1),
                organization_id=ORG_ID,
            )

        assert result.value == Decimal(10)
        mock_ch.assert_called_once()

    def test_does_not_delegate_when_disabled(self, db_session):
        """When ClickHouse is disabled, uses SQL aggregation."""
        from app.repositories.billable_metric_repository import BillableMetricRepository
        from app.schemas.billable_metric import BillableMetricCreate
        from app.services.usage_aggregation import UsageAggregationService

        metric_repo = BillableMetricRepository(db_session)
        metric_repo.create(
            BillableMetricCreate(
                code="sql_test",
                name="SQL Test",
                aggregation_type=AggregationType.COUNT,
            ),
            ORG_ID,
        )

        service = UsageAggregationService(db_session)

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.clickhouse_enabled = False

            result = service.aggregate_usage_with_count(
                external_customer_id="cust-001",
                code="sql_test",
                from_timestamp=NOW,
                to_timestamp=NOW + timedelta(days=1),
                organization_id=ORG_ID,
            )

        assert result.value == Decimal(0)  # No events in SQL


# ---------------------------------------------------------------------------
# EventRepository dual-write
# ---------------------------------------------------------------------------
class TestEventRepositoryDualWrite:
    def test_create_calls_clickhouse_insert(self, db_session, billable_metric):
        """create() calls ClickHouse insert when enabled."""
        from app.repositories.event_repository import EventRepository

        repo = EventRepository(db_session)
        event_data = EventCreate(
            transaction_id="dw-tx-001",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=NOW,
        )

        with patch.object(repo, "_clickhouse_insert") as mock_ch:
            repo.create(event_data, ORG_ID)
            mock_ch.assert_called_once_with(event_data, ORG_ID)

    def test_create_batch_calls_clickhouse_insert(self, db_session, billable_metric):
        """create_batch() calls ClickHouse batch insert for new events."""
        from app.repositories.event_repository import EventRepository

        repo = EventRepository(db_session)
        events_data = [
            EventCreate(
                transaction_id=f"dw-batch-{i}",
                external_customer_id="cust-001",
                code="api_calls",
                timestamp=NOW,
            )
            for i in range(3)
        ]

        with patch.object(repo, "_clickhouse_insert_batch") as mock_ch:
            events, ingested, duplicates = repo.create_batch(events_data, ORG_ID)
            assert ingested == 3
            mock_ch.assert_called_once()

    def test_clickhouse_insert_noop_when_disabled(self, db_session, billable_metric):
        """_clickhouse_insert does nothing when ClickHouse is disabled."""
        from app.repositories.event_repository import EventRepository

        repo = EventRepository(db_session)
        event_data = EventCreate(
            transaction_id="dw-noop",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=NOW,
        )

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.clickhouse_enabled = False
            repo._clickhouse_insert(event_data, ORG_ID)  # Should not raise

    def test_clickhouse_insert_calls_store(self, db_session, billable_metric):
        """_clickhouse_insert calls insert_event when enabled."""
        from app.repositories.event_repository import EventRepository

        repo = EventRepository(db_session)
        event_data = EventCreate(
            transaction_id="dw-store",
            external_customer_id="cust-001",
            code="api_calls",
            timestamp=NOW,
        )

        with (
            patch("app.core.config.settings") as mock_settings,
            patch(
                "app.services.clickhouse_event_store.insert_event",
            ) as mock_insert,
        ):
            mock_settings.clickhouse_enabled = True
            repo._clickhouse_insert(event_data, ORG_ID)
            mock_insert.assert_called_once()

    def test_clickhouse_insert_batch_noop_when_disabled(self, db_session):
        """_clickhouse_insert_batch does nothing when disabled."""
        from app.repositories.event_repository import EventRepository

        repo = EventRepository(db_session)

        with patch("app.core.config.settings") as mock_settings:
            mock_settings.clickhouse_enabled = False
            repo._clickhouse_insert_batch([], ORG_ID)

    def test_clickhouse_insert_batch_calls_store(self, db_session, billable_metric):
        """_clickhouse_insert_batch calls insert_events_batch when enabled."""
        from app.repositories.event_repository import EventRepository

        repo = EventRepository(db_session)
        events_data = [
            EventCreate(
                transaction_id="dw-bs",
                external_customer_id="c",
                code="api_calls",
                timestamp=NOW,
            )
        ]

        with (
            patch("app.core.config.settings") as mock_settings,
            patch(
                "app.services.clickhouse_event_store.insert_events_batch",
            ) as mock_insert,
        ):
            mock_settings.clickhouse_enabled = True
            repo._clickhouse_insert_batch(events_data, ORG_ID)
            mock_insert.assert_called_once()

    def test_resolve_field_name(self, db_session, billable_metric_sum):
        """_resolve_field_name returns the metric's field_name."""
        from app.repositories.event_repository import EventRepository

        repo = EventRepository(db_session)
        assert repo._resolve_field_name("data_transfer", ORG_ID) == "bytes"

    def test_resolve_field_name_none_for_count(self, db_session, billable_metric):
        """_resolve_field_name returns None for COUNT metric (no field_name)."""
        from app.repositories.event_repository import EventRepository

        repo = EventRepository(db_session)
        assert repo._resolve_field_name("api_calls", ORG_ID) is None

    def test_resolve_field_name_nonexistent(self, db_session):
        """_resolve_field_name returns None for non-existent metric."""
        from app.repositories.event_repository import EventRepository

        repo = EventRepository(db_session)
        assert repo._resolve_field_name("nonexistent", ORG_ID) is None

    def test_resolve_field_names(self, db_session, billable_metric, billable_metric_sum):
        """_resolve_field_names returns mapping for all codes."""
        from app.repositories.event_repository import EventRepository

        repo = EventRepository(db_session)
        events = [
            EventCreate(
                transaction_id="rfn-1", external_customer_id="c", code="api_calls", timestamp=NOW
            ),
            EventCreate(
                transaction_id="rfn-2",
                external_customer_id="c",
                code="data_transfer",
                timestamp=NOW,
            ),
        ]
        result = repo._resolve_field_names(events, ORG_ID)
        assert result == {"api_calls": None, "data_transfer": "bytes"}


# ---------------------------------------------------------------------------
# Config property
# ---------------------------------------------------------------------------
class TestSettingsClickhouseEnabled:
    def test_enabled_when_url_set(self):
        s = Settings(CLICKHOUSE_URL="clickhouse://localhost/db")
        assert s.clickhouse_enabled is True

    def test_disabled_when_url_empty(self):
        s = Settings(CLICKHOUSE_URL="")
        assert s.clickhouse_enabled is False

    def test_disabled_by_default(self):
        s = Settings()
        assert s.clickhouse_enabled is False


# ---------------------------------------------------------------------------
# Fixtures (shared with test_events.py)
# ---------------------------------------------------------------------------
@pytest.fixture
def db_session():
    """Create a database session for direct repository testing."""
    from app.core.database import get_db

    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def billable_metric(db_session):
    """Create a COUNT billable metric for testing."""
    from app.repositories.billable_metric_repository import BillableMetricRepository
    from app.schemas.billable_metric import BillableMetricCreate

    repo = BillableMetricRepository(db_session)
    data = BillableMetricCreate(
        code="api_calls", name="API Calls", aggregation_type=AggregationType.COUNT
    )
    return repo.create(data, ORG_ID)


@pytest.fixture
def billable_metric_sum(db_session):
    """Create a SUM billable metric for testing."""
    from app.repositories.billable_metric_repository import BillableMetricRepository
    from app.schemas.billable_metric import BillableMetricCreate

    repo = BillableMetricRepository(db_session)
    data = BillableMetricCreate(
        code="data_transfer",
        name="Data Transfer",
        aggregation_type=AggregationType.SUM,
        field_name="bytes",
    )
    return repo.create(data, ORG_ID)
