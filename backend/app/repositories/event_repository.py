from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.event import Event
from app.schemas.event import EventCreate


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        external_customer_id: str | None = None,
        code: str | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
    ) -> list[Event]:
        query = self.db.query(Event)

        if external_customer_id:
            query = query.filter(Event.external_customer_id == external_customer_id)
        if code:
            query = query.filter(Event.code == code)
        if from_timestamp:
            query = query.filter(Event.timestamp >= from_timestamp)
        if to_timestamp:
            query = query.filter(Event.timestamp <= to_timestamp)

        return query.order_by(Event.timestamp.desc()).offset(skip).limit(limit).all()

    def get_by_id(self, event_id: UUID) -> Event | None:
        return self.db.query(Event).filter(Event.id == event_id).first()

    def get_by_transaction_id(self, transaction_id: str) -> Event | None:
        return self.db.query(Event).filter(Event.transaction_id == transaction_id).first()

    def transaction_id_exists(self, transaction_id: str) -> bool:
        """Check if an event with the given transaction_id already exists."""
        query = self.db.query(Event).filter(Event.transaction_id == transaction_id)
        return query.first() is not None

    def create(self, data: EventCreate) -> Event:
        event = Event(
            transaction_id=data.transaction_id,
            external_customer_id=data.external_customer_id,
            code=data.code,
            timestamp=data.timestamp,
            properties=data.properties,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def create_or_get_existing(self, data: EventCreate) -> tuple[Event, bool]:
        """Create an event or return existing one if transaction_id exists.

        Returns:
            Tuple of (event, is_new) where is_new is True if created, False if existing.
        """
        existing = self.get_by_transaction_id(data.transaction_id)
        if existing:
            return existing, False
        return self.create(data), True

    def create_batch(self, events_data: list[EventCreate]) -> tuple[list[Event], int, int]:
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
            existing = self.get_by_transaction_id(data.transaction_id)
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

        return events, ingested, duplicates

    def delete(self, event_id: UUID) -> bool:
        event = self.get_by_id(event_id)
        if not event:
            return False
        self.db.delete(event)
        self.db.commit()
        return True
