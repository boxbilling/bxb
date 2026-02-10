from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.plan import Plan
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan import PlanCreate, PlanResponse, PlanUpdate

router = APIRouter()


@router.get("/", response_model=list[PlanResponse])
async def list_plans(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[Plan]:
    """List all plans with pagination."""
    repo = PlanRepository(db)
    return repo.get_all(skip=skip, limit=limit)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
) -> Plan:
    """Get a plan by ID."""
    repo = PlanRepository(db)
    plan = repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("/", response_model=PlanResponse, status_code=201)
async def create_plan(
    data: PlanCreate,
    db: Session = Depends(get_db),
) -> Plan:
    """Create a new plan."""
    repo = PlanRepository(db)
    if repo.code_exists(data.code):
        raise HTTPException(
            status_code=409, detail="Plan with this code already exists"
        )
    return repo.create(data)


@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: UUID,
    data: PlanUpdate,
    db: Session = Depends(get_db),
) -> Plan:
    """Update a plan."""
    repo = PlanRepository(db)
    plan = repo.update(plan_id, data)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a plan."""
    repo = PlanRepository(db)
    if not repo.delete(plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")
