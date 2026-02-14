"""Data exports router for CSV export endpoints."""

import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.data_export import DataExport, ExportStatus
from app.repositories.data_export_repository import DataExportRepository
from app.schemas.data_export import DataExportCreate, DataExportResponse
from app.services.data_export_service import DataExportService

router = APIRouter()


@router.post(
    "/",
    response_model=DataExportResponse,
    status_code=201,
    summary="Create data export",
    responses={
        401: {"description": "Unauthorized"},
        422: {"description": "Validation error"},
    },
)
async def create_data_export(
    data: DataExportCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> DataExport:
    """Create a new data export and enqueue background processing."""
    service = DataExportService(db)
    export = service.create_export(
        organization_id=organization_id,
        export_type=data.export_type,
        filters=data.filters,
    )

    # Process synchronously for now; in production this would be enqueued
    service.process_export(export.id)  # type: ignore[arg-type]

    # Re-fetch to get updated status
    repo = DataExportRepository(db)
    updated = repo.get_by_id(export.id, organization_id)  # type: ignore[arg-type]
    return updated  # type: ignore[return-value]


@router.get(
    "/",
    response_model=list[DataExportResponse],
    summary="List data exports",
    responses={401: {"description": "Unauthorized"}},
)
async def list_data_exports(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[DataExport]:
    """List data exports for the organization."""
    repo = DataExportRepository(db)
    return repo.get_all(organization_id, skip=skip, limit=limit)


@router.get(
    "/{export_id}",
    response_model=DataExportResponse,
    summary="Get data export",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Data export not found"},
    },
)
async def get_data_export(
    export_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> DataExport:
    """Get a data export by ID."""
    repo = DataExportRepository(db)
    export = repo.get_by_id(export_id, organization_id)
    if not export:
        raise HTTPException(status_code=404, detail="Data export not found")
    return export


@router.get(
    "/{export_id}/download",
    summary="Download data export",
    responses={
        400: {"description": "Export is not completed"},
        401: {"description": "Unauthorized"},
        404: {"description": "Data export or file not found"},
    },
)
async def download_data_export(
    export_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> FileResponse:
    """Download the CSV file for a completed data export."""
    repo = DataExportRepository(db)
    export = repo.get_by_id(export_id, organization_id)
    if not export:
        raise HTTPException(status_code=404, detail="Data export not found")
    if export.status != ExportStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Export is not completed")
    if not export.file_path or not os.path.exists(str(export.file_path)):
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(
        path=str(export.file_path),
        media_type="text/csv",
        filename=f"{export.export_type}_{export_id}.csv",
    )
