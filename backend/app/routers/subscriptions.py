from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.core.idempotency import IdempotencyResult, check_idempotency, record_idempotency_response
from app.models.entitlement import Entitlement
from app.models.invoice import Invoice
from app.models.payment import Payment
from app.models.subscription import Subscription, TerminationAction
from app.repositories.customer_repository import CustomerRepository
from app.repositories.entitlement_repository import EntitlementRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.entitlement import EntitlementResponse
from app.schemas.subscription import (
    ChangePlanPreviewRequest,
    ChangePlanPreviewResponse,
    PlanSummary,
    ProrationDetail,
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from app.schemas.subscription_lifecycle import LifecycleEvent, SubscriptionLifecycleResponse
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


INTERVAL_DAYS = {
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "yearly": 365,
}


@router.post(
    "/{subscription_id}/change_plan_preview",
    response_model=ChangePlanPreviewResponse,
    summary="Preview plan change with price comparison and proration",
    responses={
        400: {"description": "Invalid plan or same plan"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Subscription or plan not found"},
    },
)
async def change_plan_preview(
    subscription_id: UUID,
    data: ChangePlanPreviewRequest,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> ChangePlanPreviewResponse:
    """Preview a plan change showing price comparison and proration details."""
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(subscription_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    plan_repo = PlanRepository(db)
    current_plan = plan_repo.get_by_id(
        UUID(str(subscription.plan_id)), organization_id
    )
    if not current_plan:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Current plan not found")

    new_plan = plan_repo.get_by_id(data.new_plan_id, organization_id)
    if not new_plan:
        raise HTTPException(status_code=404, detail="New plan not found")

    if str(subscription.plan_id) == str(data.new_plan_id):
        raise HTTPException(
            status_code=400, detail="New plan must be different from current plan"
        )

    effective = data.effective_date or datetime.now(UTC)
    # Ensure effective is timezone-aware for comparison
    if effective.tzinfo is None:
        effective = effective.replace(tzinfo=UTC)

    # Calculate proration based on billing interval
    interval_str = str(current_plan.interval)
    total_days = INTERVAL_DAYS.get(interval_str, 30)

    # Determine period start based on started_at or created_at
    period_anchor = subscription.started_at or subscription.created_at
    if period_anchor:
        # Ensure timezone-aware for subtraction
        anchor = period_anchor if period_anchor.tzinfo else period_anchor.replace(tzinfo=UTC)
        elapsed = (effective - anchor).days % total_days
        days_remaining = max(total_days - elapsed, 0)
    else:  # pragma: no cover — created_at always set by DB
        days_remaining = total_days

    current_amount: int = current_plan.amount_cents  # type: ignore[assignment]
    new_amount: int = new_plan.amount_cents  # type: ignore[assignment]

    # Prorate: credit for unused portion of current plan, charge for new plan
    credit_cents = int(current_amount * days_remaining / total_days)
    charge_cents = int(new_amount * days_remaining / total_days)
    net_cents = charge_cents - credit_cents

    return ChangePlanPreviewResponse(
        current_plan=PlanSummary(
            id=current_plan.id,  # type: ignore[arg-type]
            name=str(current_plan.name),
            code=str(current_plan.code),
            interval=interval_str,
            amount_cents=current_amount,
            currency=str(current_plan.currency),
        ),
        new_plan=PlanSummary(
            id=new_plan.id,  # type: ignore[arg-type]
            name=str(new_plan.name),
            code=str(new_plan.code),
            interval=str(new_plan.interval),
            amount_cents=new_amount,
            currency=str(new_plan.currency),
        ),
        effective_date=effective,
        proration=ProrationDetail(
            days_remaining=days_remaining,
            total_days=total_days,
            current_plan_credit_cents=credit_cents,
            new_plan_charge_cents=charge_cents,
            net_amount_cents=net_cents,
        ),
    )


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


def _format_currency(amount: Decimal | float | int, currency: str = "USD") -> str:
    """Format a decimal amount as currency string."""
    val = float(amount) / 100
    return f"{currency} {val:,.2f}"


@router.get(
    "/{subscription_id}/lifecycle",
    response_model=SubscriptionLifecycleResponse,
    summary="Get subscription lifecycle timeline",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Subscription not found"},
    },
)
async def get_subscription_lifecycle(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> SubscriptionLifecycleResponse:
    """Get the full lifecycle timeline for a subscription."""
    repo = SubscriptionRepository(db)
    subscription = repo.get_by_id(subscription_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    events: list[LifecycleEvent] = []

    # 1. Subscription creation
    events.append(
        LifecycleEvent(
            timestamp=subscription.created_at,  # type: ignore[arg-type]
            event_type="subscription",
            title="Subscription created",
            description=f"External ID: {subscription.external_id}",
            status="created",
        )
    )

    # 2. Subscription started (if different from created)
    if subscription.started_at and subscription.started_at != subscription.created_at:
        events.append(
            LifecycleEvent(
                timestamp=subscription.started_at,  # type: ignore[arg-type]
                event_type="status_change",
                title="Subscription activated",
                status="active",
            )
        )

    # 3. Trial ended
    if subscription.trial_ended_at:
        events.append(
            LifecycleEvent(
                timestamp=subscription.trial_ended_at,  # type: ignore[arg-type]
                event_type="status_change",
                title="Trial period ended",
                description=f"Trial lasted {subscription.trial_period_days} days",
                status="active",
            )
        )

    # 4. Plan change (downgrade)
    if subscription.downgraded_at:
        events.append(
            LifecycleEvent(
                timestamp=subscription.downgraded_at,  # type: ignore[arg-type]
                event_type="status_change",
                title="Plan changed",
                description="Subscription plan was changed",
                status="changed",
            )
        )

    # 5. Canceled
    if subscription.canceled_at:
        events.append(
            LifecycleEvent(
                timestamp=subscription.canceled_at,  # type: ignore[arg-type]
                event_type="status_change",
                title="Subscription canceled",
                status="canceled",
            )
        )

    # 6. Terminated
    if subscription.ending_at:
        events.append(
            LifecycleEvent(
                timestamp=subscription.ending_at,  # type: ignore[arg-type]
                event_type="status_change",
                title="Subscription terminated",
                status="terminated",
            )
        )

    # 7. Invoices for this subscription
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.subscription_id == subscription_id,
            Invoice.organization_id == organization_id,
        )
        .order_by(Invoice.created_at.asc())
        .all()
    )
    for inv in invoices:
        total_str = _format_currency(
            float(inv.total),
            str(inv.currency),
        )
        events.append(
            LifecycleEvent(
                timestamp=inv.created_at,  # type: ignore[arg-type]
                event_type="invoice",
                title=f"Invoice {inv.invoice_number}",
                description=f"Total: {total_str}",
                status=str(inv.status),
                resource_id=str(inv.id),
                resource_type="invoice",
                metadata={"invoice_number": str(inv.invoice_number)},
            )
        )

    # 8. Payments related to this subscription's invoices
    invoice_ids = [inv.id for inv in invoices]
    if invoice_ids:
        payments = (
            db.query(Payment)
            .filter(
                Payment.invoice_id.in_(invoice_ids),
                Payment.organization_id == organization_id,
            )
            .order_by(Payment.created_at.asc())
            .all()
        )
        # Build invoice number lookup
        inv_number_map = {str(inv.id): str(inv.invoice_number) for inv in invoices}
        for pmt in payments:
            amount_str = _format_currency(
                float(pmt.amount),
                str(pmt.currency),
            )
            inv_num = inv_number_map.get(str(pmt.invoice_id), "")
            events.append(
                LifecycleEvent(
                    timestamp=pmt.created_at,  # type: ignore[arg-type]
                    event_type="payment",
                    title=f"Payment {pmt.status}",
                    description=f"Amount: {amount_str}" + (f" for {inv_num}" if inv_num else ""),
                    status=str(pmt.status),
                    resource_id=str(pmt.id),
                    resource_type="payment",
                    metadata={"provider": str(pmt.provider)},
                )
            )

    # Sort by timestamp ascending (chronological order)
    events.sort(key=lambda e: e.timestamp)

    return SubscriptionLifecycleResponse(events=events)


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
