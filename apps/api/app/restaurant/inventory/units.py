from __future__ import annotations

from decimal import Decimal
from enum import StrEnum


QUANTITY_UNIT = Decimal('0.000001')


class UnitCode(StrEnum):
    KG = 'KG'
    G = 'G'
    L = 'L'
    ML = 'ML'
    UNIT = 'UNIT'
    PORTION = 'PORTION'


_FAMILY = {
    UnitCode.KG: 'MASS',
    UnitCode.G: 'MASS',
    UnitCode.L: 'VOLUME',
    UnitCode.ML: 'VOLUME',
    UnitCode.UNIT: 'UNIT',
    UnitCode.PORTION: 'PORTION',
}
_TO_FAMILY_BASE = {
    UnitCode.KG: Decimal('1000'),
    UnitCode.G: Decimal('1'),
    UnitCode.L: Decimal('1000'),
    UnitCode.ML: Decimal('1'),
    UnitCode.UNIT: Decimal('1'),
    UnitCode.PORTION: Decimal('1'),
}


class UnitConversionError(ValueError):
    pass


def unit_code(value: str | UnitCode) -> UnitCode:
    try:
        return value if isinstance(value, UnitCode) else UnitCode(value.strip().upper())
    except (AttributeError, ValueError) as exc:
        raise UnitConversionError('Unsupported unit of measure') from exc


def exact_quantity(value: Decimal, *, positive: bool = False) -> Decimal:
    if isinstance(value, float) or not isinstance(value, Decimal) or not value.is_finite():
        raise UnitConversionError('Quantity must be an exact Decimal')
    if value != value.quantize(QUANTITY_UNIT):
        raise UnitConversionError('Quantity has more than six decimal places')
    if positive and value <= 0:
        raise UnitConversionError('Quantity must be greater than zero')
    return value


def convert_quantity(
    quantity: Decimal, *, from_uom: str | UnitCode, to_uom: str | UnitCode
) -> Decimal:
    value = exact_quantity(quantity)
    source = unit_code(from_uom)
    target = unit_code(to_uom)
    if _FAMILY[source] != _FAMILY[target]:
        raise UnitConversionError(f'Cannot convert {source.value} to {target.value}')
    normalized = value * _TO_FAMILY_BASE[source] / _TO_FAMILY_BASE[target]
    return exact_quantity(normalized)
