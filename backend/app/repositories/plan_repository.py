from uuid import UUID

from sqlalchemy.orm import Session

from app.models.charge import Charge
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

    def get_charges(self, plan_id: UUID) -> list[Charge]:
        return self.db.query(Charge).filter(Charge.plan_id == plan_id).all()

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
        self.db.flush()  # Get the plan ID

        # Create charges
        for charge_data in data.charges:
            charge = Charge(
                plan_id=plan.id,
                billable_metric_id=charge_data.billable_metric_id,
                charge_model=charge_data.charge_model.value,
                properties=charge_data.properties,
            )
            self.db.add(charge)

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def update(self, plan_id: UUID, data: PlanUpdate) -> Plan | None:
        plan = self.get_by_id(plan_id)
        if not plan:
            return None

        # Update plan fields (excluding charges)
        update_data = data.model_dump(exclude_unset=True, exclude={"charges"})
        for key, value in update_data.items():
            setattr(plan, key, value)

        # Handle charges if provided
        if data.charges is not None:
            # Delete existing charges
            self.db.query(Charge).filter(Charge.plan_id == plan_id).delete()

            # Create new charges
            for charge_data in data.charges:
                charge = Charge(
                    plan_id=plan_id,
                    billable_metric_id=charge_data.billable_metric_id,
                    charge_model=charge_data.charge_model.value,
                    properties=charge_data.properties,
                )
                self.db.add(charge)

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def delete(self, plan_id: UUID) -> bool:
        plan = self.get_by_id(plan_id)
        if not plan:
            return False
        # Charges will be cascade deleted due to FK constraint
        self.db.delete(plan)
        self.db.commit()
        return True

    def code_exists(self, code: str) -> bool:
        """Check if a plan with the given code already exists."""
        query = self.db.query(Plan).filter(Plan.code == code)
        return query.first() is not None
