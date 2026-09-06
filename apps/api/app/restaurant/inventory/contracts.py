from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ConsumptionComponentInput:
    inventory_item_id: int
    quantity: Decimal
    uom: str


@dataclass(frozen=True, slots=True)
class ConsumptionComponentProjection:
    inventory_item_id: int
    inventory_item_code: str
    inventory_item_name: str
    quantity: Decimal
    base_uom: str


@dataclass(frozen=True, slots=True)
class ConsumptionDefinitionProjection:
    id: int
    product_id: int
    location_id: int
    version: int
    status: str
    tracking_mode: str
    components: tuple[ConsumptionComponentProjection, ...]


@dataclass(frozen=True, slots=True)
class StockMovementProjection:
    id: int
    inventory_item_id: int
    location_id: int
    movement_type: str
    quantity: Decimal
    base_uom: str
    reversal_of_movement_id: int | None
    reason: str | None
    reference: str | None
    recorded_at: datetime
    actor_type: str
    actor_id: int | None
    actor_reference: str | None


@dataclass(frozen=True, slots=True)
class StockProjection:
    inventory_item_id: int
    code: str
    name: str
    location_id: int
    base_uom: str
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class CostComponentProjection:
    inventory_item_id: int
    inventory_item_code: str
    inventory_item_name: str
    quantity: Decimal
    base_uom: str
    standard_unit_cost: Decimal
    currency: str
    theoretical_cost: Decimal


@dataclass(frozen=True, slots=True)
class ProductCostProjection:
    product_id: int
    location_id: int
    definition_version: int
    tracking_mode: str
    cost_status: str
    currency: str | None
    components: tuple[CostComponentProjection, ...]
    total_theoretical_cost: Decimal | None
