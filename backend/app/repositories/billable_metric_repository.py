from uuid import UUID

from sqlalchemy.orm import Session

from app.models.billable_metric import BillableMetric
from app.schemas.billable_metric import BillableMetricCreate, BillableMetricUpdate


class BillableMetricRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> list[BillableMetric]:
        return self.db.query(BillableMetric).offset(skip).limit(limit).all()

    def get_by_id(self, metric_id: UUID) -> BillableMetric | None:
        return self.db.query(BillableMetric).filter(BillableMetric.id == metric_id).first()

    def get_by_code(self, code: str) -> BillableMetric | None:
        return self.db.query(BillableMetric).filter(BillableMetric.code == code).first()

    def create(self, data: BillableMetricCreate) -> BillableMetric:
        metric = BillableMetric(
            code=data.code,
            name=data.name,
            description=data.description,
            aggregation_type=data.aggregation_type.value,
            field_name=data.field_name,
            recurring=data.recurring,
            rounding_function=data.rounding_function,
            rounding_precision=data.rounding_precision,
            expression=data.expression,
        )
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return metric

    def update(self, metric_id: UUID, data: BillableMetricUpdate) -> BillableMetric | None:
        metric = self.get_by_id(metric_id)
        if not metric:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(metric, key, value)
        self.db.commit()
        self.db.refresh(metric)
        return metric

    def delete(self, metric_id: UUID) -> bool:
        metric = self.get_by_id(metric_id)
        if not metric:
            return False
        self.db.delete(metric)
        self.db.commit()
        return True

    def code_exists(self, code: str) -> bool:
        """Check if a billable metric with the given code already exists."""
        query = self.db.query(BillableMetric).filter(BillableMetric.code == code)
        return query.first() is not None
