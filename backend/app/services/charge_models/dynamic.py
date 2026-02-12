from decimal import Decimal
from typing import Any


def calculate(
    events: list[dict[str, Any]],
    properties: dict[str, Any],
) -> Decimal:
    """Dynamic charge: pricing derived from event properties.

    Each event is expected to have price and quantity fields.
    The charge properties specify which event property fields to use:
        price_field: Name of the event property containing the unit price (default: "unit_price")
        quantity_field: Name of the event property containing the quantity (default: "quantity")

    Returns:
        Sum of (price * quantity) across all events.
    """
    price_field = str(properties.get("price_field", "unit_price"))
    quantity_field = str(properties.get("quantity_field", "quantity"))

    total = Decimal(0)
    for event in events:
        price = Decimal(str(event.get(price_field, 0)))
        quantity = Decimal(str(event.get(quantity_field, 0)))
        total += price * quantity

    return total
