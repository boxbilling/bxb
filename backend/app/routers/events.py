import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limiter import RateLimiter
from app.models.event import Event
from app.models.subscription import SubscriptionStatus
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.event_repository import EventRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.event import (
    EventBatchCreate,
    EventBatchResponse,
    EventCreate,
    EventResponse,
)
from app.tasks import enqueue_check_usage_thresholds

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level rate limiter instance for event ingestion
event_rate_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_EVENTS_PER_MINUTE,
    window_seconds=60,
)


def _check_rate_limit(
    request: Request, organization_id: UUID = Depends(get_current_organization)
) -> UUID:
    """Dependency that enforces event ingestion rate limiting per organization."""
    key = str(organization_id)
    if not event_rate_limiter.is_allowed(key):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum "
            f"{settings.RATE_LIMIT_EVENTS_PER_MINUTE} events per minute.",
        )
    return organization_id


def validate_billable_metric_code(code: str, db: Session, organization_id: UUID) -> None:
    """Validate that the billable metric code exists."""
    metric_repo = BillableMetricRepository(db)
    if not metric_repo.code_exists(code, organization_id):
        raise HTTPException(
            status_code=422,
            detail=f"Billable metric with code '{code}' does not exist",
        )


def _get_active_subscription_ids(
    external_customer_id: str, db: Session, organization_id: UUID
) -> list[str]:
    """Find active subscription IDs for the given external customer.

    Looks up the customer by external_id and returns the IDs of all
    active subscriptions as strings (for task serialization).
    """
    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_external_id(external_customer_id, organization_id)
    if not customer:
        return []

    sub_repo = SubscriptionRepository(db)
    subscriptions = sub_repo.get_by_customer_id(
        customer_id=UUID(str(customer.id)),
        organization_id=organization_id,
    )
    return [str(sub.id) for sub in subscriptions if sub.status == SubscriptionStatus.ACTIVE.value]


async def _enqueue_threshold_checks(subscription_ids: list[str]) -> None:
    """Enqueue threshold check tasks for the given subscription IDs."""
    for sub_id in subscription_ids:
        try:
            await enqueue_check_usage_thresholds(sub_id)
        except Exception:
            logger.exception("Failed to enqueue threshold check for subscription %s", sub_id)


@router.get(
    "/",
    response_model=list[EventResponse],
    summary="List events",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_events(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    external_customer_id: str | None = None,
    code: str | None = None,
    from_timestamp: datetime | None = None,
    to_timestamp: datetime | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Event]:
    """List events with optional filters."""
    repo = EventRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(
        organization_id,
        skip=skip,
        limit=limit,
        external_customer_id=external_customer_id,
        code=code,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
    )


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get event",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Event not found"},
    },
)
async def get_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Event:
    """Get an event by ID."""
    repo = EventRepository(db)
    event = repo.get_by_id(event_id, organization_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post(
    "/",
    response_model=EventResponse,
    status_code=201,
    summary="Ingest event",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        422: {"description": "Billable metric code does not exist"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def create_event(
    data: EventCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(_check_rate_limit),
) -> Event:
    """Ingest a single event.

    If an event with the same transaction_id already exists, returns the existing event.
    This provides idempotent event ingestion.
    """
    validate_billable_metric_code(data.code, db, organization_id)

    repo = EventRepository(db)
    event, is_new = repo.create_or_get_existing(data, organization_id)

    if is_new:
        sub_ids = _get_active_subscription_ids(data.external_customer_id, db, organization_id)
        if sub_ids:
            background_tasks.add_task(_enqueue_threshold_checks, sub_ids)

    return event


@router.post(
    "/batch",
    response_model=EventBatchResponse,
    status_code=201,
    summary="Ingest event batch",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        422: {"description": "Billable metric code does not exist"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def create_events_batch(
    data: EventBatchCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(_check_rate_limit),
) -> EventBatchResponse:
    """Ingest a batch of events (up to 100).

    Duplicate transaction_ids are handled gracefully - existing events are returned
    without error. The response includes counts of newly ingested vs duplicate events.
    """
    # Validate all billable metric codes upfront
    unique_codes = {event.code for event in data.events}
    for code in unique_codes:
        validate_billable_metric_code(code, db, organization_id)

    repo = EventRepository(db)
    events, ingested, duplicates = repo.create_batch(data.events, organization_id)

    if ingested > 0:
        # Collect unique external_customer_ids from the batch
        unique_customer_ids = {event.external_customer_id for event in data.events}
        all_sub_ids: list[str] = []
        for ext_cust_id in unique_customer_ids:
            all_sub_ids.extend(_get_active_subscription_ids(ext_cust_id, db, organization_id))
        # Deduplicate subscription IDs
        unique_sub_ids = list(set(all_sub_ids))
        if unique_sub_ids:
            background_tasks.add_task(_enqueue_threshold_checks, unique_sub_ids)

    return EventBatchResponse(
        ingested=ingested,
        duplicates=duplicates,
        events=[EventResponse.model_validate(e) for e in events],
    )
