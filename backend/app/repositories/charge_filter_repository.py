from uuid import UUID

from sqlalchemy.orm import Session

from app.models.billable_metric_filter import BillableMetricFilter
from app.models.charge_filter import ChargeFilter
from app.models.charge_filter_value import ChargeFilterValue
from app.schemas.charge_filter import ChargeFilterCreate


class ChargeFilterRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, filter_id: UUID) -> ChargeFilter | None:
        return (
            self.db.query(ChargeFilter)
            .filter(ChargeFilter.id == filter_id)
            .first()
        )

    def get_by_charge_id(self, charge_id: UUID) -> list[ChargeFilter]:
        return (
            self.db.query(ChargeFilter)
            .filter(ChargeFilter.charge_id == charge_id)
            .all()
        )

    def get_filter_values(self, charge_filter_id: UUID) -> list[ChargeFilterValue]:
        return (
            self.db.query(ChargeFilterValue)
            .filter(ChargeFilterValue.charge_filter_id == charge_filter_id)
            .all()
        )

    def get_matching_filter(
        self, charge_id: UUID, event_properties: dict[str, str]
    ) -> ChargeFilter | None:
        """Find the ChargeFilter that matches the given event properties.

        For each ChargeFilter on the charge, check if all its filter values
        match the corresponding event property values.
        """
        charge_filters = self.get_by_charge_id(charge_id)
        for cf in charge_filters:
            filter_values = self.get_filter_values(cf.id)  # type: ignore[arg-type]
            if not filter_values:
                continue
            all_match = True
            for fv in filter_values:
                bmf = (
                    self.db.query(BillableMetricFilter)
                    .filter(BillableMetricFilter.id == fv.billable_metric_filter_id)
                    .first()
                )
                if bmf is None:
                    all_match = False
                    break
                if event_properties.get(bmf.key) != fv.value:  # type: ignore[call-overload]
                    all_match = False
                    break
            if all_match:
                return cf
        return None

    def create(self, charge_id: UUID, data: ChargeFilterCreate) -> ChargeFilter:
        charge_filter = ChargeFilter(
            charge_id=charge_id,
            properties=data.properties,
            invoice_display_name=data.invoice_display_name,
        )
        self.db.add(charge_filter)
        self.db.commit()
        self.db.refresh(charge_filter)

        for value_data in data.values:
            cfv = ChargeFilterValue(
                charge_filter_id=charge_filter.id,
                billable_metric_filter_id=value_data.billable_metric_filter_id,
                value=value_data.value,
            )
            self.db.add(cfv)
        self.db.commit()

        return charge_filter

    def delete(self, filter_id: UUID) -> bool:
        charge_filter = self.get_by_id(filter_id)
        if not charge_filter:
            return False
        # Delete associated filter values first
        self.db.query(ChargeFilterValue).filter(
            ChargeFilterValue.charge_filter_id == filter_id
        ).delete()
        self.db.delete(charge_filter)
        self.db.commit()
        return True
