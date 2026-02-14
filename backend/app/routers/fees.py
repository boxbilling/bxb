"""Fee API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.fee import Fee, FeePaymentStatus, FeeType
from app.repositories.fee_repository import FeeRepository
from app.schemas.fee import FeeResponse, FeeUpdate

router = APIRouter()


@router.get(
    "/",
    response_model=list[FeeResponse],
    summary="List fees",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_fees(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    invoice_id: UUID | None = None,
    customer_id: UUID | None = None,
    subscription_id: UUID | None = None,
    fee_type: FeeType | None = None,
    payment_status: FeePaymentStatus | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Fee]:
    """List fees with optional filters."""
    repo = FeeRepository(db)
    return repo.get_all(
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        invoice_id=invoice_id,
        customer_id=customer_id,
        subscription_id=subscription_id,
        fee_type=fee_type,
        payment_status=payment_status,
    )


@router.get(
    "/{fee_id}",
    response_model=FeeResponse,
    summary="Get fee",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Fee not found"},
    },
)
async def get_fee(
    fee_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Fee:
    """Get a fee by ID."""
    repo = FeeRepository(db)
    fee = repo.get_by_id(fee_id, organization_id)
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    return fee


@router.put(
    "/{fee_id}",
    response_model=FeeResponse,
    summary="Update fee",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Fee not found"},
        422: {"description": "Validation error"},
    },
)
async def update_fee(
    fee_id: UUID,
    data: FeeUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Fee:
    """Update a fee."""
    repo = FeeRepository(db)
    fee = repo.update(fee_id, data)
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    return fee
