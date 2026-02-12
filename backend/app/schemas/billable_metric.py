from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.billable_metric import AggregationType


class BillableMetricCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    aggregation_type: AggregationType
    field_name: str | None = Field(default=None, max_length=255)
    recurring: bool = False
    rounding_function: Literal["round", "ceil", "floor"] | None = None
    rounding_precision: int | None = Field(default=None, ge=0, le=15)
    expression: str | None = None

    @model_validator(mode="after")
    def validate_field_name_required(self) -> Self:
        """Validate field_name is provided for aggregation types that need it."""
        requires_field = (
            AggregationType.SUM,
            AggregationType.MAX,
            AggregationType.UNIQUE_COUNT,
            AggregationType.WEIGHTED_SUM,
            AggregationType.LATEST,
        )
        if self.aggregation_type in requires_field and not self.field_name:
            msg = f"field_name is required for aggregation_type '{self.aggregation_type.value}'"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_expression_required(self) -> Self:
        """Validate expression is provided for CUSTOM aggregation type."""
        if self.aggregation_type == AggregationType.CUSTOM and not self.expression:
            msg = "expression is required for aggregation_type 'custom'"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_recurring_aggregation_types(self) -> Self:
        """Validate recurring is only used with compatible aggregation types."""
        allowed_recurring = (
            AggregationType.COUNT,
            AggregationType.MAX,
            AggregationType.LATEST,
        )
        if self.recurring and self.aggregation_type not in allowed_recurring:
            msg = "recurring is only supported for aggregation types: count, max, latest"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_rounding_precision_requires_function(self) -> Self:
        """Validate rounding_precision requires rounding_function."""
        if self.rounding_precision is not None and self.rounding_function is None:
            msg = "rounding_precision requires rounding_function to be set"
            raise ValueError(msg)
        return self


class BillableMetricUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    field_name: str | None = Field(default=None, max_length=255)
    recurring: bool | None = None
    rounding_function: Literal["round", "ceil", "floor"] | None = None
    rounding_precision: int | None = Field(default=None, ge=0, le=15)
    expression: str | None = None


class BillableMetricResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    aggregation_type: AggregationType
    field_name: str | None
    recurring: bool
    rounding_function: str | None
    rounding_precision: int | None
    expression: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
