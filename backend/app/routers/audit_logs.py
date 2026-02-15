"""Audit log API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.audit_log import AuditLogResponse

router = APIRouter()


@router.get(
    "/",
    response_model=list[AuditLogResponse],
    summary="List audit logs",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_audit_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    action: str | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[AuditLogResponse]:
    """List audit logs with optional filters."""
    repo = AuditLogRepository(db)
    if resource_id is not None and resource_type is not None:
        logs = repo.get_by_resource(resource_type, resource_id, skip=skip, limit=limit)
        return [AuditLogResponse.model_validate(log) for log in logs]
    return [
        AuditLogResponse.model_validate(log)
        for log in repo.get_all(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            resource_type=resource_type,
            action=action,
        )
    ]


@router.get(
    "/{resource_type}/{resource_id}",
    response_model=list[AuditLogResponse],
    summary="Get audit trail for a resource",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_resource_audit_trail(
    resource_type: str,
    resource_id: UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[AuditLogResponse]:
    """Get the audit trail for a specific resource."""
    repo = AuditLogRepository(db)
    logs = repo.get_by_resource(resource_type, resource_id, skip=skip, limit=limit)
    return [AuditLogResponse.model_validate(log) for log in logs]
