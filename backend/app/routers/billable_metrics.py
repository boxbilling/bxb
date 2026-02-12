from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.billable_metric import BillableMetric
from app.models.billable_metric_filter import BillableMetricFilter
from app.repositories.billable_metric_filter_repository import BillableMetricFilterRepository
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.schemas.billable_metric import (
    BillableMetricCreate,
    BillableMetricResponse,
    BillableMetricUpdate,
)
from app.schemas.billable_metric_filter import (
    BillableMetricFilterCreate,
    BillableMetricFilterResponse,
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
        raise HTTPException(status_code=409, detail="Billable metric with this code already exists")
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


@router.post(
    "/{code}/filters",
    response_model=BillableMetricFilterResponse,
    status_code=201,
)
async def create_billable_metric_filter(
    code: str,
    data: BillableMetricFilterCreate,
    db: Session = Depends(get_db),
) -> BillableMetricFilter:
    """Add a filter to a billable metric."""
    metric_repo = BillableMetricRepository(db)
    metric = metric_repo.get_by_code(code)
    if not metric:
        raise HTTPException(status_code=404, detail="Billable metric not found")

    filter_repo = BillableMetricFilterRepository(db)
    return filter_repo.create(metric.id, data)  # type: ignore[arg-type]


@router.get(
    "/{code}/filters",
    response_model=list[BillableMetricFilterResponse],
)
async def list_billable_metric_filters(
    code: str,
    db: Session = Depends(get_db),
) -> list[BillableMetricFilter]:
    """List filters for a billable metric."""
    metric_repo = BillableMetricRepository(db)
    metric = metric_repo.get_by_code(code)
    if not metric:
        raise HTTPException(status_code=404, detail="Billable metric not found")

    filter_repo = BillableMetricFilterRepository(db)
    return filter_repo.get_by_metric_id(metric.id)  # type: ignore[arg-type]


@router.delete("/{code}/filters/{filter_id}", status_code=204)
async def delete_billable_metric_filter(
    code: str,
    filter_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Remove a filter from a billable metric."""
    metric_repo = BillableMetricRepository(db)
    metric = metric_repo.get_by_code(code)
    if not metric:
        raise HTTPException(status_code=404, detail="Billable metric not found")

    filter_repo = BillableMetricFilterRepository(db)
    if not filter_repo.delete(filter_id):
        raise HTTPException(status_code=404, detail="Filter not found")
