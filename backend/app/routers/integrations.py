"""Integrations router for managing external system connections."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.integration import Integration
from app.models.integration_customer import IntegrationCustomer
from app.models.integration_mapping import IntegrationMapping
from app.models.integration_sync_history import IntegrationSyncHistory
from app.repositories.integration_customer_repository import IntegrationCustomerRepository
from app.repositories.integration_mapping_repository import IntegrationMappingRepository
from app.repositories.integration_repository import IntegrationRepository
from app.repositories.integration_sync_history_repository import IntegrationSyncHistoryRepository
from app.schemas.integration import IntegrationCreate, IntegrationResponse, IntegrationUpdate
from app.schemas.integration_customer import IntegrationCustomerResponse
from app.schemas.integration_mapping import IntegrationMappingResponse
from app.schemas.integration_sync_history import IntegrationSyncHistoryResponse
from app.services.integrations.base import get_integration_adapter

router = APIRouter()


def _get_integration_or_404(
    integration_id: UUID,
    organization_id: UUID,
    db: Session,
) -> Integration:
    """Fetch an integration or raise 404."""
    repo = IntegrationRepository(db)
    integration = repo.get_by_id(integration_id, organization_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


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
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    order_by: str | None = Query(default=None),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[Integration]:
    """List integrations for the organization."""
    repo = IntegrationRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    return repo.get_all(organization_id, skip=skip, limit=limit, order_by=order_by)


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
    return _get_integration_or_404(integration_id, organization_id, db)


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
    """Update an integration's settings."""
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
    """Test an integration's connection credentials."""
    integration = _get_integration_or_404(integration_id, organization_id, db)
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


# ─────────────────────────────────────────────────────────────────────────────
# Sub-resource endpoints: Customer Mappings
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/{integration_id}/customers",
    response_model=list[IntegrationCustomerResponse],
    summary="List integration customer mappings",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Integration not found"},
    },
)
async def list_integration_customers(
    integration_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[IntegrationCustomer]:
    """List customer mappings for an integration."""
    _get_integration_or_404(integration_id, organization_id, db)
    repo = IntegrationCustomerRepository(db)
    return repo.get_all(integration_id, skip=skip, limit=limit)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-resource endpoints: Field Mappings
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/{integration_id}/mappings",
    response_model=list[IntegrationMappingResponse],
    summary="List integration field mappings",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Integration not found"},
    },
)
async def list_integration_mappings(
    integration_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[IntegrationMapping]:
    """List field mappings for an integration."""
    _get_integration_or_404(integration_id, organization_id, db)
    repo = IntegrationMappingRepository(db)
    return repo.get_all(integration_id, skip=skip, limit=limit)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-resource endpoints: Sync History
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/{integration_id}/sync_history",
    response_model=list[IntegrationSyncHistoryResponse],
    summary="List integration sync history",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Integration not found"},
    },
)
async def list_integration_sync_history(
    integration_id: UUID,
    status: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[IntegrationSyncHistory]:
    """List sync history for an integration, with optional status/resource_type filters."""
    _get_integration_or_404(integration_id, organization_id, db)
    repo = IntegrationSyncHistoryRepository(db)
    return repo.get_all(
        integration_id,
        status=status,
        resource_type=resource_type,
        skip=skip,
        limit=limit,
    )
