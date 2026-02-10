from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.event import Event
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.event_repository import EventRepository
from app.schemas.event import (
    EventBatchCreate,
    EventBatchResponse,
    EventCreate,
    EventResponse,
)

router = APIRouter()


def validate_billable_metric_code(code: str, db: Session) -> None:
    """Validate that the billable metric code exists."""
    metric_repo = BillableMetricRepository(db)
    if not metric_repo.code_exists(code):
        raise HTTPException(
            status_code=422,
            detail=f"Billable metric with code '{code}' does not exist",
        )


@router.get("/", response_model=list[EventResponse])
async def list_events(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    external_customer_id: str | None = None,
    code: str | None = None,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    db: Session = Depends(get_db),
) -> list[Event]:
    """List events with optional filters."""
    repo = EventRepository(db)
    return repo.get_all(
        skip=skip,
        limit=limit,
        external_customer_id=external_customer_id,
        code=code,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    db: Session = Depends(get_db),
) -> Event:
    """Get an event by ID."""
    repo = EventRepository(db)
    event = repo.get_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/", response_model=EventResponse, status_code=201)
async def create_event(
    data: EventCreate,
    db: Session = Depends(get_db),
) -> Event:
    """Ingest a single event.

    If an event with the same transaction_id already exists, returns the existing event.
    This provides idempotent event ingestion.
    """
    validate_billable_metric_code(data.code, db)

    repo = EventRepository(db)
    event, is_new = repo.create_or_get_existing(data)
    return event


@router.post("/batch", response_model=EventBatchResponse, status_code=201)
async def create_events_batch(
    data: EventBatchCreate,
    db: Session = Depends(get_db),
) -> EventBatchResponse:
    """Ingest a batch of events (up to 100).

    Duplicate transaction_ids are handled gracefully - existing events are returned
    without error. The response includes counts of newly ingested vs duplicate events.
    """
    # Validate all billable metric codes upfront
    unique_codes = {event.code for event in data.events}
    for code in unique_codes:
        validate_billable_metric_code(code, db)

    repo = EventRepository(db)
    events, ingested, duplicates = repo.create_batch(data.events)

    return EventBatchResponse(
        ingested=ingested,
        duplicates=duplicates,
        events=[EventResponse.model_validate(e) for e in events],
    )
