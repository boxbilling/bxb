from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.subscription import Subscription, TerminationAction
from app.repositories.customer_repository import CustomerRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.subscription import SubscriptionCreate, SubscriptionResponse, SubscriptionUpdate
from app.services.subscription_lifecycle import SubscriptionLifecycleService
from app.services.webhook_service import WebhookService

router = APIRouter()


@router.get("/", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    skip: int = 0,
    limit: int = 100,
    customer_id: UUID | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Subscription]:
    """List all subscriptions with pagination. Optionally filter by customer_id."""
    repo = SubscriptionRepository(db)
    if customer_id:
        return repo.get_by_customer_id(customer_id, organization_id)
    return repo.get_all(organization_id, skip=skip, limit=limit)


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
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


@router.post("/", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Subscription:
    """Create a new subscription."""
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

    webhook_service = WebhookService(db)
    webhook_service.send_webhook(
        webhook_type="subscription.created",
        object_type="subscription",
        object_id=subscription.id,  # type: ignore[arg-type]
        payload={"subscription_id": str(subscription.id)},
    )

    return subscription


@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: UUID,
    data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Subscription:
    """Update a subscription."""
    repo = SubscriptionRepository(db)
    subscription = repo.update(subscription_id, data, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


@router.delete("/{subscription_id}", status_code=204)
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


@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
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

    repo = SubscriptionRepository(db)
    subscription = repo.get_by_id(subscription_id, organization_id)
    return subscription  # type: ignore[return-value]
