import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.config import settings
from app.core.database import get_db
from app.core.idempotency import IdempotencyResult, check_idempotency, record_idempotency_response
from app.core.rate_limiter import RateLimiter
from app.models.charge import ChargeModel
from app.models.event import Event
from app.models.subscription import SubscriptionStatus
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.charge_repository import ChargeRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.event_repository import EventRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.event import (
    EventBatchCreate,
    EventBatchResponse,
    EventCreate,
    EventResponse,
)
from app.schemas.invoice_preview import EstimateFeesRequest, EstimateFeesResponse
from app.services.charge_models.factory import get_charge_calculator
from app.services.usage_aggregation import UsageAggregationService
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


@router.post(
    "/estimate_fees",
    response_model=EstimateFeesResponse,
    summary="Estimate fees for a hypothetical event",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Subscription or charge not found"},
        422: {"description": "Billable metric code does not exist"},
    },
)
async def estimate_fees(
    data: EstimateFeesRequest,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> EstimateFeesResponse:
    """Estimate fees from a hypothetical event.

    Aggregates current-period usage for the given metric, adds the hypothetical
    event's contribution, and applies the charge model to return the estimated
    fee amount.
    """
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(data.subscription_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if subscription.status != SubscriptionStatus.ACTIVE.value:
        raise HTTPException(status_code=400, detail="Subscription is not active")

    metric_repo = BillableMetricRepository(db)
    metric = metric_repo.get_by_code(data.code, organization_id)
    if not metric:
        raise HTTPException(
            status_code=422,
            detail=f"Billable metric with code '{data.code}' does not exist",
        )

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(subscription.customer_id)  # type: ignore[arg-type]
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    plan_id = UUID(str(subscription.plan_id))
    charge_repo = ChargeRepository(db)
    charges = charge_repo.get_by_plan_id(plan_id)
    metric_id = UUID(str(metric.id))
    charge = next(
        (c for c in charges if UUID(str(c.billable_metric_id)) == metric_id),
        None,
    )
    if not charge:
        raise HTTPException(
            status_code=404,
            detail=f"No charge found for metric '{data.code}' on this subscription's plan",
        )

    # Determine current billing period
    now = datetime.now()
    billing_period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    billing_period_end = now

    # Aggregate current usage
    usage_service = UsageAggregationService(db)
    usage_result = usage_service.aggregate_usage_with_count(
        external_customer_id=str(customer.external_id),
        code=data.code,
        from_timestamp=billing_period_start,
        to_timestamp=billing_period_end,
    )

    # Add hypothetical event contribution
    usage_with_event = _add_hypothetical_event(
        current_usage=usage_result.value,
        current_count=usage_result.events_count,
        aggregation_type=str(metric.aggregation_type),
        field_name=str(metric.field_name) if metric.field_name else None,
        event_properties=data.properties,
    )

    # Apply charge model
    charge_model = ChargeModel(charge.charge_model)
    properties: dict[str, Any] = dict(charge.properties) if charge.properties else {}
    unit_price = Decimal(str(properties.get("unit_price", 0)))
    calculator = get_charge_calculator(charge_model)
    if not calculator:
        raise HTTPException(status_code=400, detail=f"Unsupported charge model: {charge_model}")

    amount = _calculate_estimated_amount(
        calculator=calculator,
        charge_model=charge_model,
        usage=usage_with_event,
        properties=properties,
    )

    return EstimateFeesResponse(
        charge_model=str(charge.charge_model),
        metric_code=data.code,
        units=usage_with_event,
        amount_cents=amount,
        unit_amount_cents=unit_price if usage_with_event else amount,
    )


def _add_hypothetical_event(
    current_usage: Decimal,
    current_count: int,
    aggregation_type: str,
    field_name: str | None,
    event_properties: dict[str, Any],
) -> Decimal:
    """Add a hypothetical event's contribution to the current usage."""
    from app.models.billable_metric import AggregationType

    agg = AggregationType(aggregation_type)

    if agg == AggregationType.COUNT:
        return current_usage + 1

    if agg in (AggregationType.SUM, AggregationType.WEIGHTED_SUM):
        event_value = Decimal(str(event_properties.get(field_name or "", 0)))
        return current_usage + event_value

    if agg == AggregationType.MAX:
        event_value = Decimal(str(event_properties.get(field_name or "", 0)))
        return max(current_usage, event_value)

    if agg == AggregationType.LATEST:
        event_value = Decimal(str(event_properties.get(field_name or "", 0)))
        return event_value

    if agg == AggregationType.UNIQUE_COUNT:
        # Conservatively assume the new value is unique
        return current_usage + 1

    # CUSTOM or unknown — conservatively add 1
    return current_usage + 1


def _calculate_estimated_amount(
    calculator: Any,
    charge_model: ChargeModel,
    usage: Decimal,
    properties: dict[str, Any],
) -> Decimal:
    """Calculate the estimated fee amount using the charge calculator."""
    amount: Decimal
    if charge_model in (
        ChargeModel.STANDARD,
        ChargeModel.GRADUATED,
        ChargeModel.VOLUME,
        ChargeModel.PACKAGE,
        ChargeModel.CUSTOM,
    ):
        amount = Decimal(str(calculator(units=usage, properties=properties)))
    elif charge_model == ChargeModel.PERCENTAGE:
        total_amount = Decimal(str(properties.get("base_amount", 0)))
        event_count = int(properties.get("event_count", 0))
        amount = Decimal(
            str(
                calculator(
                    units=usage,
                    properties=properties,
                    total_amount=total_amount,
                    event_count=event_count,
                )
            )
        )
    elif charge_model == ChargeModel.GRADUATED_PERCENTAGE:
        usage_amount = Decimal(str(properties.get("base_amount", usage)))
        amount = Decimal(str(calculator(total_amount=usage_amount, properties=properties)))
    else:  # DYNAMIC
        amount = Decimal(str(calculator(events=[], properties=properties)))

    # Apply min/max price constraints for standard charges
    if charge_model == ChargeModel.STANDARD:
        min_price = Decimal(str(properties.get("min_price", 0)))
        max_price = Decimal(str(properties.get("max_price", 0)))
        if min_price and amount < min_price:
            amount = min_price
        if max_price and amount > max_price:
            amount = max_price

    return amount


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
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(_check_rate_limit),
) -> Event | JSONResponse:
    """Ingest a single event.

    If an event with the same transaction_id already exists, returns the existing event.
    This provides idempotent event ingestion.  The ``Idempotency-Key`` header adds an
    additional layer of deduplication on top of the existing ``transaction_id`` check.
    """
    idempotency = check_idempotency(request, db, organization_id)
    if isinstance(idempotency, JSONResponse):
        return idempotency

    validate_billable_metric_code(data.code, db, organization_id)

    repo = EventRepository(db)
    event, is_new = repo.create_or_get_existing(data, organization_id)

    if is_new:
        sub_ids = _get_active_subscription_ids(data.external_customer_id, db, organization_id)
        if sub_ids:
            background_tasks.add_task(_enqueue_threshold_checks, sub_ids)

    if isinstance(idempotency, IdempotencyResult):
        body = EventResponse.model_validate(event).model_dump(mode="json")
        record_idempotency_response(db, organization_id, idempotency.key, 201, body)

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
