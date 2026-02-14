from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.repositories.customer_repository import CustomerRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_threshold_repository import UsageThresholdRepository
from app.schemas.usage_threshold import (
    CurrentUsageResponse,
    UsageThresholdCreate,
    UsageThresholdCreateAPI,
    UsageThresholdResponse,
)
from app.services.subscription_dates import SubscriptionDatesService
from app.services.usage_threshold_service import UsageThresholdService

router = APIRouter()


@router.post(
    "/plans/{plan_code}/usage_thresholds",
    response_model=UsageThresholdResponse,
    status_code=201,
)
async def create_plan_usage_threshold(
    plan_code: str,
    data: UsageThresholdCreateAPI,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> UsageThresholdResponse:
    """Add a usage threshold to a plan."""
    plan_repo = PlanRepository(db)
    plan = plan_repo.get_by_code(plan_code, organization_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    create_data = UsageThresholdCreate(
        plan_id=plan.id,  # type: ignore[arg-type]
        amount_cents=data.amount_cents,
        currency=data.currency,
        recurring=data.recurring,
        threshold_display_name=data.threshold_display_name,
    )
    repo = UsageThresholdRepository(db)
    threshold = repo.create(create_data, organization_id)
    return UsageThresholdResponse.model_validate(threshold)


@router.get(
    "/plans/{plan_code}/usage_thresholds",
    response_model=list[UsageThresholdResponse],
)
async def list_plan_usage_thresholds(
    plan_code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[UsageThresholdResponse]:
    """List all usage thresholds for a plan."""
    plan_repo = PlanRepository(db)
    plan = plan_repo.get_by_code(plan_code, organization_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    repo = UsageThresholdRepository(db)
    thresholds = repo.get_by_plan_id(plan.id)  # type: ignore[arg-type]
    return [UsageThresholdResponse.model_validate(t) for t in thresholds]


@router.post(
    "/subscriptions/{subscription_id}/usage_thresholds",
    response_model=UsageThresholdResponse,
    status_code=201,
)
async def create_subscription_usage_threshold(
    subscription_id: UUID,
    data: UsageThresholdCreateAPI,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> UsageThresholdResponse:
    """Add a usage threshold to a subscription."""
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(subscription_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    create_data = UsageThresholdCreate(
        subscription_id=subscription_id,
        amount_cents=data.amount_cents,
        currency=data.currency,
        recurring=data.recurring,
        threshold_display_name=data.threshold_display_name,
    )
    repo = UsageThresholdRepository(db)
    threshold = repo.create(create_data, organization_id)
    return UsageThresholdResponse.model_validate(threshold)


@router.get(
    "/subscriptions/{subscription_id}/usage_thresholds",
    response_model=list[UsageThresholdResponse],
)
async def list_subscription_usage_thresholds(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[UsageThresholdResponse]:
    """List all usage thresholds for a subscription."""
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(subscription_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    repo = UsageThresholdRepository(db)
    thresholds = repo.get_by_subscription_id(subscription_id)
    return [UsageThresholdResponse.model_validate(t) for t in thresholds]


@router.get(
    "/subscriptions/{subscription_id}/current_usage",
    response_model=CurrentUsageResponse,
)
async def get_current_usage(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CurrentUsageResponse:
    """Get current period usage amount for a subscription."""
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(subscription_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    plan_repo = PlanRepository(db)
    plan = plan_repo.get_by_id(UUID(str(subscription.plan_id)))
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(UUID(str(subscription.customer_id)))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    dates_service = SubscriptionDatesService()
    now = datetime.now(UTC)
    period_start, period_end = dates_service.calculate_billing_period(
        subscription, str(plan.interval), now
    )

    service = UsageThresholdService(db)
    current_usage = service.get_current_usage_amount(
        subscription_id=subscription_id,
        billing_period_start=period_start,
        billing_period_end=period_end,
        external_customer_id=str(customer.external_id),
    )

    return CurrentUsageResponse(
        subscription_id=subscription_id,
        current_usage_amount_cents=current_usage,
        billing_period_start=period_start,
        billing_period_end=period_end,
    )


@router.delete("/usage_thresholds/{threshold_id}", status_code=204)
async def delete_usage_threshold(
    threshold_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Remove a usage threshold."""
    repo = UsageThresholdRepository(db)
    if not repo.delete(threshold_id, organization_id):
        raise HTTPException(status_code=404, detail="Usage threshold not found")
