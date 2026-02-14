"""DunningCampaign API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.models.dunning_campaign import DunningCampaign
from app.repositories.dunning_campaign_repository import DunningCampaignRepository
from app.schemas.dunning_campaign import (
    DunningCampaignCreate,
    DunningCampaignResponse,
    DunningCampaignThresholdResponse,
    DunningCampaignUpdate,
)

router = APIRouter()


def _campaign_to_response(
    campaign: DunningCampaign,
    repo: DunningCampaignRepository,
) -> DunningCampaignResponse:
    """Build a DunningCampaignResponse with thresholds loaded."""
    campaign_id: UUID = campaign.id  # type: ignore[assignment]
    thresholds = repo.get_thresholds(campaign_id)
    threshold_responses = [DunningCampaignThresholdResponse.model_validate(t) for t in thresholds]
    resp = DunningCampaignResponse.model_validate(campaign)
    resp.thresholds = threshold_responses
    return resp


@router.post(
    "/",
    response_model=DunningCampaignResponse,
    status_code=201,
    summary="Create dunning campaign",
    responses={
        401: {"description": "Unauthorized"},
        409: {"description": "Dunning campaign with this code already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_dunning_campaign(
    data: DunningCampaignCreate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> DunningCampaignResponse:
    """Create a new dunning campaign."""
    repo = DunningCampaignRepository(db)
    if repo.get_by_code(data.code, organization_id):
        raise HTTPException(
            status_code=409,
            detail="Dunning campaign with this code already exists",
        )
    campaign = repo.create(data, organization_id)
    return _campaign_to_response(campaign, repo)


@router.get(
    "/",
    response_model=list[DunningCampaignResponse],
    summary="List dunning campaigns",
    responses={401: {"description": "Unauthorized"}},
)
async def list_dunning_campaigns(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    status: str | None = None,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> list[DunningCampaignResponse]:
    """List dunning campaigns with optional status filter."""
    repo = DunningCampaignRepository(db)
    campaigns = repo.get_all(organization_id, skip=skip, limit=limit, status=status)
    return [_campaign_to_response(c, repo) for c in campaigns]


@router.get(
    "/{campaign_id}",
    response_model=DunningCampaignResponse,
    summary="Get dunning campaign",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Dunning campaign not found"},
    },
)
async def get_dunning_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> DunningCampaignResponse:
    """Get a dunning campaign by ID."""
    repo = DunningCampaignRepository(db)
    campaign = repo.get_by_id(campaign_id, organization_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Dunning campaign not found")
    return _campaign_to_response(campaign, repo)


@router.put(
    "/{campaign_id}",
    response_model=DunningCampaignResponse,
    summary="Update dunning campaign",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Dunning campaign not found"},
        422: {"description": "Validation error"},
    },
)
async def update_dunning_campaign(
    campaign_id: UUID,
    data: DunningCampaignUpdate,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> DunningCampaignResponse:
    """Update a dunning campaign."""
    repo = DunningCampaignRepository(db)
    campaign = repo.update(campaign_id, data, organization_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Dunning campaign not found")
    return _campaign_to_response(campaign, repo)


@router.delete(
    "/{campaign_id}",
    status_code=204,
    summary="Delete dunning campaign",
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Dunning campaign not found"},
    },
)
async def delete_dunning_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    organization_id: UUID = Depends(get_current_organization),
) -> None:
    """Delete a dunning campaign."""
    repo = DunningCampaignRepository(db)
    if not repo.delete(campaign_id, organization_id):
        raise HTTPException(status_code=404, detail="Dunning campaign not found")
