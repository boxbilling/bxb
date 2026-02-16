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
    TaxApplicationCountsResponse,
    TaxAppliedEntitiesResponse,
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
    order_by: str | None = Query(default=None),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Tax]:
    """List all taxes."""
    repo = TaxRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(organization_id, skip=skip, limit=limit, order_by=order_by)


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
    tax_repo = TaxRepository(db)
    applied = repo.get_by_taxable(taxable_type, taxable_id)
    results = []
    for a in applied:
        response = AppliedTaxResponse.model_validate(a)
        tax = tax_repo.get_by_id(a.tax_id)  # type: ignore[arg-type]
        response.tax_name = str(tax.name) if tax else None
        response.tax_code = str(tax.code) if tax else None
        results.append(response)
    return results


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
    response = AppliedTaxResponse.model_validate(applied)
    tax_repo = TaxRepository(db)
    tax = tax_repo.get_by_id(applied.tax_id)  # type: ignore[arg-type]
    response.tax_name = str(tax.name) if tax else None
    response.tax_code = str(tax.code) if tax else None
    return response


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
    "/application_counts",
    response_model=TaxApplicationCountsResponse,
    summary="Get tax application counts",
    responses={401: {"description": "Unauthorized"}},
)
async def get_application_counts(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> TaxApplicationCountsResponse:
    """Get the count of applied tax records per tax."""
    repo = AppliedTaxRepository(db)
    counts = repo.application_counts()
    return TaxApplicationCountsResponse(counts=counts)


@router.get(
    "/{code}/applied_entities",
    response_model=TaxAppliedEntitiesResponse,
    summary="Get entities a tax is applied to",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Tax not found"},
    },
)
async def get_applied_entities(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> TaxAppliedEntitiesResponse:
    """Get all entities a tax is applied to."""
    tax_repo = TaxRepository(db)
    tax = tax_repo.get_by_code(code, organization_id)
    if not tax:
        raise HTTPException(status_code=404, detail="Tax not found")
    applied_repo = AppliedTaxRepository(db)
    applied = applied_repo.get_by_tax_id(tax.id)  # type: ignore[arg-type]
    entities: list[dict[str, str | None]] = [
        {
            "taxable_type": str(a.taxable_type),
            "taxable_id": str(a.taxable_id),
        }
        for a in applied
    ]
    return TaxAppliedEntitiesResponse(
        tax_id=tax.id,  # type: ignore[arg-type]
        tax_code=tax.code,  # type: ignore[arg-type]
        entities=entities,
    )


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
