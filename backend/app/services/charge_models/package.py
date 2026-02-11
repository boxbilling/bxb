import math
from decimal import Decimal


def calculate(units: Decimal, properties: dict) -> Decimal:
    amount = Decimal(str(properties.get("amount", properties.get("unit_price", 0))))
    package_size = Decimal(str(properties.get("package_size", 1)))
    free_units = Decimal(str(properties.get("free_units", 0)))

    billable = max(Decimal(0), units - free_units)
    if billable == 0:
        return Decimal(0)

    packages = Decimal(math.ceil(billable / package_size))
    return packages * amount
