from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.core.idempotency import IdempotencyResult, check_idempotency, record_idempotency_response
from app.models.usage_alert import UsageAlert
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_alert_repository import UsageAlertRepository
from app.schemas.usage_alert import UsageAlertCreate, UsageAlertResponse, UsageAlertUpdate

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
