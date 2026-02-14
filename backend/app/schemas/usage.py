from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BillableMetricUsage(BaseModel):
    code: str
    name: str
    aggregation_type: str


class ChargeUsage(BaseModel):
    billable_metric: BillableMetricUsage
    units: Decimal
    amount_cents: Decimal
    charge_model: str
    filters: dict[str, str]


class CurrentUsageResponse(BaseModel):
    from_datetime: datetime
    to_datetime: datetime
    amount_cents: Decimal
    currency: str
    charges: list[ChargeUsage]
