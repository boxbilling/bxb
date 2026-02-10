from uuid import UUID

from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.schemas.plan import PlanCreate, PlanUpdate


class PlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Plan]:
        return self.db.query(Plan).offset(skip).limit(limit).all()

    def get_by_id(self, plan_id: UUID) -> Plan | None:
        return self.db.query(Plan).filter(Plan.id == plan_id).first()

    def get_by_code(self, code: str) -> Plan | None:
        return self.db.query(Plan).filter(Plan.code == code).first()

    def create(self, data: PlanCreate) -> Plan:
        plan = Plan(
            code=data.code,
            name=data.name,
            description=data.description,
            interval=data.interval.value,
            amount_cents=data.amount_cents,
            currency=data.currency,
            trial_period_days=data.trial_period_days,
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def update(self, plan_id: UUID, data: PlanUpdate) -> Plan | None:
        plan = self.get_by_id(plan_id)
        if not plan:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(plan, key, value)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def delete(self, plan_id: UUID) -> bool:
        plan = self.get_by_id(plan_id)
        if not plan:
            return False
        self.db.delete(plan)
        self.db.commit()
        return True

    def code_exists(self, code: str) -> bool:
        """Check if a plan with the given code already exists."""
        query = self.db.query(Plan).filter(Plan.code == code)
        return query.first() is not None
