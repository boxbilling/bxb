from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.charge import Charge
from app.models.charge_filter import ChargeFilter
from app.models.charge_filter_value import ChargeFilterValue
from app.models.plan import Plan
from app.schemas.plan import ChargeInput, PlanCreate, PlanUpdate


class PlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, organization_id: UUID, skip: int = 0, limit: int = 100) -> list[Plan]:
        return (
            self.db.query(Plan)
            .filter(Plan.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, organization_id: UUID) -> int:
        return (
            self.db.query(func.count(Plan.id))
            .filter(Plan.organization_id == organization_id)
            .scalar()
            or 0
        )

    def get_by_id(self, plan_id: UUID, organization_id: UUID | None = None) -> Plan | None:
        query = self.db.query(Plan).filter(Plan.id == plan_id)
        if organization_id is not None:
            query = query.filter(Plan.organization_id == organization_id)
        return query.first()

    def get_by_code(self, code: str, organization_id: UUID) -> Plan | None:
        return (
            self.db.query(Plan)
            .filter(Plan.code == code, Plan.organization_id == organization_id)
            .first()
        )

    def get_charges(self, plan_id: UUID) -> list[Charge]:
        return self.db.query(Charge).filter(Charge.plan_id == plan_id).all()

    def _create_charge_with_filters(self, plan_id: UUID, charge_data: ChargeInput) -> Charge:
        """Create a charge and its associated filters.

        Each filter input creates one ChargeFilter per value, since the
        unique constraint on ChargeFilterValue only allows one value per
        (charge_filter_id, billable_metric_filter_id) combination.
        """
        charge = Charge(
            plan_id=plan_id,
            billable_metric_id=charge_data.billable_metric_id,
            charge_model=charge_data.charge_model.value,
            properties=charge_data.properties,
        )
        self.db.add(charge)
        self.db.flush()

        for filter_input in charge_data.filters:
            for value in filter_input.values:
                charge_filter = ChargeFilter(
                    charge_id=charge.id,
                    properties=filter_input.properties,
                    invoice_display_name=filter_input.invoice_display_name,
                )
                self.db.add(charge_filter)
                self.db.flush()

                cfv = ChargeFilterValue(
                    charge_filter_id=charge_filter.id,
                    billable_metric_filter_id=filter_input.billable_metric_filter_id,
                    value=value,
                )
                self.db.add(cfv)

        return charge

    def create(self, data: PlanCreate, organization_id: UUID) -> Plan:
        plan = Plan(
            code=data.code,
            name=data.name,
            description=data.description,
            interval=data.interval.value,
            amount_cents=data.amount_cents,
            currency=data.currency,
            trial_period_days=data.trial_period_days,
            organization_id=organization_id,
        )
        self.db.add(plan)
        self.db.flush()  # Get the plan ID

        # Create charges with filters
        for charge_data in data.charges:
            self._create_charge_with_filters(plan.id, charge_data)  # type: ignore[arg-type]

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def update(self, plan_id: UUID, data: PlanUpdate, organization_id: UUID) -> Plan | None:
        plan = self.get_by_id(plan_id, organization_id)
        if not plan:
            return None

        # Update plan fields (excluding charges)
        update_data = data.model_dump(exclude_unset=True, exclude={"charges"})
        for key, value in update_data.items():
            setattr(plan, key, value)

        # Handle charges if provided
        if data.charges is not None:
            # Delete existing charge filters and values first
            existing_charges = self.db.query(Charge).filter(Charge.plan_id == plan_id).all()
            for existing_charge in existing_charges:
                existing_filters = (
                    self.db.query(ChargeFilter)
                    .filter(ChargeFilter.charge_id == existing_charge.id)
                    .all()
                )
                for ef in existing_filters:
                    self.db.query(ChargeFilterValue).filter(
                        ChargeFilterValue.charge_filter_id == ef.id
                    ).delete()
                    self.db.delete(ef)
            # Delete existing charges
            self.db.query(Charge).filter(Charge.plan_id == plan_id).delete()

            # Create new charges with filters
            for charge_data in data.charges:
                self._create_charge_with_filters(plan_id, charge_data)

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def delete(self, plan_id: UUID, organization_id: UUID) -> bool:
        plan = self.get_by_id(plan_id, organization_id)
        if not plan:
            return False
        # Charges will be cascade deleted due to FK constraint
        self.db.delete(plan)
        self.db.commit()
        return True

    def code_exists(self, code: str, organization_id: UUID) -> bool:
        """Check if a plan with the given code already exists."""
        query = self.db.query(Plan).filter(
            Plan.code == code, Plan.organization_id == organization_id
        )
        return query.first() is not None
