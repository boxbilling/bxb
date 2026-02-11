from collections.abc import Callable

from app.models.charge import ChargeModel
from app.services.charge_models import (
    graduated,
    graduated_percentage,
    package,
    percentage,
    standard,
    volume,
)

_CALCULATORS: dict[ChargeModel, Callable] = {
    ChargeModel.STANDARD: standard.calculate,
    ChargeModel.GRADUATED: graduated.calculate,
    ChargeModel.VOLUME: volume.calculate,
    ChargeModel.PACKAGE: package.calculate,
    ChargeModel.PERCENTAGE: percentage.calculate,
    ChargeModel.GRADUATED_PERCENTAGE: graduated_percentage.calculate,
}


def get_charge_calculator(model: ChargeModel) -> Callable | None:
    return _CALCULATORS.get(model)
