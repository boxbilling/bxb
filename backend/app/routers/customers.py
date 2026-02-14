from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.applied_coupon import AppliedCoupon
from app.models.customer import Customer
from app.repositories.applied_coupon_repository import AppliedCouponRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.coupon import AppliedCouponResponse
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter()


@router.get(
    "/",
    response_model=list[CustomerResponse],
    summary="List customers",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_customers(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Customer]:
    """List all customers with pagination."""
    repo = CustomerRepository(db)
    return repo.get_all(organization_id, skip=skip, limit=limit)


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
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Customer:
    """Create a new customer."""
    repo = CustomerRepository(db)
    if repo.external_id_exists(data.external_id, organization_id):
        raise HTTPException(status_code=409, detail="Customer with this external_id already exists")
    return repo.create(data, organization_id)


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
