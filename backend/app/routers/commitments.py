from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.repositories.commitment_repository import CommitmentRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.commitment import (
    CommitmentCreate,
    CommitmentCreateAPI,
    CommitmentResponse,
    CommitmentUpdate,
)
from app.services.audit_service import AuditService

router = APIRouter()


@router.get(
    "/plans/{plan_code}/commitments",
    response_model=list[CommitmentResponse],
    summary="List plan commitments",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Plan not found"},
    },
)
async def list_commitments_for_plan(
    plan_code: str,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[CommitmentResponse]:
    """List all commitments for a plan."""
    plan_repo = PlanRepository(db)
    plan = plan_repo.get_by_code(plan_code, organization_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    repo = CommitmentRepository(db)
    return [
        CommitmentResponse.model_validate(c)
        for c in repo.get_by_plan_id(plan.id)  # type: ignore[arg-type]
    ]


@router.post(
    "/plans/{plan_code}/commitments",
    response_model=CommitmentResponse,
    status_code=201,
    summary="Create commitment",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Plan not found"},
        422: {"description": "Validation error"},
    },
)
async def create_commitment(
    plan_code: str,
    data: CommitmentCreateAPI,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CommitmentResponse:
    """Add a commitment to a plan."""
    plan_repo = PlanRepository(db)
    plan = plan_repo.get_by_code(plan_code, organization_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    create_data = CommitmentCreate(
        plan_id=plan.id,  # type: ignore[arg-type]
        commitment_type=data.commitment_type,
        amount_cents=data.amount_cents,
        invoice_display_name=data.invoice_display_name,
    )
    repo = CommitmentRepository(db)
    commitment = repo.create(create_data, organization_id)

    audit_service = AuditService(db)
    audit_service.log_create(
        resource_type="commitment",
        resource_id=commitment.id,  # type: ignore[arg-type]
        organization_id=organization_id,
        actor_type="api_key",
        data={
            "plan_code": plan_code,
            "commitment_type": commitment.commitment_type,
            "amount_cents": commitment.amount_cents,
        },
    )

    return CommitmentResponse.model_validate(commitment)


@router.put(
    "/commitments/{commitment_id}",
    response_model=CommitmentResponse,
    summary="Update commitment",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Commitment not found"},
        422: {"description": "Validation error"},
    },
)
async def update_commitment(
    commitment_id: UUID,
    data: CommitmentUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> CommitmentResponse:
    """Update a commitment."""
    repo = CommitmentRepository(db)
    old_commitment = repo.get_by_id(commitment_id, organization_id)
    if not old_commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")

    fields = data.model_dump(exclude_unset=True)
    old_data = {
        k: str(getattr(old_commitment, k))
        for k in fields
        if hasattr(old_commitment, k)
    }

    commitment = repo.update(commitment_id, data, organization_id)
    if not commitment:  # pragma: no cover - race condition
        raise HTTPException(status_code=404, detail="Commitment not found")

    new_data = {
        k: str(getattr(commitment, k)) if getattr(commitment, k) is not None else None
        for k in fields
        if hasattr(commitment, k)
    }

    audit_service = AuditService(db)
    audit_service.log_update(
        resource_type="commitment",
        resource_id=commitment_id,
        organization_id=organization_id,
        actor_type="api_key",
        old_data=old_data,
        new_data=new_data,
    )

    return CommitmentResponse.model_validate(commitment)


@router.delete(
    "/commitments/{commitment_id}",
    status_code=204,
    summary="Delete commitment",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Commitment not found"},
    },
)
async def delete_commitment(
    commitment_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Remove a commitment."""
    repo = CommitmentRepository(db)
    commitment = repo.get_by_id(commitment_id, organization_id)
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")

    audit_service = AuditService(db)
    audit_service.log_delete(
        resource_type="commitment",
        resource_id=commitment_id,
        organization_id=organization_id,
        actor_type="api_key",
        data={
            "commitment_type": commitment.commitment_type,
            "amount_cents": commitment.amount_cents,
            "plan_id": str(commitment.plan_id),
        },
    )

    repo.delete(commitment_id, organization_id)
