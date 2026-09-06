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


@dataclass(frozen=True, slots=True)
class OrderConsumptionMovementProjection:
    stock_movement_id: int
    restaurant_order_item_id: int
    restaurant_order_item_component_id: int | None
    source_product_id: int
    inventory_item_id: int
    inventory_item_name: str
    base_uom: str
    consumed_quantity: Decimal
    consumption_definition_version: int
    unit_cost: Decimal
    currency: str
    extended_cost: Decimal


@dataclass(frozen=True, slots=True)
class OrderItemConsumptionProjection:
    restaurant_order_item_id: int
    product_id: int
    product_name: str
    quantity: Decimal
    commercial_amount: Decimal
    coverage_status: str
    unresolved_evidence: tuple[dict[str, object], ...]
    movements: tuple[OrderConsumptionMovementProjection, ...]
    historical_theoretical_cost: Decimal | None
    theoretical_gross_margin: Decimal | None
    theoretical_margin_percent: Decimal | None


@dataclass(frozen=True, slots=True)
class OrderConsumptionProjection:
    restaurant_order_id: int
    currency: str
    coverage_status: str
    schema_version: int
    source_fingerprint: str
    unresolved_evidence: tuple[dict[str, object], ...]
    items: tuple[OrderItemConsumptionProjection, ...]
    commercial_amount: Decimal
    historical_theoretical_cost: Decimal | None
    theoretical_gross_margin: Decimal | None
    theoretical_margin_percent: Decimal | None
