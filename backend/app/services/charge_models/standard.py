from decimal import Decimal
from typing import Any


def calculate(units: Decimal, properties: dict[str, Any]) -> Decimal:
    amount = Decimal(str(properties.get("amount", properties.get("unit_price", 0))))
    return units * amount
