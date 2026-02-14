"""ClickHouse event store for writing events to ClickHouse."""

import json
import logging
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.core.clickhouse import EVENTS_RAW_TABLE, get_clickhouse_client
from app.schemas.event import EventCreate

logger = logging.getLogger(__name__)

COLUMNS = [
    "organization_id",
    "transaction_id",
    "external_customer_id",
    "code",
    "timestamp",
    "properties",
    "value",
    "decimal_value",
]


def _extract_value(
    properties: dict[str, object], field_name: str | None
) -> tuple[str | None, Decimal | None]:
    """Extract the value and decimal_value from event properties.

    Returns (value_str, decimal_value) tuple.
    """
    if not field_name:
        return None, None

    raw = properties.get(field_name)
    if raw is None:
        return None, None

    value_str = str(raw)
    try:
        decimal_val = Decimal(value_str)
    except (InvalidOperation, ValueError):
        decimal_val = None

    return value_str, decimal_val


def _build_row(
    event: EventCreate,
    organization_id: UUID,
    field_name: str | None,
) -> list[object]:
    """Build a ClickHouse row from an EventCreate."""
    value_str, decimal_val = _extract_value(event.properties, field_name)
    return [
        str(organization_id),
        event.transaction_id,
        event.external_customer_id,
        event.code,
        event.timestamp,
        json.dumps(event.properties),
        value_str,
        decimal_val,
    ]


def insert_event(
    event: EventCreate,
    organization_id: UUID,
    field_name: str | None = None,
) -> None:
    """Insert a single event into ClickHouse.

    Args:
        event: The event data to insert.
        organization_id: The organization ID.
        field_name: The billable metric field_name for value extraction.
    """
    client = get_clickhouse_client()
    if client is None:
        return

    row = _build_row(event, organization_id, field_name)
    try:
        client.insert(EVENTS_RAW_TABLE, [row], column_names=COLUMNS)
    except Exception:
        logger.exception("Failed to insert event %s into ClickHouse", event.transaction_id)


def insert_events_batch(
    events: list[EventCreate],
    organization_id: UUID,
    field_names: dict[str, str | None] | None = None,
) -> None:
    """Insert a batch of events into ClickHouse.

    Args:
        events: The events to insert.
        organization_id: The organization ID.
        field_names: Mapping of metric code to field_name for value extraction.
    """
    client = get_clickhouse_client()
    if client is None:
        return

    field_names = field_names or {}
    rows = [
        _build_row(event, organization_id, field_names.get(event.code))
        for event in events
    ]

    try:
        client.insert(EVENTS_RAW_TABLE, rows, column_names=COLUMNS)
    except Exception:
        logger.exception("Failed to insert %d events into ClickHouse", len(events))
