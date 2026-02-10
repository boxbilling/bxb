from uuid import UUID

from sqlalchemy.orm import Session

from app.models.charge import Charge
from app.schemas.charge import ChargeCreate, ChargeUpdate


class ChargeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, charge_id: UUID) -> Charge | None:
        return self.db.query(Charge).filter(Charge.id == charge_id).first()

    def get_by_plan_id(self, plan_id: UUID) -> list[Charge]:
        return self.db.query(Charge).filter(Charge.plan_id == plan_id).all()

    def create(self, plan_id: UUID, data: ChargeCreate) -> Charge:
        charge = Charge(
            plan_id=plan_id,
            billable_metric_id=data.billable_metric_id,
            charge_model=data.charge_model.value,
            properties=data.properties,
        )
        self.db.add(charge)
        self.db.commit()
        self.db.refresh(charge)
        return charge

    def update(self, charge_id: UUID, data: ChargeUpdate) -> Charge | None:
        charge = self.get_by_id(charge_id)
        if not charge:
            return None
        update_data = data.model_dump(exclude_unset=True)
        # Convert enum to string value if present
        if "charge_model" in update_data and update_data["charge_model"] is not None:
            update_data["charge_model"] = update_data["charge_model"].value
        for key, value in update_data.items():
            setattr(charge, key, value)
        self.db.commit()
        self.db.refresh(charge)
        return charge

    def delete(self, charge_id: UUID) -> bool:
        charge = self.get_by_id(charge_id)
        if not charge:
            return False
        self.db.delete(charge)
        self.db.commit()
        return True

    def delete_by_plan_id(self, plan_id: UUID) -> int:
        """Delete all charges for a plan. Returns count of deleted charges."""
        result = self.db.query(Charge).filter(Charge.plan_id == plan_id).delete()
        self.db.commit()
        return result
