"""Tax API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.tax import Tax
from app.repositories.applied_tax_repository import AppliedTaxRepository
from app.repositories.tax_repository import TaxRepository
from app.schemas.tax import (
    AppliedTaxResponse,
    ApplyTaxRequest,
    TaxCreate,
    TaxResponse,
    TaxUpdate,
)
from app.services.tax_service import TaxCalculationService

router = APIRouter()


@router.post(
    "/",
    response_model=TaxResponse,
    status_code=201,
    summary="Create tax",
    responses={
        401: {"description": "Unauthorized"},
        409: {"description": "Tax with this code already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_tax(
    data: TaxCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Tax:
    """Create a new tax."""
    repo = TaxRepository(db)
    if repo.get_by_code(data.code, organization_id):
        raise HTTPException(status_code=409, detail="Tax with this code already exists")
    return repo.create(data, organization_id)


@router.get(
    "/",
    response_model=list[TaxResponse],
    summary="List taxes",
    responses={401: {"description": "Unauthorized"}},
)
async def list_taxes(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Tax]:
    """List all taxes."""
    repo = TaxRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(organization_id, skip=skip, limit=limit)


@router.get(
    "/applied",
    response_model=list[AppliedTaxResponse],
    summary="List applied taxes",
    responses={401: {"description": "Unauthorized"}},
)
async def list_applied_taxes(
    taxable_type: str = Query(..., max_length=50),
    taxable_id: UUID = Query(...),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[AppliedTaxResponse]:
    """List applied taxes for a given entity."""
    repo = AppliedTaxRepository(db)
    applied = repo.get_by_taxable(taxable_type, taxable_id)
    return [AppliedTaxResponse.model_validate(a) for a in applied]


@router.post(
    "/apply",
    response_model=AppliedTaxResponse,
    status_code=201,
    summary="Apply tax to entity",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Tax not found"},
    },
)
async def apply_tax(
    data: ApplyTaxRequest,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> AppliedTaxResponse:
    """Apply a tax to an entity."""
    service = TaxCalculationService(db)
    try:
        applied = service.apply_tax_to_entity(
            tax_code=data.tax_code,
            taxable_type=data.taxable_type,
            taxable_id=data.taxable_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    return AppliedTaxResponse.model_validate(applied)


@router.delete(
    "/applied/{applied_tax_id}",
    status_code=204,
    summary="Remove applied tax",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Applied tax not found"},
    },
)
async def remove_applied_tax(
    applied_tax_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Remove an applied tax by ID."""
    repo = AppliedTaxRepository(db)
    if not repo.delete_by_id(applied_tax_id):
        raise HTTPException(status_code=404, detail="Applied tax not found")


@router.get(
    "/{code}",
    response_model=TaxResponse,
    summary="Get tax",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Tax not found"},
    },
)
async def get_tax(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Tax:
    """Get a tax by code."""
    repo = TaxRepository(db)
    tax = repo.get_by_code(code, organization_id)
    if not tax:
        raise HTTPException(status_code=404, detail="Tax not found")
    return tax


@router.put(
    "/{code}",
    response_model=TaxResponse,
    summary="Update tax",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Tax not found"},
        422: {"description": "Validation error"},
    },
)
async def update_tax(
    code: str,
    data: TaxUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Tax:
    """Update a tax by code."""
    repo = TaxRepository(db)
    tax = repo.update(code, data, organization_id)
    if not tax:
        raise HTTPException(status_code=404, detail="Tax not found")
    return tax


@router.delete(
    "/{code}",
    status_code=204,
    summary="Delete tax",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Tax not found"},
    },
)
async def delete_tax(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a tax by code."""
    repo = TaxRepository(db)
    if not repo.delete(code, organization_id):
        raise HTTPException(status_code=404, detail="Tax not found")
