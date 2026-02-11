from collections.abc import Callable
from decimal import Decimal

from app.models.charge import ChargeModel
from app.services.charge_models import (
    graduated,
    graduated_percentage,
    package,
    percentage,
    standard,
    volume,
)

# Calculator functions have varying signatures based on charge model type.
# Using Callable[..., Decimal] to accommodate different parameter requirements:
# - standard, graduated, volume, package: (units, properties)
# - percentage: (units, properties, total_amount, event_count)
# - graduated_percentage: (total_amount, properties)
CalculatorFn = Callable[..., Decimal]

_CALCULATORS: dict[ChargeModel, CalculatorFn] = {
    ChargeModel.STANDARD: standard.calculate,
    ChargeModel.GRADUATED: graduated.calculate,
    ChargeModel.VOLUME: volume.calculate,
    ChargeModel.PACKAGE: package.calculate,
    ChargeModel.PERCENTAGE: percentage.calculate,
    ChargeModel.GRADUATED_PERCENTAGE: graduated_percentage.calculate,
}


def get_charge_calculator(model: ChargeModel) -> CalculatorFn | None:
    return _CALCULATORS.get(model)
