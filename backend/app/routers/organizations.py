"""Organization management and API key endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.organization import Organization
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
)
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)

router = APIRouter()


class OrganizationCreateResponse(OrganizationResponse):
    """Organization creation response that includes the initial API key."""

    api_key: ApiKeyCreateResponse


@router.post(
    "/",
    response_model=OrganizationCreateResponse,
    status_code=201,
    summary="Create organization",
    responses={422: {"description": "Validation error"}},
)
async def create_organization(
    data: OrganizationCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a new organization with an initial API key."""
    org_repo = OrganizationRepository(db)
    org = org_repo.create(data)

    api_key_repo = ApiKeyRepository(db)
    api_key, raw_key = api_key_repo.create(
        org.id,  # type: ignore[arg-type]
        ApiKeyCreate(name="Initial API Key"),
    )

    api_key_response = ApiKeyCreateResponse(
        **ApiKeyResponse.model_validate(api_key).model_dump(),
        raw_key=raw_key,
    )

    org_response = OrganizationResponse.model_validate(org).model_dump()
    org_response["api_key"] = api_key_response

    return org_response


@router.get(
    "/current",
    response_model=OrganizationResponse,
    summary="Get current organization",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Organization not found"},
    },
)
async def get_current_org(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Organization:
    """Get the current organization (identified by API key)."""
    repo = OrganizationRepository(db)
    org = repo.get_by_id(organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.put(
    "/current",
    response_model=OrganizationResponse,
    summary="Update current organization",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Organization not found"},
        422: {"description": "Validation error"},
    },
)
async def update_current_org(
    data: OrganizationUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Organization:
    """Update the current organization."""
    repo = OrganizationRepository(db)
    org = repo.update(organization_id, data)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.post(
    "/current/api_keys",
    response_model=ApiKeyCreateResponse,
    status_code=201,
    summary="Create API key",
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Validation error"},
    },
)
async def create_api_key(
    data: ApiKeyCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> dict[str, Any]:
    """Generate a new API key for the current organization."""
    repo = ApiKeyRepository(db)
    api_key, raw_key = repo.create(organization_id, data)

    response = ApiKeyResponse.model_validate(api_key).model_dump()
    response["raw_key"] = raw_key
    return response


@router.get(
    "/current/api_keys",
    response_model=list[ApiKeyListResponse],
    summary="List API keys",
    responses={401: {"description": "Unauthorized"}},
)
async def list_api_keys(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[ApiKey]:
    """List API keys for the current organization (prefix and name only)."""
    repo = ApiKeyRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.list_by_org(organization_id, skip=skip, limit=limit)


@router.delete(
    "/current/api_keys/{api_key_id}",
    status_code=204,
    summary="Revoke API key",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "API key not found"},
    },
)
async def revoke_api_key(
    api_key_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Revoke an API key."""
    repo = ApiKeyRepository(db)
    result = repo.revoke(api_key_id, organization_id)
    if not result:
        raise HTTPException(status_code=404, detail="API key not found")
