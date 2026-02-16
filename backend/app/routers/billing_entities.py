from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.core.idempotency import IdempotencyResult, check_idempotency, record_idempotency_response
from app.models.billing_entity import BillingEntity
from app.models.invoice import Invoice
from app.repositories.billing_entity_repository import BillingEntityRepository
from app.schemas.billing_entity import (
    BillingEntityCreate,
    BillingEntityResponse,
    BillingEntityUpdate,
)

router = APIRouter()


@router.get(
    "/",
    response_model=list[BillingEntityResponse],
    summary="List billing entities",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_billing_entities(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    order_by: str | None = Query(default=None),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[BillingEntity]:
    """List all billing entities with pagination."""
    repo = BillingEntityRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(organization_id, skip=skip, limit=limit, order_by=order_by)


@router.get(
    "/customer_counts",
    response_model=dict[str, int],
    summary="Get customer counts per billing entity",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_customer_counts(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> dict[str, int]:
    """Return a mapping of billing entity ID to associated customer count."""
    repo = BillingEntityRepository(db)
    return repo.customer_counts(organization_id)


@router.get(
    "/{code}",
    response_model=BillingEntityResponse,
    summary="Get billing entity by code",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Billing entity not found"},
    },
)
async def get_billing_entity(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> BillingEntity:
    """Get a billing entity by its code."""
    repo = BillingEntityRepository(db)
    entity = repo.get_by_code(code, organization_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Billing entity not found")
    return entity


@router.post(
    "/",
    response_model=BillingEntityResponse,
    status_code=201,
    summary="Create billing entity",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        409: {"description": "Billing entity with this code already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_billing_entity(
    data: BillingEntityCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> BillingEntity | JSONResponse:
    """Create a new billing entity."""
    idempotency = check_idempotency(request, db, organization_id)
    if isinstance(idempotency, JSONResponse):
        return idempotency

    repo = BillingEntityRepository(db)
    if repo.code_exists(data.code, organization_id):
        raise HTTPException(
            status_code=409, detail="Billing entity with this code already exists"
        )
    entity = repo.create(data, organization_id)

    if isinstance(idempotency, IdempotencyResult):
        body = BillingEntityResponse.model_validate(entity).model_dump(mode="json")
        record_idempotency_response(db, organization_id, idempotency.key, 201, body)

    return entity


@router.patch(
    "/{code}",
    response_model=BillingEntityResponse,
    summary="Update billing entity",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Billing entity not found"},
        422: {"description": "Validation error"},
    },
)
async def update_billing_entity(
    code: str,
    data: BillingEntityUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> BillingEntity:
    """Update a billing entity by code."""
    repo = BillingEntityRepository(db)
    entity = repo.get_by_code(code, organization_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Billing entity not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(entity, key, value)
    db.commit()
    db.refresh(entity)
    return entity


@router.delete(
    "/{code}",
    status_code=204,
    summary="Delete billing entity",
    responses={
        400: {"description": "Cannot delete billing entity with invoices"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Billing entity not found"},
    },
)
async def delete_billing_entity(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a billing entity. Returns 400 if it has invoices."""
    repo = BillingEntityRepository(db)
    entity = repo.get_by_code(code, organization_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Billing entity not found")

    # Check if the entity has any invoices
    has_invoices = (
        db.query(Invoice.id)
        .filter(Invoice.billing_entity_id == entity.id)
        .first()
        is not None
    )
    if has_invoices:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete billing entity with existing invoices",
        )

    repo.delete(UUID(str(entity.id)), organization_id)
