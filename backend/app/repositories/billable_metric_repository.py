from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billable_metric import BillableMetric
from app.schemas.billable_metric import BillableMetricCreate, BillableMetricUpdate


class BillableMetricRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> list[BillableMetric]:
        return (
            self.db.query(BillableMetric)
            .filter(BillableMetric.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, organization_id: UUID) -> int:
        return (
            self.db.query(func.count(BillableMetric.id))
            .filter(BillableMetric.organization_id == organization_id)
            .scalar()
            or 0
        )

    def get_by_id(
        self, metric_id: UUID, organization_id: UUID | None = None
    ) -> BillableMetric | None:
        query = self.db.query(BillableMetric).filter(BillableMetric.id == metric_id)
        if organization_id is not None:
            query = query.filter(BillableMetric.organization_id == organization_id)
        return query.first()

    def get_by_code(self, code: str, organization_id: UUID) -> BillableMetric | None:
        return (
            self.db.query(BillableMetric)
            .filter(
                BillableMetric.code == code,
                BillableMetric.organization_id == organization_id,
            )
            .first()
        )

    def create(self, data: BillableMetricCreate, organization_id: UUID) -> BillableMetric:
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
            organization_id=organization_id,
        )
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return metric

    def update(
        self, metric_id: UUID, data: BillableMetricUpdate, organization_id: UUID
    ) -> BillableMetric | None:
        metric = self.get_by_id(metric_id, organization_id)
        if not metric:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(metric, key, value)
        self.db.commit()
        self.db.refresh(metric)
        return metric

    def delete(self, metric_id: UUID, organization_id: UUID) -> bool:
        metric = self.get_by_id(metric_id, organization_id)
        if not metric:
            return False
        self.db.delete(metric)
        self.db.commit()
        return True

    def code_exists(self, code: str, organization_id: UUID) -> bool:
        """Check if a billable metric with the given code already exists."""
        query = self.db.query(BillableMetric).filter(
            BillableMetric.code == code,
            BillableMetric.organization_id == organization_id,
        )
        return query.first() is not None
