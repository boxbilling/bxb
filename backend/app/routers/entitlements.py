from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.core.idempotency import IdempotencyResult, check_idempotency, record_idempotency_response
from app.models.entitlement import Entitlement
from app.repositories.entitlement_repository import EntitlementRepository
from app.repositories.feature_repository import FeatureRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.entitlement import EntitlementCreate, EntitlementResponse, EntitlementUpdate

router = APIRouter()


@router.get(
    "/",
    response_model=list[EntitlementResponse],
    summary="List entitlements",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_entitlements(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    plan_id: UUID | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Entitlement]:
    """List all entitlements with pagination. Optionally filter by plan_id."""
    repo = EntitlementRepository(db)
    response.headers["X-Total-Count"] = str(
        repo.count(organization_id, plan_id=plan_id)
    )
    if plan_id:
        return repo.get_by_plan_id(plan_id, organization_id)
    return repo.get_all(organization_id, skip=skip, limit=limit)


@router.post(
    "/",
    response_model=EntitlementResponse,
    status_code=201,
    summary="Create entitlement",
    responses={
        400: {"description": "Invalid plan or feature reference"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        409: {"description": "Entitlement for this plan/feature already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_entitlement(
    data: EntitlementCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Entitlement | JSONResponse:
    """Create an entitlement linking a feature to a plan with a value."""
    idempotency = check_idempotency(request, db, organization_id)
    if isinstance(idempotency, JSONResponse):
        return idempotency

    # Validate plan exists
    plan_repo = PlanRepository(db)
    if not plan_repo.get_by_id(data.plan_id, organization_id):
        raise HTTPException(
            status_code=400, detail=f"Plan {data.plan_id} not found"
        )

    # Validate feature exists
    feature_repo = FeatureRepository(db)
    if not feature_repo.get_by_id(data.feature_id, organization_id):
        raise HTTPException(
            status_code=400, detail=f"Feature {data.feature_id} not found"
        )

    # Check for duplicate plan+feature combination
    repo = EntitlementRepository(db)
    existing = repo.get_by_plan_id(data.plan_id, organization_id)
    for ent in existing:
        if ent.feature_id == data.feature_id:
            raise HTTPException(
                status_code=409,
                detail="Entitlement for this plan and feature already exists",
            )

    entitlement = repo.create(data, organization_id)

    if isinstance(idempotency, IdempotencyResult):
        body = EntitlementResponse.model_validate(entitlement).model_dump(mode="json")
        record_idempotency_response(db, organization_id, idempotency.key, 201, body)

    return entitlement


@router.patch(
    "/{entitlement_id}",
    response_model=EntitlementResponse,
    summary="Update entitlement",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Entitlement not found"},
        422: {"description": "Validation error"},
    },
)
async def update_entitlement(
    entitlement_id: UUID,
    data: EntitlementUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Entitlement:
    """Update an entitlement's value."""
    repo = EntitlementRepository(db)
    entitlement = repo.get_by_id(entitlement_id, organization_id)
    if not entitlement:
        raise HTTPException(status_code=404, detail="Entitlement not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(entitlement, key, value)
    db.commit()
    db.refresh(entitlement)
    return entitlement


@router.delete(
    "/{entitlement_id}",
    status_code=204,
    summary="Delete entitlement",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Entitlement not found"},
    },
)
async def delete_entitlement(
    entitlement_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete an entitlement."""
    repo = EntitlementRepository(db)
    entitlement = repo.get_by_id(entitlement_id, organization_id)
    if not entitlement:
        raise HTTPException(status_code=404, detail="Entitlement not found")
    repo.delete(entitlement_id, organization_id)
