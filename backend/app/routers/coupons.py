"""Coupon and AppliedCoupon API endpoints."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.applied_coupon import AppliedCoupon, AppliedCouponStatus
from app.models.coupon import Coupon, CouponStatus
from app.repositories.applied_coupon_repository import AppliedCouponRepository
from app.repositories.coupon_repository import CouponRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.coupon import (
    AppliedCouponResponse,
    ApplyCouponRequest,
    CouponAnalyticsResponse,
    CouponCreate,
    CouponResponse,
    CouponUpdate,
)

router = APIRouter()


@router.post(
    "/",
    response_model=CouponResponse,
    status_code=201,
    summary="Create coupon",
    responses={
        401: {"description": "Unauthorized"},
        409: {"description": "Coupon with this code already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_coupon(
    data: CouponCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Coupon:
    """Create a new coupon."""
    repo = CouponRepository(db)
    if repo.get_by_code(data.code, organization_id):
        raise HTTPException(status_code=409, detail="Coupon with this code already exists")
    return repo.create(data, organization_id)


@router.get(
    "/",
    response_model=list[CouponResponse],
    summary="List coupons",
    responses={401: {"description": "Unauthorized"}},
)
async def list_coupons(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    order_by: str | None = Query(default=None),
    status: CouponStatus | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Coupon]:
    """List coupons with optional status filter."""
    repo = CouponRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(organization_id, skip=skip, limit=limit, order_by=order_by, status=status)


@router.get(
    "/{code}",
    response_model=CouponResponse,
    summary="Get coupon",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Coupon not found"},
    },
)
async def get_coupon(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Coupon:
    """Get a coupon by code."""
    repo = CouponRepository(db)
    coupon = repo.get_by_code(code, organization_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return coupon


@router.put(
    "/{code}",
    response_model=CouponResponse,
    summary="Update coupon",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Coupon not found"},
        422: {"description": "Validation error"},
    },
)
async def update_coupon(
    code: str,
    data: CouponUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Coupon:
    """Update a coupon by code."""
    repo = CouponRepository(db)
    coupon = repo.update(code, data, organization_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return coupon


@router.delete(
    "/{code}",
    status_code=204,
    summary="Terminate coupon",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Coupon not found"},
    },
)
async def terminate_coupon(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Terminate a coupon by code."""
    repo = CouponRepository(db)
    coupon = repo.terminate(code, organization_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")


@router.post(
    "/apply",
    response_model=AppliedCouponResponse,
    status_code=201,
    summary="Apply coupon to customer",
    responses={
        400: {"description": "Coupon is not active"},
        401: {"description": "Unauthorized"},
        404: {"description": "Coupon or customer not found"},
        409: {"description": "Coupon already applied to this customer"},
    },
)
async def apply_coupon(
    data: ApplyCouponRequest,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> AppliedCoupon:
    """Apply a coupon to a customer."""
    coupon_repo = CouponRepository(db)
    coupon = coupon_repo.get_by_code(data.coupon_code, organization_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    if coupon.status != CouponStatus.ACTIVE.value:
        raise HTTPException(status_code=400, detail="Coupon is not active")

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(data.customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    applied_repo = AppliedCouponRepository(db)
    if not coupon.reusable:
        existing = applied_repo.get_by_coupon_and_customer(
            coupon.id,  # type: ignore[arg-type]
            data.customer_id,
        )
        if existing:
            raise HTTPException(status_code=409, detail="Coupon already applied to this customer")

    return applied_repo.create(
        coupon_id=coupon.id,  # type: ignore[arg-type]
        customer_id=data.customer_id,
        amount_cents=data.amount_cents if data.amount_cents is not None else coupon.amount_cents,  # type: ignore[arg-type]
        amount_currency=(
            data.amount_currency if data.amount_currency is not None else coupon.amount_currency  # type: ignore[arg-type]
        ),
        percentage_rate=(
            data.percentage_rate  # type: ignore[arg-type]
            if data.percentage_rate is not None
            else coupon.percentage_rate
        ),
        frequency=str(coupon.frequency),
        frequency_duration=coupon.frequency_duration,  # type: ignore[arg-type]
    )


@router.delete(
    "/applied/{applied_coupon_id}",
    status_code=204,
    summary="Remove applied coupon",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Applied coupon not found"},
    },
)
async def remove_applied_coupon(
    applied_coupon_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Remove (terminate) an applied coupon from a customer."""
    applied_repo = AppliedCouponRepository(db)
    applied_coupon = applied_repo.get_by_id(applied_coupon_id)
    if not applied_coupon:
        raise HTTPException(status_code=404, detail="Applied coupon not found")
    applied_repo.terminate(applied_coupon_id)


@router.get(
    "/{code}/analytics",
    response_model=CouponAnalyticsResponse,
    summary="Get coupon analytics",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Coupon not found"},
    },
)
async def get_coupon_analytics(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CouponAnalyticsResponse:
    """Get usage analytics for a coupon."""
    coupon_repo = CouponRepository(db)
    coupon = coupon_repo.get_by_code(code, organization_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    applied_repo = AppliedCouponRepository(db)
    all_applied = applied_repo.get_all_by_coupon_id(coupon.id)  # type: ignore[arg-type]

    active_count = sum(1 for a in all_applied if a.status == AppliedCouponStatus.ACTIVE.value)
    terminated_count = sum(
        1 for a in all_applied if a.status == AppliedCouponStatus.TERMINATED.value
    )

    # Calculate remaining uses across all active recurring applications
    remaining_uses: int | None = None
    has_recurring = False
    total_remaining = 0
    for a in all_applied:
        is_active = a.status == AppliedCouponStatus.ACTIVE.value
        if is_active and a.frequency_duration_remaining is not None:
            has_recurring = True
            total_remaining += a.frequency_duration_remaining  # type: ignore[assignment]
    if has_recurring:
        remaining_uses = total_remaining

    # Approximate total discount by summing applied coupon amounts * times consumed
    total_discount_cents = Decimal("0")
    for a in all_applied:
        if a.status == AppliedCouponStatus.TERMINATED.value and a.frequency == "once":
            # Once coupons: consumed exactly once
            total_discount_cents += Decimal(str(a.amount_cents or 0))
        elif a.frequency == "recurring" and a.frequency_duration is not None:
            # Recurring: times used = duration - remaining
            remaining = a.frequency_duration_remaining or 0
            times_used = a.frequency_duration - remaining
            total_discount_cents += Decimal(str(a.amount_cents or 0)) * times_used  # type: ignore[assignment]

    return CouponAnalyticsResponse(
        times_applied=len(all_applied),
        active_applications=active_count,
        terminated_applications=terminated_count,
        total_discount_cents=total_discount_cents,
        remaining_uses=remaining_uses,
    )


@router.post(
    "/{code}/duplicate",
    response_model=CouponResponse,
    status_code=201,
    summary="Duplicate coupon",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Coupon not found"},
        409: {"description": "Duplicate code already exists"},
    },
)
async def duplicate_coupon(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Coupon:
    """Create a copy of an existing coupon with a new code."""
    repo = CouponRepository(db)
    coupon = repo.get_by_code(code, organization_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    new_code = f"{coupon.code}_copy"
    if repo.get_by_code(new_code, organization_id):
        raise HTTPException(
            status_code=409, detail=f"Coupon with code '{new_code}' already exists"
        )

    create_data = CouponCreate(
        code=new_code,
        name=f"{coupon.name} (Copy)",
        description=coupon.description,  # type: ignore[arg-type]
        coupon_type=coupon.coupon_type,  # type: ignore[arg-type]
        amount_cents=coupon.amount_cents,  # type: ignore[arg-type]
        amount_currency=coupon.amount_currency,  # type: ignore[arg-type]
        percentage_rate=coupon.percentage_rate,  # type: ignore[arg-type]
        frequency=coupon.frequency,  # type: ignore[arg-type]
        frequency_duration=coupon.frequency_duration,  # type: ignore[arg-type]
        reusable=coupon.reusable,  # type: ignore[arg-type]
        expiration=coupon.expiration,  # type: ignore[arg-type]
        expiration_at=coupon.expiration_at,  # type: ignore[arg-type]
    )
    return repo.create(create_data, organization_id)
