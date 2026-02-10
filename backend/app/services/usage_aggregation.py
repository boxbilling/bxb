from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.billable_metric import AggregationType
from app.models.event import Event
from app.repositories.billable_metric_repository import BillableMetricRepository


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
    ) -> Decimal:
        """Aggregate usage for a customer and metric code within a time period.

        Returns:
            Aggregated usage value based on the metric's aggregation type.
        """
        metric = self.metric_repo.get_by_code(code)
        if not metric:
            raise ValueError(f"Billable metric with code '{code}' not found")

        aggregation_type = AggregationType(metric.aggregation_type)

        query = self.db.query(Event).filter(
            Event.external_customer_id == external_customer_id,
            Event.code == code,
            Event.timestamp >= from_timestamp,
            Event.timestamp < to_timestamp,
        )

        if aggregation_type == AggregationType.COUNT:
            count = query.count()
            return Decimal(count)

        elif aggregation_type == AggregationType.SUM:
            if not metric.field_name:
                raise ValueError(f"Metric '{code}' requires field_name for SUM aggregation")
            events = query.all()
            total = Decimal(0)
            for event in events:
                value = event.properties.get(metric.field_name, 0)
                total += Decimal(str(value))
            return total

        elif aggregation_type == AggregationType.MAX:
            if not metric.field_name:
                raise ValueError(f"Metric '{code}' requires field_name for MAX aggregation")
            events = query.all()
            if not events:
                return Decimal(0)
            max_val = Decimal(0)
            for event in events:
                value = event.properties.get(metric.field_name, 0)
                max_val = max(max_val, Decimal(str(value)))
            return max_val

        elif aggregation_type == AggregationType.UNIQUE_COUNT:
            if not metric.field_name:
                raise ValueError(
                    f"Metric '{code}' requires field_name for UNIQUE_COUNT aggregation"
                )
            events = query.all()
            unique_values = set()
            for event in events:
                value = event.properties.get(metric.field_name)
                if value is not None:
                    unique_values.add(value)
            return Decimal(len(unique_values))

        else:  # pragma: no cover
            raise ValueError(f"Unknown aggregation type: {aggregation_type}")

    def get_customer_usage_summary(
        self,
        external_customer_id: str,
        from_timestamp: datetime,
        to_timestamp: datetime,
    ) -> dict[str, Decimal]:
        """Get usage summary for all metrics for a customer.

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
                    external_customer_id, code, from_timestamp, to_timestamp
                )
            except ValueError:
                # Skip metrics that don't exist
                continue

        return summary
