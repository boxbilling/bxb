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
from app.schemas.entitlement import (
    EntitlementCopyRequest,
    EntitlementCreate,
    EntitlementResponse,
    EntitlementUpdate,
)

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
    order_by: str | None = Query(default=None),
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
    return repo.get_all(organization_id, skip=skip, limit=limit, order_by=order_by)


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


@router.post(
    "/copy",
    response_model=list[EntitlementResponse],
    status_code=201,
    summary="Copy entitlements from one plan to another",
    responses={
        400: {"description": "Source or target plan not found, or same plan"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        422: {"description": "Validation error"},
    },
)
async def copy_entitlements(
    data: EntitlementCopyRequest,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Entitlement]:
    """Copy all entitlements from one plan to another, skipping duplicates."""
    if data.source_plan_id == data.target_plan_id:
        raise HTTPException(
            status_code=400, detail="Source and target plan must be different"
        )

    plan_repo = PlanRepository(db)
    if not plan_repo.get_by_id(data.source_plan_id, organization_id):
        raise HTTPException(
            status_code=400,
            detail=f"Source plan {data.source_plan_id} not found",
        )
    if not plan_repo.get_by_id(data.target_plan_id, organization_id):
        raise HTTPException(
            status_code=400,
            detail=f"Target plan {data.target_plan_id} not found",
        )

    repo = EntitlementRepository(db)
    source_entitlements = repo.get_by_plan_id(data.source_plan_id, organization_id)
    existing_target = repo.get_by_plan_id(data.target_plan_id, organization_id)
    existing_feature_ids = {e.feature_id for e in existing_target}

    created = []
    for ent in source_entitlements:
        if ent.feature_id in existing_feature_ids:
            continue
        new_ent = repo.create(
            EntitlementCreate(
                plan_id=data.target_plan_id,
                feature_id=UUID(str(ent.feature_id)),
                value=str(ent.value),
            ),
            organization_id,
        )
        created.append(new_ent)

    return created


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
