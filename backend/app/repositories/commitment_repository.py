from uuid import UUID

from sqlalchemy.orm import Session

from app.models.commitment import Commitment
from app.schemas.commitment import CommitmentCreate, CommitmentUpdate


class CommitmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, organization_id: UUID, skip: int = 0, limit: int = 100) -> list[Commitment]:
        return (
            self.db.query(Commitment)
            .filter(Commitment.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id(
        self, commitment_id: UUID, organization_id: UUID | None = None
    ) -> Commitment | None:
        query = self.db.query(Commitment).filter(Commitment.id == commitment_id)
        if organization_id is not None:
            query = query.filter(Commitment.organization_id == organization_id)
        return query.first()

    def get_by_plan_id(self, plan_id: UUID) -> list[Commitment]:
        return self.db.query(Commitment).filter(Commitment.plan_id == plan_id).all()

    def create(self, data: CommitmentCreate, organization_id: UUID) -> Commitment:
        commitment = Commitment(
            plan_id=data.plan_id,
            commitment_type=data.commitment_type,
            amount_cents=data.amount_cents,
            invoice_display_name=data.invoice_display_name,
            organization_id=organization_id,
        )
        self.db.add(commitment)
        self.db.commit()
        self.db.refresh(commitment)
        return commitment

    def update(
        self, commitment_id: UUID, data: CommitmentUpdate, organization_id: UUID
    ) -> Commitment | None:
        commitment = self.get_by_id(commitment_id, organization_id)
        if not commitment:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(commitment, key, value)
        self.db.commit()
        self.db.refresh(commitment)
        return commitment

    def delete(self, commitment_id: UUID, organization_id: UUID) -> bool:
        commitment = self.get_by_id(commitment_id, organization_id)
        if not commitment:
            return False
        self.db.delete(commitment)
        self.db.commit()
        return True
