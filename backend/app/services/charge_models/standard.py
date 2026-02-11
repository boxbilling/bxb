from decimal import Decimal


def calculate(units: Decimal, properties: dict) -> Decimal:
    amount = Decimal(str(properties.get("amount", properties.get("unit_price", 0))))
    return units * amount
