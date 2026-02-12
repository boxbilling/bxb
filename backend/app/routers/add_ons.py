"""AddOn and AppliedAddOn API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

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
    AppliedAddOnResponse,
    ApplyAddOnRequest,
)

router = APIRouter()


@router.post("/", response_model=AddOnResponse, status_code=201)
async def create_add_on(
    data: AddOnCreate,
    db: Session = Depends(get_db),
) -> AddOn:
    """Create a new add-on."""
    repo = AddOnRepository(db)
    if repo.get_by_code(data.code):
        raise HTTPException(status_code=409, detail="Add-on with this code already exists")
    return repo.create(data)


@router.get("/", response_model=list[AddOnResponse])
async def list_add_ons(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[AddOn]:
    """List add-ons with pagination."""
    repo = AddOnRepository(db)
    return repo.get_all(skip=skip, limit=limit)


@router.get("/{code}", response_model=AddOnResponse)
async def get_add_on(
    code: str,
    db: Session = Depends(get_db),
) -> AddOn:
    """Get an add-on by code."""
    repo = AddOnRepository(db)
    add_on = repo.get_by_code(code)
    if not add_on:
        raise HTTPException(status_code=404, detail="Add-on not found")
    return add_on


@router.put("/{code}", response_model=AddOnResponse)
async def update_add_on(
    code: str,
    data: AddOnUpdate,
    db: Session = Depends(get_db),
) -> AddOn:
    """Update an add-on by code."""
    repo = AddOnRepository(db)
    add_on = repo.update(code, data)
    if not add_on:
        raise HTTPException(status_code=404, detail="Add-on not found")
    return add_on


@router.delete("/{code}", status_code=204)
async def delete_add_on(
    code: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete an add-on by code."""
    repo = AddOnRepository(db)
    if not repo.delete(code):
        raise HTTPException(status_code=404, detail="Add-on not found")


@router.post("/apply", response_model=AppliedAddOnResponse, status_code=201)
async def apply_add_on(
    data: ApplyAddOnRequest,
    db: Session = Depends(get_db),
) -> AppliedAddOn:
    """Apply an add-on to a customer."""
    add_on_repo = AddOnRepository(db)
    add_on = add_on_repo.get_by_code(data.add_on_code)
    if not add_on:
        raise HTTPException(status_code=404, detail="Add-on not found")

    customer_repo = CustomerRepository(db)
    customer = customer_repo.get_by_id(data.customer_id)
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
