import re
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.billable_metric import AggregationType, BillableMetric
from app.models.customer import DEFAULT_ORGANIZATION_ID
from app.models.event import Event
from app.repositories.billable_metric_repository import BillableMetricRepository

# Pattern to tokenize simple math expressions like "field1 + field2 * 2"
_TOKEN_RE = re.compile(r"(\d+(?:\.\d+)?|[a-zA-Z_]\w*|[+\-*/()])")


def _evaluate_expression(expression: str, variables: dict[str, Decimal]) -> Decimal:
    """Safely evaluate a simple arithmetic expression with variables.

    Supports: +, -, *, / operators and parentheses.
    Variables are resolved from the provided dict.
    No eval() or exec() — uses a simple recursive descent parser.
    """
    tokens = _TOKEN_RE.findall(expression)
    pos = [0]

    def _peek() -> str | None:
        if pos[0] < len(tokens):
            return str(tokens[pos[0]])
        return None

    def _consume() -> str:
        token = str(tokens[pos[0]])
        pos[0] += 1
        return token

    def _parse_primary() -> Decimal:
        token = _peek()
        if token is None:
            raise ValueError("Unexpected end of expression")
        if token == "(":
            _consume()  # consume '('
            result = _parse_additive()
            if _peek() != ")":
                raise ValueError("Expected ')'")
            _consume()  # consume ')'
            return result
        _consume()
        # Number literal
        try:
            return Decimal(token)
        except Exception:
            pass
        # Variable reference
        if token in variables:
            return variables[token]
        raise ValueError(f"Unknown variable: {token}")

    def _parse_multiplicative() -> Decimal:
        left = _parse_primary()
        while _peek() in ("*", "/"):
            op = _consume()
            right = _parse_primary()
            if op == "*":
                left = left * right
            else:
                if right == 0:
                    raise ValueError("Division by zero")
                left = left / right
        return left

    def _parse_additive() -> Decimal:
        left = _parse_multiplicative()
        while _peek() in ("+", "-"):
            op = _consume()
            right = _parse_multiplicative()
            left = left + right if op == "+" else left - right
        return left

    if not tokens:
        raise ValueError("Empty expression")

    result = _parse_additive()
    if pos[0] != len(tokens):
        raise ValueError("Unexpected tokens in expression")
    return result


def _apply_rounding(
    value: Decimal,
    rounding_function: str | None,
    rounding_precision: int | None,
) -> Decimal:
    """Apply rounding to an aggregated value."""
    if rounding_function is None:
        return value

    precision = rounding_precision if rounding_precision is not None else 0
    quantize_exp = Decimal(10) ** -precision

    if rounding_function == "round":
        return value.quantize(quantize_exp, rounding=ROUND_HALF_UP)
    elif rounding_function == "ceil":
        return value.quantize(quantize_exp, rounding=ROUND_CEILING)
    elif rounding_function == "floor":
        return value.quantize(quantize_exp, rounding=ROUND_FLOOR)
    else:
        raise ValueError(f"Unknown rounding function: {rounding_function}")


@dataclass
class UsageResult:
    """Result of a usage aggregation containing value and event count."""

    value: Decimal
    events_count: int


class UsageAggregationService:
    """Service for aggregating events into usage data by billing period."""

    def __init__(self, db: Session):
        self.db = db
        self.metric_repo = BillableMetricRepository(db)

    def aggregate_usage(
        self,
        external_customer_id: str,
        code: str,
        from_timestamp: datetime,
        to_timestamp: datetime,
        filters: dict[str, str] | None = None,
        organization_id: UUID = DEFAULT_ORGANIZATION_ID,
    ) -> Decimal:
        """Aggregate usage for a customer and metric code within a time period.

        Args:
            external_customer_id: Customer to aggregate for
            code: Billable metric code
            from_timestamp: Start of period
            to_timestamp: End of period
            filters: Optional dict of property key-value pairs to filter events
            organization_id: Organization to scope the metric lookup to.

        Returns:
            Aggregated usage value based on the metric's aggregation type.
        """
        result = self.aggregate_usage_with_count(
            external_customer_id=external_customer_id,
            code=code,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            filters=filters,
            organization_id=organization_id,
        )
        return result.value

    def aggregate_usage_with_count(
        self,
        external_customer_id: str,
        code: str,
        from_timestamp: datetime,
        to_timestamp: datetime,
        filters: dict[str, str] | None = None,
        organization_id: UUID = DEFAULT_ORGANIZATION_ID,
    ) -> UsageResult:
        """Aggregate usage for a customer and metric code within a time period.

        Args:
            external_customer_id: Customer to aggregate for
            code: Billable metric code
            from_timestamp: Start of period
            to_timestamp: End of period
            filters: Optional dict of property key-value pairs to filter events
            organization_id: Organization to scope the metric lookup to.

        Returns:
            UsageResult with aggregated value and events count.
        """
        metric = self.metric_repo.get_by_code(code, organization_id)
        if not metric:
            raise ValueError(f"Billable metric with code '{code}' not found")

        aggregation_type = AggregationType(metric.aggregation_type)

        # Delegate to ClickHouse when enabled
        from app.core.config import settings as _settings

        if _settings.clickhouse_enabled:
            from app.services.clickhouse_aggregation import clickhouse_aggregate

            ch_result = clickhouse_aggregate(
                organization_id=organization_id,
                code=code,
                external_customer_id=external_customer_id,
                from_timestamp=from_timestamp,
                to_timestamp=to_timestamp,
                aggregation_type=aggregation_type,
                field_name=str(metric.field_name) if metric.field_name else None,
                expression=str(metric.expression) if metric.expression else None,
                filters=filters,
            )
            ch_rounding_fn: str | None = (
                str(metric.rounding_function) if metric.rounding_function else None
            )
            ch_rounding_prec: int | None = (
                int(metric.rounding_precision)
                if metric.rounding_precision is not None
                else None
            )
            return UsageResult(
                value=_apply_rounding(ch_result.value, ch_rounding_fn, ch_rounding_prec),
                events_count=ch_result.events_count,
            )

        query = self.db.query(Event).filter(
            Event.external_customer_id == external_customer_id,
            Event.code == code,
            Event.timestamp >= from_timestamp,
            Event.timestamp < to_timestamp,
        )

        events = query.all()

        # Apply property-based filters
        if filters:
            events = [
                e for e in events if all(e.properties.get(k) == v for k, v in filters.items())
            ]

        events_count = len(events)

        result = self._compute_aggregation(
            aggregation_type=aggregation_type,
            metric=metric,
            events=events,
            events_count=events_count,
            code=code,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
        )

        # Apply rounding
        rounding_fn: str | None = (
            str(metric.rounding_function) if metric.rounding_function else None
        )
        rounding_prec: int | None = (
            int(metric.rounding_precision) if metric.rounding_precision is not None else None
        )
        result = UsageResult(
            value=_apply_rounding(result.value, rounding_fn, rounding_prec),
            events_count=result.events_count,
        )

        return result

    def _compute_aggregation(
        self,
        aggregation_type: AggregationType,
        metric: BillableMetric,
        events: list[Event],
        events_count: int,
        code: str,
        from_timestamp: datetime,
        to_timestamp: datetime,
    ) -> UsageResult:
        """Compute the aggregation value based on the aggregation type."""
        if aggregation_type == AggregationType.COUNT:
            return UsageResult(value=Decimal(events_count), events_count=events_count)

        elif aggregation_type == AggregationType.SUM:
            if not metric.field_name:
                raise ValueError(f"Metric '{code}' requires field_name for SUM aggregation")
            total = Decimal(0)
            for event in events:
                value = event.properties.get(metric.field_name, 0)
                total += Decimal(str(value))
            return UsageResult(value=total, events_count=events_count)

        elif aggregation_type == AggregationType.MAX:
            if not metric.field_name:
                raise ValueError(f"Metric '{code}' requires field_name for MAX aggregation")
            if not events:
                return UsageResult(value=Decimal(0), events_count=0)
            max_val = Decimal(0)
            for event in events:
                value = event.properties.get(metric.field_name, 0)
                max_val = max(max_val, Decimal(str(value)))
            return UsageResult(value=max_val, events_count=events_count)

        elif aggregation_type == AggregationType.UNIQUE_COUNT:
            if not metric.field_name:
                raise ValueError(
                    f"Metric '{code}' requires field_name for UNIQUE_COUNT aggregation"
                )
            unique_values = set()
            for event in events:
                value = event.properties.get(metric.field_name)
                if value is not None:
                    unique_values.add(value)
            return UsageResult(value=Decimal(len(unique_values)), events_count=events_count)

        elif aggregation_type == AggregationType.WEIGHTED_SUM:
            if not metric.field_name:
                raise ValueError(
                    f"Metric '{code}' requires field_name for WEIGHTED_SUM aggregation"
                )
            if not events:
                return UsageResult(value=Decimal(0), events_count=0)
            total_seconds = Decimal(str((to_timestamp - from_timestamp).total_seconds()))
            if total_seconds == 0:
                return UsageResult(value=Decimal(0), events_count=events_count)
            # Sort events by timestamp
            sorted_events = sorted(events, key=lambda e: e.timestamp)
            # Normalize to_timestamp to match event timestamp tz-awareness
            period_end = _strip_tz(to_timestamp)
            weighted_sum = Decimal(0)
            for i, event in enumerate(sorted_events):
                value = Decimal(str(event.properties.get(metric.field_name, 0)))
                event_ts = _strip_tz(event.timestamp)  # type: ignore[arg-type]
                if i + 1 < len(sorted_events):
                    next_ts = _strip_tz(sorted_events[i + 1].timestamp)  # type: ignore[arg-type]
                else:
                    next_ts = period_end
                interval = Decimal(str((next_ts - event_ts).total_seconds()))
                weighted_sum += value * interval / total_seconds
            return UsageResult(value=weighted_sum, events_count=events_count)

        elif aggregation_type == AggregationType.LATEST:
            if not metric.field_name:
                raise ValueError(f"Metric '{code}' requires field_name for LATEST aggregation")
            if not events:
                return UsageResult(value=Decimal(0), events_count=0)
            latest_event = max(events, key=lambda e: e.timestamp)
            value = latest_event.properties.get(metric.field_name, 0)
            return UsageResult(value=Decimal(str(value)), events_count=events_count)

        elif aggregation_type == AggregationType.CUSTOM:
            if not metric.expression:
                raise ValueError(f"Metric '{code}' requires expression for CUSTOM aggregation")
            if not events:
                return UsageResult(value=Decimal(0), events_count=0)
            total = Decimal(0)
            for event in events:
                variables = {
                    k: Decimal(str(v))
                    for k, v in event.properties.items()
                    if isinstance(v, (int, float, str)) and _is_numeric(v)
                }
                total += _evaluate_expression(str(metric.expression), variables)
            return UsageResult(value=total, events_count=events_count)

        else:
            raise ValueError(f"Unknown aggregation type: {aggregation_type}")

    def get_customer_usage_summary(
        self,
        external_customer_id: str,
        from_timestamp: datetime,
        to_timestamp: datetime,
        organization_id: UUID = DEFAULT_ORGANIZATION_ID,
    ) -> dict[str, Decimal]:
        """Get usage summary for all metrics for a customer.

        Args:
            external_customer_id: Customer to summarize for.
            from_timestamp: Start of period.
            to_timestamp: End of period.
            organization_id: Organization to scope the metric lookup to.

        Returns:
            Dictionary mapping metric code to aggregated usage value.
        """
        # Get all unique metric codes for this customer's events in the period
        codes = (
            self.db.query(Event.code)
            .filter(
                Event.external_customer_id == external_customer_id,
                Event.timestamp >= from_timestamp,
                Event.timestamp < to_timestamp,
            )
            .distinct()
            .all()
        )

        summary = {}
        for (code,) in codes:
            try:
                summary[code] = self.aggregate_usage(
                    external_customer_id,
                    code,
                    from_timestamp,
                    to_timestamp,
                    organization_id=organization_id,
                )
            except ValueError:
                # Skip metrics that don't exist
                continue

        return summary


def _strip_tz(dt: datetime) -> datetime:
    """Strip timezone info from a datetime for safe arithmetic with naive datetimes."""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def _is_numeric(value: object) -> bool:
    """Check if a value can be converted to Decimal."""
    try:
        Decimal(str(value))
        return True
    except Exception:
        return False
