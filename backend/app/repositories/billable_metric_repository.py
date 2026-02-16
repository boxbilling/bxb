from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.sorting import apply_order_by
from app.models.billable_metric import BillableMetric
from app.models.charge import Charge
from app.schemas.billable_metric import BillableMetricCreate, BillableMetricUpdate


class BillableMetricRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(
        self,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[BillableMetric]:
        query = (
            self.db.query(BillableMetric)
            .filter(BillableMetric.organization_id == organization_id)
        )
        query = apply_order_by(query, BillableMetric, order_by)
        return query.offset(skip).limit(limit).all()

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

    def counts_by_aggregation_type(self, organization_id: UUID) -> dict[str, int]:
        """Return counts of metrics grouped by aggregation_type."""
        rows = (
            self.db.query(
                BillableMetric.aggregation_type, func.count(BillableMetric.id)
            )
            .filter(BillableMetric.organization_id == organization_id)
            .group_by(BillableMetric.aggregation_type)
            .all()
        )
        return {str(agg_type): int(cnt) for agg_type, cnt in rows}

    def plan_counts(self, organization_id: UUID) -> dict[str, int]:
        """Return a mapping of billable_metric_id -> count of distinct plans using it."""
        rows = (
            self.db.query(
                Charge.billable_metric_id,
                func.count(func.distinct(Charge.plan_id)),
            )
            .filter(Charge.organization_id == organization_id)
            .group_by(Charge.billable_metric_id)
            .all()
        )
        return {str(metric_id): int(cnt) for metric_id, cnt in rows}

    def code_exists(self, code: str, organization_id: UUID) -> bool:
        """Check if a billable metric with the given code already exists."""
        query = self.db.query(BillableMetric).filter(
            BillableMetric.code == code,
            BillableMetric.organization_id == organization_id,
        )
        return query.first() is not None
