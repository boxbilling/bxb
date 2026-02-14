"""Integrations router for managing external system connections."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.integration import Integration
from app.repositories.integration_repository import IntegrationRepository
from app.schemas.integration import IntegrationCreate, IntegrationResponse, IntegrationUpdate
from app.services.integrations.base import get_integration_adapter

router = APIRouter()


@router.post(
    "/",
    response_model=IntegrationResponse,
    status_code=201,
    summary="Create integration",
    responses={
        401: {"description": "Unauthorized"},
        409: {"description": "Integration with this provider already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_integration(
    data: IntegrationCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Integration:
    """Create a new integration."""
    repo = IntegrationRepository(db)
    existing = repo.get_by_provider(organization_id, data.provider_type)
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Integration with this provider already exists for this organization",
        )
    return repo.create(data, organization_id)


@router.get(
    "/",
    response_model=list[IntegrationResponse],
    summary="List integrations",
    responses={401: {"description": "Unauthorized"}},
)
async def list_integrations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Integration]:
    """List integrations for the organization."""
    repo = IntegrationRepository(db)
    return repo.get_all(organization_id, skip=skip, limit=limit)


@router.get(
    "/{integration_id}",
    response_model=IntegrationResponse,
    summary="Get integration",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Integration not found"},
    },
)
async def get_integration(
    integration_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Integration:
    """Get an integration by ID."""
    repo = IntegrationRepository(db)
    integration = repo.get_by_id(integration_id, organization_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.put(
    "/{integration_id}",
    response_model=IntegrationResponse,
    summary="Update integration",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Integration not found"},
        422: {"description": "Validation error"},
    },
)
async def update_integration(
    integration_id: UUID,
    data: IntegrationUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> Integration:
    """Update an integration\'s settings."""
    repo = IntegrationRepository(db)
    integration = repo.update(integration_id, data, organization_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.delete(
    "/{integration_id}",
    status_code=204,
    summary="Delete integration",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Integration not found"},
    },
)
async def delete_integration(
    integration_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Remove an integration."""
    repo = IntegrationRepository(db)
    if not repo.delete(integration_id, organization_id):
        raise HTTPException(status_code=404, detail="Integration not found")


@router.post(
    "/{integration_id}/test",
    response_model=dict[str, Any],
    summary="Test integration connection",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Integration not found"},
        422: {"description": "Unsupported integration type"},
    },
)
async def test_integration_connection(
    integration_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> dict[str, Any]:
    """Test an integration\'s connection credentials."""
    repo = IntegrationRepository(db)
    integration = repo.get_by_id(integration_id, organization_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    try:
        adapter = get_integration_adapter(integration)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = adapter.test_connection()
    return {
        "success": result.success,
        "error": result.error,
        "details": result.details,
    }
