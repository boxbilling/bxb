from decimal import Decimal
from typing import Any


def calculate(units: Decimal, properties: dict[str, Any]) -> Decimal:
    """Custom charge based on a configured fixed amount or per-unit amount.

    Properties:
        custom_amount: A fixed total amount for the charge
        unit_price: Per-unit price applied to the aggregated usage
    """
    custom_amount = properties.get("custom_amount")
    if custom_amount is not None:
        return Decimal(str(custom_amount))

    unit_price = Decimal(str(properties.get("unit_price", 0)))
    return units * unit_price
