from decimal import Decimal
from typing import Any


def calculate(units: Decimal, properties: dict[str, Any]) -> Decimal:
    ranges = properties.get("graduated_ranges", [])
    if ranges:
        return _calculate_lago_format(units, ranges)

    tiers = properties.get("tiers", [])
    if tiers:
        return _calculate_bxb_format(units, tiers)

    return Decimal(0)


def _calculate_lago_format(units: Decimal, ranges: list[dict[str, Any]]) -> Decimal:
    total = Decimal(0)
    remaining = units

    for r in sorted(ranges, key=lambda x: x.get("from_value", 0)):
        if remaining <= 0:
            break

        from_value = Decimal(str(r.get("from_value", 0)))
        to_value = r.get("to_value")
        per_unit = Decimal(str(r.get("per_unit_amount", 0)))
        flat = Decimal(str(r.get("flat_amount", 0)))

        tier_capacity = remaining if to_value is None else Decimal(str(to_value)) - from_value + 1

        units_in_tier = min(remaining, tier_capacity)
        if units_in_tier <= 0:
            continue

        total += units_in_tier * per_unit + flat
        remaining -= units_in_tier

    return total


def _calculate_bxb_format(units: Decimal, tiers: list[dict[str, Any]]) -> Decimal:
    total = Decimal(0)
    remaining = units
    prev_limit = Decimal(0)

    for tier in sorted(tiers, key=lambda t: t.get("up_to", float("inf"))):
        if remaining <= 0:
            break

        up_to = Decimal(str(tier.get("up_to", float("inf"))))
        tier_price = Decimal(str(tier.get("unit_price", 0)))

        tier_usage = min(remaining, up_to - prev_limit)
        if tier_usage <= 0:
            break

        total += tier_usage * tier_price
        remaining -= tier_usage
        prev_limit = up_to

    return total
