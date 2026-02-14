"""Coupon and AppliedCoupon API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.applied_coupon import AppliedCoupon
from app.models.coupon import Coupon, CouponStatus
from app.repositories.applied_coupon_repository import AppliedCouponRepository
from app.repositories.coupon_repository import CouponRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.coupon import (
    AppliedCouponResponse,
    ApplyCouponRequest,
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
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    status: CouponStatus | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Coupon]:
    """List coupons with optional status filter."""
    repo = CouponRepository(db)
    return repo.get_all(organization_id, skip=skip, limit=limit, status=status)


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
