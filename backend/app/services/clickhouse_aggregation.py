"""ClickHouse-based aggregation service (adapted from Lago's ClickhouseStore).

Provides the same aggregation types as UsageAggregationService but runs
queries against ClickHouse for high-volume event workloads.
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.clickhouse import EVENTS_RAW_TABLE, get_clickhouse_client
from app.models.billable_metric import AggregationType
from app.services.usage_aggregation import UsageResult, _evaluate_expression, _is_numeric

logger = logging.getLogger(__name__)

# Base WHERE clause shared by all aggregation queries
_BASE_WHERE = (
    "organization_id = {org_id:String}"
    " AND code = {code:String}"
    " AND external_customer_id = {cust_id:String}"
    " AND timestamp >= {from_ts:DateTime64(3)}"
    " AND timestamp < {to_ts:DateTime64(3)}"
)


def _build_filter_clause(filters: dict[str, str] | None) -> str:
    """Build additional WHERE clause for property-based filters."""
    if not filters:
        return ""
    clauses = []
    for i, (_key, _value) in enumerate(filters.items()):
        clauses.append(
            f" AND JSONExtractString(properties, {{fk{i}:String}}) = {{fv{i}:String}}"
        )
    return "".join(clauses)


def _build_filter_params(filters: dict[str, str] | None) -> dict[str, str]:
    """Build query parameters for property-based filters."""
    if not filters:
        return {}
    params: dict[str, str] = {}
    for i, (key, value) in enumerate(filters.items()):
        params[f"fk{i}"] = key
        params[f"fv{i}"] = value
    return params


def _base_params(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
) -> dict[str, object]:
    return {
        "org_id": str(organization_id),
        "code": code,
        "cust_id": external_customer_id,
        "from_ts": from_timestamp,
        "to_ts": to_timestamp,
    }


def _query_params(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    filters: dict[str, str] | None = None,
) -> dict[str, object]:
    """Build combined base + filter query parameters."""
    return {
        **_base_params(
            organization_id, code, external_customer_id,
            from_timestamp, to_timestamp,
        ),
        **_build_filter_params(filters),
    }


def aggregate_count(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    filters: dict[str, str] | None = None,
) -> UsageResult:
    """COUNT aggregation via ClickHouse."""
    client = get_clickhouse_client()
    assert client is not None

    filter_clause = _build_filter_clause(filters)
    sql = f"SELECT count() FROM {EVENTS_RAW_TABLE} WHERE {_BASE_WHERE}{filter_clause}"
    params = _query_params(
        organization_id, code, external_customer_id,
        from_timestamp, to_timestamp, filters,
    )

    result = client.query(sql, parameters=params)
    count = int(result.first_row[0])
    return UsageResult(value=Decimal(count), events_count=count)


def aggregate_sum(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    filters: dict[str, str] | None = None,
) -> UsageResult:
    """SUM aggregation via ClickHouse."""
    client = get_clickhouse_client()
    assert client is not None

    filter_clause = _build_filter_clause(filters)
    sql = (
        f"SELECT coalesce(sum(decimal_value), 0), count()"
        f" FROM {EVENTS_RAW_TABLE} WHERE {_BASE_WHERE}{filter_clause}"
    )
    params = _query_params(
        organization_id, code, external_customer_id,
        from_timestamp, to_timestamp, filters,
    )

    result = client.query(sql, parameters=params)
    row = result.first_row
    return UsageResult(value=Decimal(str(row[0])), events_count=int(row[1]))


def aggregate_max(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    filters: dict[str, str] | None = None,
) -> UsageResult:
    """MAX aggregation via ClickHouse."""
    client = get_clickhouse_client()
    assert client is not None

    filter_clause = _build_filter_clause(filters)
    sql = (
        f"SELECT coalesce(max(decimal_value), 0), count()"
        f" FROM {EVENTS_RAW_TABLE} WHERE {_BASE_WHERE}{filter_clause}"
    )
    params = _query_params(
        organization_id, code, external_customer_id,
        from_timestamp, to_timestamp, filters,
    )

    result = client.query(sql, parameters=params)
    row = result.first_row
    return UsageResult(value=Decimal(str(row[0])), events_count=int(row[1]))


def aggregate_unique_count(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    field_name: str,
    filters: dict[str, str] | None = None,
) -> UsageResult:
    """UNIQUE_COUNT aggregation via ClickHouse using uniq()."""
    client = get_clickhouse_client()
    assert client is not None

    filter_clause = _build_filter_clause(filters)
    sql = (
        "SELECT uniq(JSONExtractString(properties, {field:String})), count()"
        f" FROM {EVENTS_RAW_TABLE} WHERE {_BASE_WHERE}{filter_clause}"
        " AND JSONHas(properties, {field:String})"
    )
    params = {
        **_query_params(
            organization_id, code, external_customer_id,
            from_timestamp, to_timestamp, filters,
        ),
        "field": field_name,
    }

    result = client.query(sql, parameters=params)
    row = result.first_row
    return UsageResult(value=Decimal(int(row[0])), events_count=int(row[1]))


def aggregate_latest(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    filters: dict[str, str] | None = None,
) -> UsageResult:
    """LATEST aggregation — returns the most recent event's decimal_value."""
    client = get_clickhouse_client()
    assert client is not None

    filter_clause = _build_filter_clause(filters)
    # Get latest value and total count in one round-trip
    sql = (
        "SELECT"
        f" (SELECT coalesce(decimal_value, 0) FROM {EVENTS_RAW_TABLE}"
        f"  WHERE {_BASE_WHERE}{filter_clause}"
        "  ORDER BY timestamp DESC LIMIT 1) AS latest_val,"
        f" (SELECT count() FROM {EVENTS_RAW_TABLE}"
        f"  WHERE {_BASE_WHERE}{filter_clause}) AS cnt"
    )
    params = _query_params(
        organization_id, code, external_customer_id,
        from_timestamp, to_timestamp, filters,
    )

    result = client.query(sql, parameters=params)
    row = result.first_row
    value = Decimal(str(row[0])) if row[0] is not None else Decimal(0)
    count = int(row[1])
    if count == 0:
        return UsageResult(value=Decimal(0), events_count=0)
    return UsageResult(value=value, events_count=count)


def aggregate_weighted_sum(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    filters: dict[str, str] | None = None,
) -> UsageResult:
    """WEIGHTED_SUM aggregation via ClickHouse window functions.

    Adapted from Lago's WeightedSumQuery: computes a time-weighted sum
    where each event's value is weighted by the fraction of the period
    it applies to (until the next event or period end).
    """
    client = get_clickhouse_client()
    assert client is not None

    total_seconds = (to_timestamp - from_timestamp).total_seconds()
    if total_seconds == 0:
        return UsageResult(value=Decimal(0), events_count=0)

    filter_clause = _build_filter_clause(filters)

    # Count events first
    count_sql = (
        f"SELECT count() FROM {EVENTS_RAW_TABLE}"
        f" WHERE {_BASE_WHERE}{filter_clause}"
    )
    params: dict[str, object] = _query_params(
        organization_id, code, external_customer_id,
        from_timestamp, to_timestamp, filters,
    )
    count_result = client.query(count_sql, parameters=params)
    events_count = int(count_result.first_row[0])

    if events_count == 0:
        return UsageResult(value=Decimal(0), events_count=0)

    # Weighted sum using window functions
    sql = f"""
    SELECT sum(period_ratio) AS aggregation FROM (
        SELECT
            coalesce(decimal_value, 0)
            * dateDiff('second', timestamp,
                leadInFrame(timestamp, 1, {{to_ts:DateTime64(3)}})
                OVER (ORDER BY timestamp ASC
                      ROWS BETWEEN CURRENT ROW AND 1 FOLLOWING))
            / {{total_seconds:Float64}}
            AS period_ratio
        FROM {EVENTS_RAW_TABLE}
        WHERE {_BASE_WHERE}{filter_clause}
        ORDER BY timestamp ASC
    )
    """
    params["total_seconds"] = total_seconds

    result = client.query(sql, parameters=params)
    value = (
        Decimal(str(result.first_row[0]))
        if result.first_row[0] is not None
        else Decimal(0)
    )
    return UsageResult(value=value, events_count=events_count)


def fetch_events_for_custom(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch raw event properties from ClickHouse for CUSTOM aggregation."""
    client = get_clickhouse_client()
    assert client is not None

    filter_clause = _build_filter_clause(filters)
    sql = (
        f"SELECT properties FROM {EVENTS_RAW_TABLE}"
        f" WHERE {_BASE_WHERE}{filter_clause}"
        " ORDER BY timestamp ASC"
    )
    params = _query_params(
        organization_id, code, external_customer_id,
        from_timestamp, to_timestamp, filters,
    )

    result = client.query(sql, parameters=params)
    return [json.loads(str(row[0])) for row in result.result_rows]


def aggregate_custom(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    expression: str,
    filters: dict[str, str] | None = None,
) -> UsageResult:
    """CUSTOM aggregation — fetch events from ClickHouse, evaluate in Python."""
    events_props = fetch_events_for_custom(
        organization_id, code, external_customer_id,
        from_timestamp, to_timestamp, filters,
    )
    events_count = len(events_props)
    if events_count == 0:
        return UsageResult(value=Decimal(0), events_count=0)

    total = Decimal(0)
    for props in events_props:
        variables = {
            k: Decimal(str(v))
            for k, v in props.items()
            if isinstance(v, (int, float, str)) and _is_numeric(v)
        }
        total += _evaluate_expression(expression, variables)
    return UsageResult(value=total, events_count=events_count)


def fetch_raw_event_properties(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch raw event properties from ClickHouse for DYNAMIC charges."""
    return fetch_events_for_custom(
        organization_id, code, external_customer_id,
        from_timestamp, to_timestamp, filters,
    )


def clickhouse_aggregate(
    organization_id: UUID,
    code: str,
    external_customer_id: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    aggregation_type: AggregationType,
    field_name: str | None = None,
    expression: str | None = None,
    filters: dict[str, str] | None = None,
) -> UsageResult:
    """Dispatch to the correct ClickHouse aggregation function.

    This is the main entry point, mirroring
    UsageAggregationService._compute_aggregation.
    """
    if aggregation_type == AggregationType.COUNT:
        return aggregate_count(
            organization_id, code, external_customer_id,
            from_timestamp, to_timestamp, filters,
        )
    elif aggregation_type == AggregationType.SUM:
        return aggregate_sum(
            organization_id, code, external_customer_id,
            from_timestamp, to_timestamp, filters,
        )
    elif aggregation_type == AggregationType.MAX:
        return aggregate_max(
            organization_id, code, external_customer_id,
            from_timestamp, to_timestamp, filters,
        )
    elif aggregation_type == AggregationType.UNIQUE_COUNT:
        assert field_name is not None
        return aggregate_unique_count(
            organization_id, code, external_customer_id,
            from_timestamp, to_timestamp, field_name, filters,
        )
    elif aggregation_type == AggregationType.LATEST:
        return aggregate_latest(
            organization_id, code, external_customer_id,
            from_timestamp, to_timestamp, filters,
        )
    elif aggregation_type == AggregationType.WEIGHTED_SUM:
        return aggregate_weighted_sum(
            organization_id, code, external_customer_id,
            from_timestamp, to_timestamp, filters,
        )
    elif aggregation_type == AggregationType.CUSTOM:
        assert expression is not None
        return aggregate_custom(
            organization_id, code, external_customer_id,
            from_timestamp, to_timestamp, expression, filters,
        )
    else:
        raise ValueError(f"Unknown aggregation type: {aggregation_type}")
