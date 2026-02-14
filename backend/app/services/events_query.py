"""Shared helper for fetching raw event properties.

Routes through ClickHouse when enabled, otherwise queries the SQL Event model.
Used by invoice generation and usage threshold services for DYNAMIC charges.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings


def fetch_event_properties(
    db: Session,
    external_customer_id: str,
    code: str,
    from_timestamp: datetime,
    to_timestamp: datetime,
    organization_id: UUID | None = None,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch raw event properties for DYNAMIC charge calculations.

    When ClickHouse is enabled, queries ClickHouse. Otherwise queries SQL.

    Args:
        db: SQLAlchemy session (used for SQL fallback).
        external_customer_id: Customer external ID.
        code: Billable metric code.
        from_timestamp: Start of period.
        to_timestamp: End of period (exclusive).
        organization_id: Organization ID (required for ClickHouse path).
        filters: Optional property-based filters.

    Returns:
        List of event property dicts.
    """
    if settings.clickhouse_enabled and organization_id is not None:
        from app.services.clickhouse_aggregation import fetch_raw_event_properties

        all_props = fetch_raw_event_properties(
            organization_id, code, external_customer_id, from_timestamp, to_timestamp
        )
        if filters:
            return [
                p for p in all_props
                if all(p.get(k) == v for k, v in filters.items())
            ]
        return all_props

    from app.models.event import Event

    raw_events = (
        db.query(Event)
        .filter(
            Event.external_customer_id == external_customer_id,
            Event.code == code,
            Event.timestamp >= from_timestamp,
            Event.timestamp < to_timestamp,
        )
        .all()
    )

    props_list = [dict(e.properties) if e.properties else {} for e in raw_events]

    if filters:
        return [p for p in props_list if all(p.get(k) == v for k, v in filters.items())]
    return props_list
