from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan import PlanCreate, PlanResponse, PlanUpdate

router = APIRouter()


def _plan_to_response(repo: PlanRepository, plan: Any) -> dict[str, Any]:
    """Convert Plan model to response dict with charges."""
    charges = repo.get_charges(plan.id)
    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "interval": plan.interval,
        "amount_cents": plan.amount_cents,
        "currency": plan.currency,
        "trial_period_days": plan.trial_period_days,
        "charges": charges,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


@router.get("/", response_model=list[PlanResponse])
async def list_plans(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all plans with pagination."""
    repo = PlanRepository(db)
    plans = repo.get_all(skip=skip, limit=limit)
    return [_plan_to_response(repo, plan) for plan in plans]


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get a plan by ID."""
    repo = PlanRepository(db)
    plan = repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_to_response(repo, plan)


@router.post("/", response_model=PlanResponse, status_code=201)
async def create_plan(
    data: PlanCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a new plan."""
    repo = PlanRepository(db)
    if repo.code_exists(data.code):
        raise HTTPException(status_code=409, detail="Plan with this code already exists")

    # Validate all billable_metric_ids exist
    metric_repo = BillableMetricRepository(db)
    for charge in data.charges:
        if not metric_repo.get_by_id(charge.billable_metric_id):
            raise HTTPException(
                status_code=400, detail=f"Billable metric {charge.billable_metric_id} not found"
            )

    plan = repo.create(data)
    return _plan_to_response(repo, plan)


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: UUID,
    data: PlanUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update a plan."""
    repo = PlanRepository(db)

    # Validate all billable_metric_ids exist if charges are being updated
    if data.charges is not None:
        metric_repo = BillableMetricRepository(db)
        for charge in data.charges:
            if not metric_repo.get_by_id(charge.billable_metric_id):
                raise HTTPException(
                    status_code=400, detail=f"Billable metric {charge.billable_metric_id} not found"
                )

    plan = repo.update(plan_id, data)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_to_response(repo, plan)


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a plan."""
    repo = PlanRepository(db)
    if not repo.delete(plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")
