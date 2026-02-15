"""AddOn and AppliedAddOn API endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.add_on import AddOn
from app.models.applied_add_on import AppliedAddOn
from app.repositories.add_on_repository import AddOnRepository
from app.repositories.applied_add_on_repository import AppliedAddOnRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.add_on import (
    AddOnCreate,
    AddOnResponse,
    AddOnUpdate,
    AppliedAddOnDetailResponse,
    AppliedAddOnResponse,
    ApplyAddOnRequest,
)

router = APIRouter()


@router.post(
    "/",
    response_model=AddOnResponse,
    status_code=201,
    summary="Create add-on",
    responses={
        401: {"description": "Unauthorized"},
        409: {"description": "Add-on with this code already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_add_on(
    data: AddOnCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> AddOn:
    """Create a new add-on."""
    repo = AddOnRepository(db)
    if repo.get_by_code(data.code, organization_id):
        raise HTTPException(status_code=409, detail="Add-on with this code already exists")
    return repo.create(data, organization_id)


@router.get(
    "/",
    response_model=list[AddOnResponse],
    summary="List add-ons",
    responses={401: {"description": "Unauthorized"}},
)
async def list_add_ons(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[AddOn]:
    """List add-ons with pagination."""
    repo = AddOnRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(organization_id, skip=skip, limit=limit)


@router.get(
    "/application_counts",
    response_model=dict[str, int],
    summary="Get application counts per add-on",
    responses={401: {"description": "Unauthorized"}},
)
async def get_application_counts(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> dict[str, int]:
    """Return a mapping of add_on_id to application count."""
    repo = AppliedAddOnRepository(db)
    return repo.application_counts()


@router.get(
    "/{code}/applications",
    response_model=list[AppliedAddOnDetailResponse],
    summary="Get application history for an add-on",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Add-on not found"},
    },
)
async def get_add_on_applications(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[dict[str, Any]]:
    """Get all applications of an add-on with customer names."""
    add_on_repo = AddOnRepository(db)
    add_on = add_on_repo.get_by_code(code, organization_id)
    if not add_on:
        raise HTTPException(status_code=404, detail="Add-on not found")

    applied_repo = AppliedAddOnRepository(db)
    applications = applied_repo.get_by_add_on_id(add_on.id)  # type: ignore[arg-type]

    customer_repo = CustomerRepository(db)
    result = []
    for app in applications:
        customer = customer_repo.get_by_id(app.customer_id)  # type: ignore[arg-type]
        result.append({
            "id": app.id,
            "add_on_id": app.add_on_id,
            "customer_id": app.customer_id,
            "customer_name": customer.name if customer else "Unknown",
            "amount_cents": app.amount_cents,
            "amount_currency": app.amount_currency,
            "created_at": app.created_at,
        })
    return result


@router.get(
    "/{code}",
    response_model=AddOnResponse,
    summary="Get add-on",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Add-on not found"},
    },
)
async def get_add_on(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> AddOn:
    """Get an add-on by code."""
    repo = AddOnRepository(db)
    add_on = repo.get_by_code(code, organization_id)
    if not add_on:
        raise HTTPException(status_code=404, detail="Add-on not found")
    return add_on


@router.put(
    "/{code}",
    response_model=AddOnResponse,
    summary="Update add-on",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Add-on not found"},
        422: {"description": "Validation error"},
    },
)
async def update_add_on(
    code: str,
    data: AddOnUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> AddOn:
    """Update an add-on by code."""
    repo = AddOnRepository(db)
    add_on = repo.update(code, data, organization_id)
    if not add_on:
        raise HTTPException(status_code=404, detail="Add-on not found")
    return add_on


@router.delete(
    "/{code}",
    status_code=204,
    summary="Delete add-on",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Add-on not found"},
    },
)
async def delete_add_on(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete an add-on by code."""
    repo = AddOnRepository(db)
    if not repo.delete(code, organization_id):
        raise HTTPException(status_code=404, detail="Add-on not found")


@router.post(
    "/apply",
    response_model=AppliedAddOnResponse,
    status_code=201,
    summary="Apply add-on to customer",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Add-on or customer not found"},
    },
)
async def apply_add_on(
    data: ApplyAddOnRequest,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> AppliedAddOn:
    """Apply an add-on to a customer."""
    add_on_repo = AddOnRepository(db)
    add_on = add_on_repo.get_by_code(data.add_on_code, organization_id)
    if not add_on:
        raise HTTPException(status_code=404, detail="Add-on not found")

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(data.customer_id, organization_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    applied_repo = AppliedAddOnRepository(db)
    return applied_repo.create(
        add_on_id=add_on.id,  # type: ignore[arg-type]
        customer_id=data.customer_id,
        amount_cents=data.amount_cents if data.amount_cents is not None else add_on.amount_cents,  # type: ignore[arg-type]
        amount_currency=(
            data.amount_currency if data.amount_currency is not None else add_on.amount_currency  # type: ignore[arg-type]
        ),
    )
