from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.core.idempotency import IdempotencyResult, check_idempotency, record_idempotency_response
from app.models.feature import Feature
from app.repositories.entitlement_repository import EntitlementRepository
from app.repositories.feature_repository import FeatureRepository
from app.schemas.feature import FeatureCreate, FeatureResponse, FeatureUpdate

router = APIRouter()


@router.get(
    "/",
    response_model=list[FeatureResponse],
    summary="List features",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_features(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Feature]:
    """List all features with pagination."""
    repo = FeatureRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(organization_id, skip=skip, limit=limit)


@router.get(
    "/plan_counts",
    response_model=dict[str, int],
    summary="Get plan counts per feature",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_feature_plan_counts(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> dict[str, int]:
    """Get the number of distinct plans with entitlements for each feature."""
    repo = FeatureRepository(db)
    return repo.plan_counts(organization_id)


@router.get(
    "/{code}",
    response_model=FeatureResponse,
    summary="Get feature by code",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Feature not found"},
    },
)
async def get_feature(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Feature:
    """Get a feature by its code."""
    repo = FeatureRepository(db)
    feature = repo.get_by_code(code, organization_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.post(
    "/",
    response_model=FeatureResponse,
    status_code=201,
    summary="Create feature",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        409: {"description": "Feature with this code already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_feature(
    data: FeatureCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Feature | JSONResponse:
    """Create a new feature."""
    idempotency = check_idempotency(request, db, organization_id)
    if isinstance(idempotency, JSONResponse):
        return idempotency

    repo = FeatureRepository(db)
    if repo.code_exists(data.code, organization_id):
        raise HTTPException(
            status_code=409, detail="Feature with this code already exists"
        )
    feature = repo.create(data, organization_id)

    if isinstance(idempotency, IdempotencyResult):
        body = FeatureResponse.model_validate(feature).model_dump(mode="json")
        record_idempotency_response(db, organization_id, idempotency.key, 201, body)

    return feature


@router.patch(
    "/{code}",
    response_model=FeatureResponse,
    summary="Update feature",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Feature not found"},
        422: {"description": "Validation error"},
    },
)
async def update_feature(
    code: str,
    data: FeatureUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Feature:
    """Update a feature by code."""
    repo = FeatureRepository(db)
    feature = repo.get_by_code(code, organization_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(feature, key, value)
    db.commit()
    db.refresh(feature)
    return feature


@router.delete(
    "/{code}",
    status_code=204,
    summary="Delete feature",
    responses={
        400: {"description": "Cannot delete feature with entitlements"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Feature not found"},
    },
)
async def delete_feature(
    code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a feature. Returns 400 if it has entitlements."""
    repo = FeatureRepository(db)
    feature = repo.get_by_code(code, organization_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    entitlement_repo = EntitlementRepository(db)
    entitlements = entitlement_repo.get_by_feature_id(
        UUID(str(feature.id)), organization_id
    )
    if entitlements:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete feature with existing entitlements",
        )

    repo.delete(UUID(str(feature.id)), organization_id)
