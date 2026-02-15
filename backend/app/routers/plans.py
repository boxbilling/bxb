from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.repositories.billable_metric_filter_repository import BillableMetricFilterRepository
from app.repositories.billable_metric_repository import BillableMetricRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan import ChargeInput, PlanCreate, PlanResponse, PlanUpdate

router = APIRouter()


def _validate_charge_filters(
    charges: list[ChargeInput],
    filter_repo: BillableMetricFilterRepository,
) -> None:
    """Validate that all billable_metric_filter_ids in charge filters exist."""
    for charge in charges:
        for filter_input in charge.filters:
            bmf = filter_repo.get_by_id(filter_input.billable_metric_filter_id)
            if not bmf:
                fid = filter_input.billable_metric_filter_id
                raise HTTPException(
                    status_code=400,
                    detail=f"Billable metric filter {fid} not found",
                )
            for value in filter_input.values:
                if bmf.values and value not in bmf.values:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Value '{value}' is not allowed for filter '{bmf.key}'. "
                            f"Allowed values: {bmf.values}"
                        ),
                    )


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


@router.get(
    "/",
    response_model=list[PlanResponse],
    summary="List plans",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def list_plans(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[dict[str, Any]]:
    """List all plans with pagination."""
    repo = PlanRepository(db)
    response.headers["X-Total-Count"] = str(repo.count(organization_id))
    plans = repo.get_all(organization_id, skip=skip, limit=limit)
    return [_plan_to_response(repo, plan) for plan in plans]


@router.get(
    "/subscription_counts",
    response_model=dict[str, int],
    summary="Get subscription counts per plan",
    responses={401: {"description": "Unauthorized – invalid or missing API key"}},
)
async def get_subscription_counts(
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> dict[str, int]:
    """Return a mapping of plan_id to subscription count."""
    repo = PlanRepository(db)
    return repo.subscription_counts(organization_id)


@router.get(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Get plan",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Plan not found"},
    },
)
async def get_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> dict[str, Any]:
    """Get a plan by ID."""
    repo = PlanRepository(db)
    plan = repo.get_by_id(plan_id, organization_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_to_response(repo, plan)


@router.post(
    "/",
    response_model=PlanResponse,
    status_code=201,
    summary="Create plan",
    responses={
        400: {"description": "Invalid billable metric or filter reference"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        409: {"description": "Plan with this code already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_plan(
    data: PlanCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> dict[str, Any]:
    """Create a new plan."""
    repo = PlanRepository(db)
    if repo.code_exists(data.code, organization_id):
        raise HTTPException(status_code=409, detail="Plan with this code already exists")

    # Validate all billable_metric_ids exist
    metric_repo = BillableMetricRepository(db)
    for charge in data.charges:
        if not metric_repo.get_by_id(charge.billable_metric_id):
            raise HTTPException(
                status_code=400, detail=f"Billable metric {charge.billable_metric_id} not found"
            )

    # Validate all billable_metric_filter_ids in charge filters
    filter_repo = BillableMetricFilterRepository(db)
    _validate_charge_filters(data.charges, filter_repo)

    plan = repo.create(data, organization_id)
    return _plan_to_response(repo, plan)


@router.put(
    "/{plan_id}",
    response_model=PlanResponse,
    summary="Update plan",
    responses={
        400: {"description": "Invalid billable metric or filter reference"},
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Plan not found"},
        422: {"description": "Validation error"},
    },
)
async def update_plan(
    plan_id: UUID,
    data: PlanUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
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

        # Validate all billable_metric_filter_ids in charge filters
        filter_repo = BillableMetricFilterRepository(db)
        _validate_charge_filters(data.charges, filter_repo)

    plan = repo.update(plan_id, data, organization_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_to_response(repo, plan)


@router.delete(
    "/{plan_id}",
    status_code=204,
    summary="Delete plan",
    responses={
        401: {"description": "Unauthorized – invalid or missing API key"},
        404: {"description": "Plan not found"},
    },
)
async def delete_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a plan."""
    repo = PlanRepository(db)
    if not repo.delete(plan_id, organization_id):
        raise HTTPException(status_code=404, detail="Plan not found")
