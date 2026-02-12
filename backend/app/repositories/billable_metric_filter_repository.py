from uuid import UUID

from sqlalchemy.orm import Session

from app.models.billable_metric_filter import BillableMetricFilter
from app.schemas.billable_metric_filter import BillableMetricFilterCreate


class BillableMetricFilterRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, filter_id: UUID) -> BillableMetricFilter | None:
        return (
            self.db.query(BillableMetricFilter).filter(BillableMetricFilter.id == filter_id).first()
        )

    def get_by_metric_id(self, billable_metric_id: UUID) -> list[BillableMetricFilter]:
        return (
            self.db.query(BillableMetricFilter)
            .filter(BillableMetricFilter.billable_metric_id == billable_metric_id)
            .all()
        )

    def create(
        self, billable_metric_id: UUID, data: BillableMetricFilterCreate
    ) -> BillableMetricFilter:
        metric_filter = BillableMetricFilter(
            billable_metric_id=billable_metric_id,
            key=data.key,
            values=data.values,
        )
        self.db.add(metric_filter)
        self.db.commit()
        self.db.refresh(metric_filter)
        return metric_filter

    def delete(self, filter_id: UUID) -> bool:
        metric_filter = self.get_by_id(filter_id)
        if not metric_filter:
            return False
        self.db.delete(metric_filter)
        self.db.commit()
        return True
