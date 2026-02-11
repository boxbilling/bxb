from decimal import Decimal
from typing import Any


def calculate(units: Decimal, properties: dict[str, Any]) -> Decimal:
    ranges = properties.get("volume_ranges", [])
    if ranges:
        return _calculate_lago_format(units, ranges)

    tiers = properties.get("tiers", [])
    if tiers:
        return _calculate_bxb_format(units, tiers)

    return Decimal(0)


def _calculate_lago_format(units: Decimal, ranges: list[dict[str, Any]]) -> Decimal:
    for r in sorted(ranges, key=lambda x: x.get("from_value", 0)):
        to_value = r.get("to_value")
        if to_value is None or units <= Decimal(str(to_value)):
            per_unit = Decimal(str(r.get("per_unit_amount", 0)))
            flat = Decimal(str(r.get("flat_amount", 0)))
            return units * per_unit + flat

    # If exceeds all tiers, use the last tier
    last = sorted(ranges, key=lambda x: x.get("from_value", 0))[-1]
    per_unit = Decimal(str(last.get("per_unit_amount", 0)))
    flat = Decimal(str(last.get("flat_amount", 0)))
    return units * per_unit + flat


def _calculate_bxb_format(units: Decimal, tiers: list[dict[str, Any]]) -> Decimal:
    for tier in sorted(tiers, key=lambda t: t.get("up_to", float("inf"))):
        up_to = Decimal(str(tier.get("up_to", float("inf"))))
        if units <= up_to:
            tier_price = Decimal(str(tier.get("unit_price", 0)))
            flat = Decimal(str(tier.get("flat_amount", 0)))
            return units * tier_price + flat

    # If exceeds all tiers, use the last tier
    last = sorted(tiers, key=lambda t: t.get("up_to", float("inf")))[-1]
    tier_price = Decimal(str(last.get("unit_price", 0)))
    flat = Decimal(str(last.get("flat_amount", 0)))
    return units * tier_price + flat
