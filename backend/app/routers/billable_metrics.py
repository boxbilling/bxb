from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.billable_metric import BillableMetric
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.schemas.billable_metric import (
    BillableMetricCreate,
    BillableMetricResponse,
    BillableMetricUpdate,
)

router = APIRouter()


@router.get("/", response_model=list[BillableMetricResponse])
async def list_billable_metrics(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[BillableMetric]:
    """List all billable metrics with pagination."""
    repo = BillableMetricRepository(db)
    return repo.get_all(skip=skip, limit=limit)


@router.get("/{metric_id}", response_model=BillableMetricResponse)
async def get_billable_metric(
    metric_id: UUID,
    db: Session = Depends(get_db),
) -> BillableMetric:
    """Get a billable metric by ID."""
    repo = BillableMetricRepository(db)
    metric = repo.get_by_id(metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Billable metric not found")
    return metric


@router.post("/", response_model=BillableMetricResponse, status_code=201)
async def create_billable_metric(
    data: BillableMetricCreate,
    db: Session = Depends(get_db),
) -> BillableMetric:
    """Create a new billable metric."""
    repo = BillableMetricRepository(db)
    if repo.code_exists(data.code):
        raise HTTPException(
            status_code=409, detail="Billable metric with this code already exists"
        )
    return repo.create(data)


@router.put("/{metric_id}", response_model=BillableMetricResponse)
async def update_billable_metric(
    metric_id: UUID,
    data: BillableMetricUpdate,
    db: Session = Depends(get_db),
) -> BillableMetric:
    """Update a billable metric."""
    repo = BillableMetricRepository(db)
    metric = repo.update(metric_id, data)
    if not metric:
        raise HTTPException(status_code=404, detail="Billable metric not found")
    return metric


@router.delete("/{metric_id}", status_code=204)
async def delete_billable_metric(
    metric_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a billable metric."""
    repo = BillableMetricRepository(db)
    if not repo.delete(metric_id):
        raise HTTPException(status_code=404, detail="Billable metric not found")
