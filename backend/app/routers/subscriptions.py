from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.core.idempotency import IdempotencyResult, check_idempotency, record_idempotency_response
from app.models.entitlement import Entitlement
from app.models.subscription import Subscription, TerminationAction
from app.repositories.customer_repository import CustomerRepository
from app.repositories.entitlement_repository import EntitlementRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.entitlement import EntitlementResponse
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse, SubscriptionUpdate
from app.services.audit_service import AuditService
from app.services.subscription_lifecycle import SubscriptionLifecycleService
from app.services.webhook_service import WebhookService

router = APIRouter()


@router.get(
    "/",
    response_model=list[SubscriptionResponse],
    summary="List subscriptions",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_subscriptions(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    customer_id: UUID | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Subscription]:
    """List all subscriptions with pagination. Optionally filter by customer_id."""
    repo = SubscriptionRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    if customer_id:
        return repo.get_by_customer_id(customer_id, organization_id)
    return repo.get_all(organization_id, skip=skip, limit=limit)


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Get subscription",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Subscription not found"},
    },
)
async def get_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Subscription:
    """Get a subscription by ID."""
    repo = SubscriptionRepository(db)
    subscription = repo.get_by_id(subscription_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


@router.post(
    "/",
    response_model=SubscriptionResponse,
    status_code=201,
    summary="Create subscription",
    responses={
        400: {"description": "Invalid customer or plan reference"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        409: {"description": "Subscription with this external_id already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_subscription(
    data: SubscriptionCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Subscription | JSONResponse:
    """Create a new subscription."""
    idempotency = check_idempotency(request, db, organization_id)
    if isinstance(idempotency, JSONResponse):
        return idempotency

    repo = SubscriptionRepository(db)

    # Check if external_id already exists
    if repo.external_id_exists(data.external_id, organization_id):
        raise HTTPException(
            status_code=409, detail="Subscription with this external_id already exists"
        )

    # Validate customer exists
    customer_repo = CustomerRepository(db)
    if not customer_repo.get_by_id(data.customer_id, organization_id):
        raise HTTPException(status_code=400, detail=f"Customer {data.customer_id} not found")

    # Validate plan exists
    plan_repo = PlanRepository(db)
    if not plan_repo.get_by_id(data.plan_id, organization_id):
        raise HTTPException(status_code=400, detail=f"Plan {data.plan_id} not found")

    subscription = repo.create(data, organization_id)

    audit_service = AuditService(db)
    audit_service.log_create(
        resource_type="subscription",
        resource_id=subscription.id,  # type: ignore[arg-type]
        organization_id=organization_id,
        actor_type="api_key",
        data={
            "customer_id": str(data.customer_id),
            "plan_id": str(data.plan_id),
            "external_id": data.external_id,
        },
    )

    webhook_service = WebhookService(db)
    webhook_service.send_webhook(
        webhook_type="subscription.created",
        object_type="subscription",
        object_id=subscription.id,  # type: ignore[arg-type]
        payload={"subscription_id": str(subscription.id)},
    )

    if isinstance(idempotency, IdempotencyResult):
        body = SubscriptionResponse.model_validate(subscription).model_dump(mode="json")
        record_idempotency_response(db, organization_id, idempotency.key, 201, body)

    return subscription


@router.put(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Update subscription",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Subscription not found"},
        422: {"description": "Validation error"},
    },
)
async def update_subscription(
    subscription_id: UUID,
    data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Subscription:
    """Update a subscription."""
    repo = SubscriptionRepository(db)
    old_subscription = repo.get_by_id(subscription_id, organization_id)
    if not old_subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    old_data = {
        k: str(v) if v is not None else None
        for k, v in data.model_dump(exclude_unset=True).items()
        if hasattr(old_subscription, k)
    }
    old_data = {k: str(getattr(old_subscription, k)) for k in old_data}

    subscription = repo.update(subscription_id, data, organization_id)
    if not subscription:  # pragma: no cover - race condition
        raise HTTPException(status_code=404, detail="Subscription not found")

    new_data = {
        k: str(getattr(subscription, k)) if getattr(subscription, k) is not None else None
        for k in data.model_dump(exclude_unset=True)
        if hasattr(subscription, k)
    }

    audit_service = AuditService(db)
    audit_service.log_update(
        resource_type="subscription",
        resource_id=subscription_id,
        organization_id=organization_id,
        actor_type="api_key",
        old_data=old_data,
        new_data=new_data,
    )

    return subscription


@router.delete(
    "/{subscription_id}",
    status_code=204,
    summary="Terminate subscription",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Subscription not found"},
    },
)
async def terminate_subscription(
    subscription_id: UUID,
    on_termination_action: TerminationAction = Query(
        default=TerminationAction.GENERATE_INVOICE,
        description="Termination action",
    ),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Terminate a subscription with configurable financial action."""
    lifecycle_service = SubscriptionLifecycleService(db)
    try:
        lifecycle_service.terminate_subscription(subscription_id, on_termination_action.value)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    audit_service = AuditService(db)
    audit_service.log_status_change(
        resource_type="subscription",
        resource_id=subscription_id,
        organization_id=organization_id,
        old_status="active",
        new_status="terminated",
        actor_type="api_key",
    )


@router.post(
    "/{subscription_id}/cancel",
    response_model=SubscriptionResponse,
    summary="Cancel subscription",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Subscription not found"},
    },
)
async def cancel_subscription(
    subscription_id: UUID,
    on_termination_action: TerminationAction = Query(
        default=TerminationAction.GENERATE_INVOICE,
        description="Cancellation action",
    ),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Subscription:
    """Cancel a subscription with configurable financial action."""
    lifecycle_service = SubscriptionLifecycleService(db)
    try:
        lifecycle_service.cancel_subscription(subscription_id, on_termination_action.value)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    audit_service = AuditService(db)
    audit_service.log_status_change(
        resource_type="subscription",
        resource_id=subscription_id,
        organization_id=organization_id,
        old_status="active",
        new_status="canceled",
        actor_type="api_key",
    )

    repo = SubscriptionRepository(db)
    subscription = repo.get_by_id(subscription_id, organization_id)
    return subscription  # type: ignore[return-value]


@router.get(
    "/{external_id}/entitlements",
    response_model=list[EntitlementResponse],
    summary="Get subscription entitlements",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Subscription not found"},
    },
)
async def get_subscription_entitlements(
    external_id: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Entitlement]:
    """Return all entitlements for the subscription's plan."""
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_external_id(external_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    entitlement_repo = EntitlementRepository(db)
    return entitlement_repo.get_by_plan_id(
        UUID(str(subscription.plan_id)), organization_id
    )
