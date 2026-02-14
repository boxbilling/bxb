import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.event import Event
from app.schemas.event import EventCreate

logger = logging.getLogger(__name__)


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        external_customer_id: str | None = None,
        code: str | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
    ) -> list[Event]:
        query = self.db.query(Event).filter(Event.organization_id == organization_id)

        if external_customer_id:
            query = query.filter(Event.external_customer_id == external_customer_id)
        if code:
            query = query.filter(Event.code == code)
        if from_timestamp:
            query = query.filter(Event.timestamp >= from_timestamp)
        if to_timestamp:
            query = query.filter(Event.timestamp <= to_timestamp)

        return query.order_by(Event.timestamp.desc()).offset(skip).limit(limit).all()

    def count(self, organization_id: UUID) -> int:
        return (
            self.db.query(func.count(Event.id))
            .filter(Event.organization_id == organization_id)
            .scalar()
            or 0
        )

    def get_by_id(self, event_id: UUID, organization_id: UUID | None = None) -> Event | None:
        query = self.db.query(Event).filter(Event.id == event_id)
        if organization_id is not None:
            query = query.filter(Event.organization_id == organization_id)
        return query.first()

    def get_by_transaction_id(
        self, transaction_id: str, organization_id: UUID | None = None
    ) -> Event | None:
        query = self.db.query(Event).filter(Event.transaction_id == transaction_id)
        if organization_id is not None:
            query = query.filter(Event.organization_id == organization_id)
        return query.first()

    def transaction_id_exists(self, transaction_id: str, organization_id: UUID) -> bool:
        """Check if an event with the given transaction_id already exists."""
        query = self.db.query(Event).filter(
            Event.transaction_id == transaction_id,
            Event.organization_id == organization_id,
        )
        return query.first() is not None

    def create(self, data: EventCreate, organization_id: UUID) -> Event:
        event = Event(
            transaction_id=data.transaction_id,
            external_customer_id=data.external_customer_id,
            code=data.code,
            timestamp=data.timestamp,
            properties=data.properties,
            organization_id=organization_id,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        self._clickhouse_insert(data, organization_id)

        return event

    def create_or_get_existing(
        self, data: EventCreate, organization_id: UUID
    ) -> tuple[Event, bool]:
        """Create an event or return existing one if transaction_id exists.

        Returns:
            Tuple of (event, is_new) where is_new is True if created, False if existing.
        """
        existing = self.get_by_transaction_id(data.transaction_id, organization_id)
        if existing:
            return existing, False
        return self.create(data, organization_id), True

    def create_batch(
        self, events_data: list[EventCreate], organization_id: UUID
    ) -> tuple[list[Event], int, int]:
        """Create multiple events, handling duplicates gracefully.

        Returns:
            Tuple of (events, ingested_count, duplicate_count)
        """
        events: list[Event] = []
        new_events: list[Event] = []
        ingested = 0
        duplicates = 0

        # First pass: check for existing events and create new ones (without commit)
        for data in events_data:
            existing = self.get_by_transaction_id(data.transaction_id, organization_id)
            if existing:
                events.append(existing)
                duplicates += 1
            else:
                event = Event(
                    transaction_id=data.transaction_id,
                    external_customer_id=data.external_customer_id,
                    code=data.code,
                    timestamp=data.timestamp,
                    properties=data.properties,
                    organization_id=organization_id,
                )
                self.db.add(event)
                new_events.append(event)
                events.append(event)
                ingested += 1

        # Single commit for all new events
        if new_events:
            self.db.commit()
            for event in new_events:
                self.db.refresh(event)

        # Dual-write new events to ClickHouse
        new_event_data = [
            d
            for d in events_data
            if d.transaction_id not in {e.transaction_id for e in events if e not in new_events}
        ][:ingested]
        if new_event_data:
            self._clickhouse_insert_batch(new_event_data, organization_id)

        return events, ingested, duplicates

    def delete(self, event_id: UUID, organization_id: UUID) -> bool:
        event = self.get_by_id(event_id, organization_id)
        if not event:
            return False
        self.db.delete(event)
        self.db.commit()
        return True

    def _clickhouse_insert(self, data: EventCreate, organization_id: UUID) -> None:
        """Dual-write a single event to ClickHouse (fire-and-forget)."""
        from app.core.config import settings

        if not settings.clickhouse_enabled:
            return

        from app.services.clickhouse_event_store import insert_event

        field_name = self._resolve_field_name(data.code, organization_id)
        insert_event(data, organization_id, field_name=field_name)

    def _clickhouse_insert_batch(
        self, events_data: list[EventCreate], organization_id: UUID
    ) -> None:
        """Dual-write a batch of events to ClickHouse (fire-and-forget)."""
        from app.core.config import settings

        if not settings.clickhouse_enabled:
            return

        from app.services.clickhouse_event_store import insert_events_batch

        field_names = self._resolve_field_names(events_data, organization_id)
        insert_events_batch(events_data, organization_id, field_names=field_names)

    def _resolve_field_name(self, code: str, organization_id: UUID) -> str | None:
        """Look up the billable metric field_name for a given code."""
        from app.repositories.billable_metric_repository import BillableMetricRepository

        metric_repo = BillableMetricRepository(self.db)
        metric = metric_repo.get_by_code(code, organization_id)
        if metric and metric.field_name:
            return str(metric.field_name)
        return None

    def _resolve_field_names(
        self, events_data: list[EventCreate], organization_id: UUID
    ) -> dict[str, str | None]:
        """Look up field_names for all unique codes in a batch."""
        unique_codes = {e.code for e in events_data}
        result: dict[str, str | None] = {}
        for code in unique_codes:
            result[code] = self._resolve_field_name(code, organization_id)
        return result
