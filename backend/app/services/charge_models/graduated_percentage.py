from decimal import Decimal
from typing import Any


def calculate(total_amount: Decimal, properties: dict[str, Any]) -> Decimal:
    ranges = properties.get("graduated_percentage_ranges", [])
    if not ranges:
        return Decimal(0)

    total = Decimal(0)
    remaining = total_amount

    for r in sorted(ranges, key=lambda x: x.get("from_value", 0)):
        if remaining <= 0:
            break

        from_value = Decimal(str(r.get("from_value", 0)))
        to_value = r.get("to_value")
        rate = Decimal(str(r.get("rate", 0)))
        flat = Decimal(str(r.get("flat_amount", 0)))

        if to_value is None:
            portion = remaining
        else:
            tier_capacity = Decimal(str(to_value)) - from_value
            portion = min(remaining, tier_capacity)

        if portion <= 0:
            continue

        total += portion * (rate / Decimal(100)) + flat
        remaining -= portion

    return total
