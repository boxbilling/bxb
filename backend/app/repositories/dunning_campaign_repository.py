"""DunningCampaign repository for data access."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.dunning_campaign import DunningCampaign
from app.models.dunning_campaign_threshold import DunningCampaignThreshold
from app.schemas.dunning_campaign import DunningCampaignCreate, DunningCampaignUpdate


class DunningCampaignRepository:
    """Repository for DunningCampaign model."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> list[DunningCampaign]:
        """Get all dunning campaigns for an organization."""
        query = self.db.query(DunningCampaign).filter(
            DunningCampaign.organization_id == organization_id,
        )
        if status is not None:
            query = query.filter(DunningCampaign.status == status)
        return query.order_by(DunningCampaign.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_id(
        self, campaign_id: UUID, organization_id: UUID,
    ) -> DunningCampaign | None:
        """Get a dunning campaign by ID."""
        return (
            self.db.query(DunningCampaign)
            .filter(
                DunningCampaign.id == campaign_id,
                DunningCampaign.organization_id == organization_id,
            )
            .first()
        )

    def get_by_code(
        self, code: str, organization_id: UUID,
    ) -> DunningCampaign | None:
        """Get a dunning campaign by code."""
        return (
            self.db.query(DunningCampaign)
            .filter(
                DunningCampaign.code == code,
                DunningCampaign.organization_id == organization_id,
            )
            .first()
        )

    def create(
        self, data: DunningCampaignCreate, organization_id: UUID,
    ) -> DunningCampaign:
        """Create a new dunning campaign with thresholds."""
        thresholds_data = data.thresholds
        campaign = DunningCampaign(
            **data.model_dump(exclude={"thresholds"}),
            organization_id=organization_id,
        )
        self.db.add(campaign)
        self.db.flush()

        for threshold_data in thresholds_data:
            threshold = DunningCampaignThreshold(
                dunning_campaign_id=campaign.id,
                **threshold_data.model_dump(),
            )
            self.db.add(threshold)

        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def update(
        self,
        campaign_id: UUID,
        data: DunningCampaignUpdate,
        organization_id: UUID,
    ) -> DunningCampaign | None:
        """Update a dunning campaign."""
        campaign = self.get_by_id(campaign_id, organization_id)
        if not campaign:
            return None

        update_data = data.model_dump(exclude_unset=True, exclude={"thresholds"})
        for key, value in update_data.items():
            setattr(campaign, key, value)

        # If thresholds are provided, replace them
        if data.thresholds is not None:
            self.db.query(DunningCampaignThreshold).filter(
                DunningCampaignThreshold.dunning_campaign_id == campaign_id,
            ).delete()
            for threshold_data in data.thresholds:
                threshold = DunningCampaignThreshold(
                    dunning_campaign_id=campaign_id,
                    **threshold_data.model_dump(),
                )
                self.db.add(threshold)

        self.db.commit()
        self.db.refresh(campaign)
        return campaign

    def delete(self, campaign_id: UUID, organization_id: UUID) -> bool:
        """Delete a dunning campaign."""
        campaign = self.get_by_id(campaign_id, organization_id)
        if not campaign:
            return False
        # Thresholds are cascade deleted via FK
        self.db.delete(campaign)
        self.db.commit()
        return True

    def get_thresholds(self, campaign_id: UUID) -> list[DunningCampaignThreshold]:
        """Get all thresholds for a dunning campaign."""
        return (
            self.db.query(DunningCampaignThreshold)
            .filter(DunningCampaignThreshold.dunning_campaign_id == campaign_id)
            .all()
        )
