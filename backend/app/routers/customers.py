from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.core.idempotency import IdempotencyResult, check_idempotency, record_idempotency_response
from app.models.applied_coupon import AppliedCoupon
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.repositories.applied_coupon_repository import AppliedCouponRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.coupon import AppliedCouponResponse
from app.schemas.customer import (
    CustomerCreate,
    CustomerHealthResponse,
    CustomerHealthStatus,
    CustomerResponse,
    CustomerUpdate,
)
from app.schemas.portal import PortalUrlResponse
from app.schemas.usage import CurrentUsageResponse
from app.services.portal_service import PortalService
from app.services.subscription_dates import SubscriptionDatesService
from app.services.usage_query_service import UsageQueryService

router = APIRouter()


@router.get(
    "/",
    response_model=list[CustomerResponse],
    summary="List customers",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_customers(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Customer]:
    """List all customers with pagination."""
    repo = CustomerRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(organization_id, skip=skip, limit=limit)


def _get_customer_by_external_id(
    external_id: str,
    db: Session,
    organization_id: UUID,
) -> Customer:
    """Look up a customer by external_id, raising 404 if not found."""
    repo = CustomerRepository(db)
    customer = repo.get_by_external_id(external_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def _get_verified_subscription(
    subscription_id: UUID,
    customer_id: UUID,
    db: Session,
    organization_id: UUID,
) -> Subscription:
    """Look up subscription and verify it belongs to the customer."""
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_id(subscription_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if UUID(str(subscription.customer_id)) != UUID(str(customer_id)):
        raise HTTPException(
            status_code=404, detail="Subscription does not belong to this customer"
        )
    return subscription


@router.get(
    "/{external_id}/current_usage",
    response_model=CurrentUsageResponse,
    summary="Get customer current usage",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer or subscription not found"},
    },
)
async def get_current_usage(
    external_id: str,
    subscription_id: UUID = Query(...),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CurrentUsageResponse:
    """Get current usage for a customer's subscription."""
    customer = _get_customer_by_external_id(external_id, db, organization_id)
    _get_verified_subscription(subscription_id, UUID(str(customer.id)), db, organization_id)
    service = UsageQueryService(db)
    return service.get_current_usage(
        subscription_id=subscription_id,
        external_customer_id=str(customer.external_id),
    )


@router.get(
    "/{external_id}/projected_usage",
    response_model=CurrentUsageResponse,
    summary="Get customer projected usage",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer or subscription not found"},
    },
)
async def get_projected_usage(
    external_id: str,
    subscription_id: UUID = Query(...),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CurrentUsageResponse:
    """Get projected usage for a customer's subscription."""
    customer = _get_customer_by_external_id(external_id, db, organization_id)
    _get_verified_subscription(subscription_id, UUID(str(customer.id)), db, organization_id)
    service = UsageQueryService(db)
    return service.get_projected_usage(
        subscription_id=subscription_id,
        external_customer_id=str(customer.external_id),
    )


@router.get(
    "/{external_id}/past_usage",
    response_model=list[CurrentUsageResponse],
    summary="Get customer past usage",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer or subscription not found"},
    },
)
async def get_past_usage(
    external_id: str,
    external_subscription_id: str = Query(...),
    periods_count: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[CurrentUsageResponse]:
    """Get past usage for completed billing periods."""
    customer = _get_customer_by_external_id(external_id, db, organization_id)
    sub_repo = SubscriptionRepository(db)
    subscription = sub_repo.get_by_external_id(external_subscription_id, organization_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if UUID(str(subscription.customer_id)) != UUID(str(customer.id)):
        raise HTTPException(
            status_code=404, detail="Subscription does not belong to this customer"
        )

    plan = db.query(Plan).filter(Plan.id == subscription.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    interval = str(plan.interval)
    dates_service = SubscriptionDatesService()
    current_start, _ = dates_service.calculate_billing_period(subscription, interval)

    results: list[CurrentUsageResponse] = []
    service = UsageQueryService(db)
    period_end = current_start
    for _ in range(periods_count):
        period_start, period_end_calc = dates_service.calculate_billing_period(
            subscription, interval, reference_date=period_end - timedelta(seconds=1),
        )
        results.append(
            service._compute_usage_for_period(
                subscription=subscription,
                external_customer_id=str(customer.external_id),
                period_start=period_start,
                period_end=period_end_calc,
            )
        )
        period_end = period_start

    return results


@router.get(
    "/{external_id}/portal_url",
    response_model=PortalUrlResponse,
    summary="Generate customer portal URL",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer not found"},
    },
)
async def generate_portal_url(
    external_id: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> PortalUrlResponse:
    """Generate a portal URL for a customer to access their self-service portal."""
    customer = _get_customer_by_external_id(external_id, db, organization_id)
    service = PortalService(db)
    return service.generate_portal_url(UUID(str(customer.id)), organization_id)


@router.get(
    "/{customer_id}/health",
    response_model=CustomerHealthResponse,
    summary="Get customer health indicator",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer not found"},
    },
)
async def get_customer_health(
    customer_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CustomerHealthResponse:
    """Get customer health indicator based on payment history."""
    repo = CustomerRepository(db)
    customer = repo.get_by_id(customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    now = datetime.now()

    # Query invoices for this customer
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.customer_id == customer_id,
            Invoice.organization_id == organization_id,
            Invoice.status != InvoiceStatus.DRAFT.value,
            Invoice.status != InvoiceStatus.VOIDED.value,
        )
        .all()
    )
    total_invoices = len(invoices)
    paid_invoices = sum(1 for i in invoices if i.status == InvoiceStatus.PAID.value)
    overdue_invoices = sum(
        1
        for i in invoices
        if i.status == InvoiceStatus.FINALIZED.value
        and i.due_date is not None
        and i.due_date < now
    )
    overdue_amount = sum(
        float(i.total)
        for i in invoices
        if i.status == InvoiceStatus.FINALIZED.value
        and i.due_date is not None
        and i.due_date < now
    )

    # Query payments for this customer
    payments = (
        db.query(Payment)
        .filter(
            Payment.customer_id == customer_id,
            Payment.organization_id == organization_id,
        )
        .all()
    )
    total_payments = len(payments)
    failed_payments = sum(
        1 for p in payments if p.status == PaymentStatus.FAILED.value
    )

    # Determine health status
    if overdue_invoices > 0 or failed_payments >= 2:
        status = CustomerHealthStatus.CRITICAL
    elif (
        (total_invoices > 0 and paid_invoices < total_invoices and overdue_invoices == 0)
        or failed_payments == 1
    ):
        status = CustomerHealthStatus.WARNING
    else:
        status = CustomerHealthStatus.GOOD

    return CustomerHealthResponse(
        status=status,
        total_invoices=total_invoices,
        paid_invoices=paid_invoices,
        overdue_invoices=overdue_invoices,
        total_payments=total_payments,
        failed_payments=failed_payments,
        overdue_amount=overdue_amount,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer not found"},
    },
)
async def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Customer:
    """Get a customer by ID."""
    repo = CustomerRepository(db)
    customer = repo.get_by_id(customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=201,
    summary="Create customer",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        409: {"description": "Customer with this external_id already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_customer(
    data: CustomerCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Customer | JSONResponse:
    """Create a new customer."""
    idempotency = check_idempotency(request, db, organization_id)
    if isinstance(idempotency, JSONResponse):
        return idempotency

    repo = CustomerRepository(db)
    if repo.external_id_exists(data.external_id, organization_id):
        raise HTTPException(status_code=409, detail="Customer with this external_id already exists")
    customer = repo.create(data, organization_id)

    if isinstance(idempotency, IdempotencyResult):
        body = CustomerResponse.model_validate(customer).model_dump(mode="json")
        record_idempotency_response(db, organization_id, idempotency.key, 201, body)

    return customer


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer not found"},
        422: {"description": "Validation error"},
    },
)
async def update_customer(
    customer_id: UUID,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Customer:
    """Update a customer."""
    repo = CustomerRepository(db)
    customer = repo.update(customer_id, data, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.delete(
    "/{customer_id}",
    status_code=204,
    summary="Delete customer",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer not found"},
    },
)
async def delete_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a customer."""
    repo = CustomerRepository(db)
    if not repo.delete(customer_id, organization_id):
        raise HTTPException(status_code=404, detail="Customer not found")


@router.get(
    "/{customer_id}/applied_coupons",
    response_model=list[AppliedCouponResponse],
    summary="List customer applied coupons",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Customer not found"},
    },
)
async def list_applied_coupons(
    customer_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[AppliedCoupon]:
    """List applied coupons for a customer."""
    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    repo = AppliedCouponRepository(db)
    return repo.get_all(skip=skip, limit=limit, customer_id=customer_id)
