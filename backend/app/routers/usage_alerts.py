from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.core.idempotency import IdempotencyResult, check_idempotency, record_idempotency_response
from app.models.usage_alert import UsageAlert
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_alert_repository import UsageAlertRepository
from app.repositories.usage_alert_trigger_repository import UsageAlertTriggerRepository
from app.schemas.usage_alert import (
    UsageAlertCreate,
    UsageAlertResponse,
    UsageAlertStatusResponse,
    UsageAlertTriggerResponse,
    UsageAlertUpdate,
)
from app.services.subscription_dates import SubscriptionDatesService
from app.services.usage_alert_service import UsageAlertService

router = APIRouter()


@router.get(
    "/",
    response_model=list[UsageAlertResponse],
    summary="List usage alerts",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_usage_alerts(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    subscription_id: UUID | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[UsageAlert]:
    """List usage alerts with optional subscription filter."""
    repo = UsageAlertRepository(db)
    response.headers["X-Total-Count"] = str(
        repo.count(organization_id, subscription_id=subscription_id)
    )
    return repo.get_all(
        organization_id, skip=skip, limit=limit, subscription_id=subscription_id
    )


@router.get(
    "/{alert_id}",
    response_model=UsageAlertResponse,
    summary="Get usage alert",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Usage alert not found"},
    },
)
async def get_usage_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> UsageAlert:
    """Get a usage alert by ID."""
    repo = UsageAlertRepository(db)
    alert = repo.get_by_id(alert_id, organization_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Usage alert not found")
    return alert


@router.post(
    "/",
    response_model=UsageAlertResponse,
    status_code=201,
    summary="Create usage alert",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Subscription or billable metric not found"},
        422: {"description": "Validation error"},
    },
)
async def create_usage_alert(
    data: UsageAlertCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> UsageAlert | JSONResponse:
    """Create a new usage alert for a subscription and metric."""
    idempotency = check_idempotency(request, db, organization_id)
    if isinstance(idempotency, JSONResponse):
        return idempotency

    sub_repo = SubscriptionRepository(db)
    if not sub_repo.get_by_id(data.subscription_id, organization_id):
        raise HTTPException(status_code=404, detail="Subscription not found")

    metric_repo = BillableMetricRepository(db)
    if not metric_repo.get_by_id(data.billable_metric_id, organization_id):
        raise HTTPException(status_code=404, detail="Billable metric not found")

    repo = UsageAlertRepository(db)
    alert = repo.create(data, organization_id)

    if isinstance(idempotency, IdempotencyResult):
        body = UsageAlertResponse.model_validate(alert).model_dump(mode="json")
        record_idempotency_response(db, organization_id, idempotency.key, 201, body)

    return alert


@router.patch(
    "/{alert_id}",
    response_model=UsageAlertResponse,
    summary="Update usage alert",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Usage alert not found"},
        422: {"description": "Validation error"},
    },
)
async def update_usage_alert(
    alert_id: UUID,
    data: UsageAlertUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> UsageAlert:
    """Update a usage alert's threshold, name, or recurring flag."""
    repo = UsageAlertRepository(db)
    alert = repo.update(alert_id, data, organization_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Usage alert not found")
    return alert


@router.delete(
    "/{alert_id}",
    status_code=204,
    summary="Delete usage alert",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Usage alert not found"},
    },
)
async def delete_usage_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a usage alert."""
    repo = UsageAlertRepository(db)
    if not repo.delete(alert_id, organization_id):
        raise HTTPException(status_code=404, detail="Usage alert not found")


def _resolve_billing_period(
    db: Session,
    alert: UsageAlert,
    organization_id: UUID,
) -> tuple[str, datetime, datetime]:
    """Look up customer external_id and billing period for an alert's subscription.

    Returns:
        Tuple of (external_customer_id, period_start, period_end).

    Raises:
        HTTPException: If subscription, plan, or customer is not found.
    """
    from app.repositories.plan_repository import PlanRepository

    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(
        UUID(str(alert.subscription_id)), organization_id
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    plan_repo = PlanRepository(db)
    plan = plan_repo.get_by_id(UUID(str(subscription.plan_id)))
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    cust_repo = CustomerRepository(db)
    customer = cust_repo.get_by_id(UUID(str(subscription.customer_id)))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    dates_service = SubscriptionDatesService()
    now = datetime.now(UTC)
    period_start, period_end = dates_service.calculate_billing_period(
        subscription, str(plan.interval), now
    )
    return str(customer.external_id), period_start, period_end


@router.get(
    "/{alert_id}/status",
    response_model=UsageAlertStatusResponse,
    summary="Get usage alert status with current usage",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Usage alert, subscription, plan, or customer not found"},
    },
)
async def get_usage_alert_status(
    alert_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> UsageAlertStatusResponse:
    """Get current usage status for a usage alert."""
    repo = UsageAlertRepository(db)
    alert = repo.get_by_id(alert_id, organization_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Usage alert not found")

    external_customer_id, period_start, period_end = _resolve_billing_period(
        db, alert, organization_id
    )

    service = UsageAlertService(db)
    current_usage = service.get_current_usage_for_alert(
        alert=alert,
        external_customer_id=external_customer_id,
        billing_period_start=period_start,
        billing_period_end=period_end,
    )

    threshold = Decimal(str(alert.threshold_value))
    percentage = (current_usage / threshold * 100) if threshold > 0 else Decimal(0)

    return UsageAlertStatusResponse(
        alert_id=alert_id,
        current_usage=current_usage,
        threshold_value=threshold,
        usage_percentage=percentage,
        billing_period_start=period_start,
        billing_period_end=period_end,
    )


@router.get(
    "/{alert_id}/triggers",
    response_model=list[UsageAlertTriggerResponse],
    summary="List alert trigger history",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Usage alert not found"},
    },
)
async def list_alert_triggers(
    alert_id: UUID,
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[UsageAlertTriggerResponse]:
    """List trigger history for a usage alert."""
    repo = UsageAlertRepository(db)
    alert = repo.get_by_id(alert_id, organization_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Usage alert not found")

    trigger_repo = UsageAlertTriggerRepository(db)
    response.headers["X-Total-Count"] = str(
        trigger_repo.count_by_alert_id(alert_id)
    )
    triggers = trigger_repo.get_by_alert_id(alert_id, skip=skip, limit=limit)
    return [UsageAlertTriggerResponse.model_validate(t) for t in triggers]


@router.post(
    "/{alert_id}/test",
    response_model=UsageAlertStatusResponse,
    summary="Test a usage alert by checking current usage",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Usage alert, subscription, plan, or customer not found"},
    },
)
async def test_usage_alert(
    alert_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> UsageAlertStatusResponse:
    """Test a usage alert by computing current usage and returning the status.

    This does NOT actually trigger the alert or send webhooks; it only shows
    what the current usage vs threshold looks like.
    """
    repo = UsageAlertRepository(db)
    alert = repo.get_by_id(alert_id, organization_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Usage alert not found")

    external_customer_id, period_start, period_end = _resolve_billing_period(
        db, alert, organization_id
    )

    service = UsageAlertService(db)
    current_usage = service.get_current_usage_for_alert(
        alert=alert,
        external_customer_id=external_customer_id,
        billing_period_start=period_start,
        billing_period_end=period_end,
    )

    threshold = Decimal(str(alert.threshold_value))
    percentage = (current_usage / threshold * 100) if threshold > 0 else Decimal(0)

    return UsageAlertStatusResponse(
        alert_id=alert_id,
        current_usage=current_usage,
        threshold_value=threshold,
        usage_percentage=percentage,
        billing_period_start=period_start,
        billing_period_end=period_end,
    )
