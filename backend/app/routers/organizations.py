"""Organization management and API key endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization, require_admin_secret
from app.core.database import get_db
from app.core.security import hash_password
from app.models.api_key import ApiKey
from app.models.organization import Organization
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.member_repository import MemberRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
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
    OrgBrandingResponse,
)
from app.schemas.user import UserCreate
from app.services.audit_service import AuditService

router = APIRouter()


class _OwnerInfo(BaseModel):
    user_id: UUID
    email: str


class OrganizationCreateResponse(OrganizationResponse):
    """Organization creation response that includes the initial API key."""

    api_key: ApiKeyCreateResponse
    owner: _OwnerInfo | None = None


@router.get(
    "/",
    response_model=list[OrganizationResponse],
    summary="List organizations",
)
async def list_organizations(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin_secret),
) -> list[Organization]:
    """List all organizations."""
    repo = OrganizationRepository(db)
    orgs = repo.get_all(skip=skip, limit=limit)
    response.headers["X-Total-Count"] = str(len(orgs))
    return orgs


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
    _admin: None = Depends(require_admin_secret),
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

    audit_service = AuditService(db)
    audit_service.log_create(
        resource_type="organization",
        resource_id=org.id,  # type: ignore[arg-type]
        organization_id=org.id,  # type: ignore[arg-type]
        actor_type="system",
        data={
            "name": org.name,
            "slug": org.slug,
        },
    )

    org_response = OrganizationResponse.model_validate(org).model_dump()
    org_response["api_key"] = api_key_response

    # Bootstrap first owner user if owner_email is provided
    if data.owner_email:
        if not data.owner_password:
            raise HTTPException(
                status_code=422,
                detail="owner_password is required when owner_email is provided",
            )
        user_repo = UserRepository(db)
        pw_hash = hash_password(data.owner_password)
        user = user_repo.create(
            UserCreate(
                email=data.owner_email,
                name=data.owner_name or data.owner_email,
                password=data.owner_password,
            ),
            password_hash=pw_hash,
        )
        member_repo = MemberRepository(db)
        member_repo.create(
            org_id=org.id,  # type: ignore[arg-type]
            user_id=user.id,  # type: ignore[arg-type]
            role="owner",
        )
        org_response["owner"] = {"user_id": user.id, "email": user.email}

    return org_response


@router.get(
    "/by-slug/{slug}",
    response_model=OrgBrandingResponse,
    summary="Get organization branding by slug",
)
async def get_org_by_slug(
    slug: str,
    db: Session = Depends(get_db),
) -> Organization:
    """Look up an organization by slug and return public branding fields."""
    org = db.query(Organization).filter(Organization.slug == slug).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.delete(
    "/{org_id}",
    status_code=204,
    summary="Delete organization",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Organization not found"},
    },
)
async def delete_organization(
    org_id: UUID,
    db: Session = Depends(get_db),
    _admin: None = Depends(require_admin_secret),
) -> None:
    """Hard-delete an organization and all its related records."""
    repo = OrganizationRepository(db)
    if not repo.delete_by_organization(org_id):
        raise HTTPException(status_code=404, detail="Organization not found")


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
    old_org = repo.get_by_id(organization_id)
    if not old_org:
        raise HTTPException(status_code=404, detail="Organization not found")

    fields = data.model_dump(exclude_unset=True)
    old_data = {
        k: str(getattr(old_org, k))
        for k in fields
        if hasattr(old_org, k)
    }

    org = repo.update(organization_id, data)
    if not org:  # pragma: no cover - race condition
        raise HTTPException(status_code=404, detail="Organization not found")

    new_data = {
        k: str(getattr(org, k)) if getattr(org, k) is not None else None
        for k in data.model_dump(exclude_unset=True)
        if hasattr(org, k)
    }

    audit_service = AuditService(db)
    audit_service.log_update(
        resource_type="organization",
        resource_id=organization_id,
        organization_id=organization_id,
        actor_type="api_key",
        old_data=old_data,
        new_data=new_data,
    )

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

    audit_service = AuditService(db)
    audit_service.log_create(
        resource_type="api_key",
        resource_id=api_key.id,  # type: ignore[arg-type]
        organization_id=organization_id,
        actor_type="api_key",
        data={"name": data.name},
    )

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


@router.post(
    "/current/api_keys/{api_key_id}/rotate",
    response_model=ApiKeyCreateResponse,
    summary="Rotate API key",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "API key not found or not active"},
    },
)
async def rotate_api_key(
    api_key_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> dict[str, Any]:
    """Rotate an API key: revoke the old key and create a new one with the same config."""
    repo = ApiKeyRepository(db)
    result = repo.rotate(api_key_id, organization_id)
    if not result:
        raise HTTPException(status_code=404, detail="API key not found or not active")
    new_key, raw_key = result

    audit_service = AuditService(db)
    audit_service.log_status_change(
        resource_type="api_key",
        resource_id=api_key_id,
        organization_id=organization_id,
        old_status="active",
        new_status="rotated",
        actor_type="api_key",
    )

    response = ApiKeyResponse.model_validate(new_key).model_dump()
    response["raw_key"] = raw_key
    return response


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

    audit_service = AuditService(db)
    audit_service.log_delete(
        resource_type="api_key",
        resource_id=api_key_id,
        organization_id=organization_id,
        actor_type="api_key",
        data={"id": str(api_key_id)},
    )
