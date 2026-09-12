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
    source_quantity: Decimal | None = None
    source_uom: str | None = None
    conversion_revision_id: int | None = None
    conversion_factor: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ConsumptionDefinitionProjection:
    id: int
    product_id: int
    location_id: int
    version: int
    status: str
    tracking_mode: str
    components: tuple[ConsumptionComponentProjection, ...]
    recipe_version_id: int | None = None
    recipe_revision: int | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    published_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class StockMovementProjection:
    id: int
    inventory_item_id: int
    location_id: int
    warehouse_id: int
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
    negative_stock_policy: str
    negative_stock_warning: bool
    resulting_stock_quantity: Decimal | None
    source_quantity: Decimal | None
    source_uom: str | None
    conversion_revision_id: int | None
    conversion_factor: Decimal | None
    base_uom_evidence: str | None
    standard_cost_revision_id: int | None
    standard_unit_cost_evidence: Decimal | None
    cost_currency_evidence: str | None
    extended_standard_cost: Decimal | None
    evidence_status: str


@dataclass(frozen=True, slots=True)
class ItemUomConversionProjection:
    id: int
    inventory_item_id: int
    operational_uom: str
    base_uom: str
    factor_to_base: Decimal
    revision: int
    effective_at: datetime
    actor_id: int
    reference: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class InventoryCostRevisionProjection:
    id: int
    inventory_item_id: int
    revision: int
    standard_unit_cost: Decimal
    currency: str
    effective_at: datetime
    source: str
    actor_id: int | None
    reference: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StockProjection:
    inventory_item_id: int
    code: str
    name: str
    location_id: int
    warehouse_id: int
    base_uom: str
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class WarehouseProjection:
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    code: str
    name: str
    status: str
    is_default: bool
    negative_stock_policy: str
    version: int
    created_at: datetime
    updated_at: datetime


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
    warehouse_id: int
    restaurant_order_item_id: int
    restaurant_order_item_component_id: int | None
    source_product_id: int
    inventory_item_id: int
    inventory_item_name: str
    base_uom: str
    consumed_quantity: Decimal
    consumption_definition_version: int
    consumption_version_id: int | None
    consumption_version_component_id: int | None
    unit_cost: Decimal
    currency: str
    extended_cost: Decimal
    source_quantity: Decimal | None
    source_uom: str | None
    conversion_revision_id: int | None
    conversion_factor: Decimal | None
    standard_cost_revision_id: int | None
    standard_unit_cost_evidence: Decimal | None
    cost_currency_evidence: str | None
    extended_standard_cost: Decimal | None
    evidence_status: str
    negative_stock_policy: str
    negative_stock_warning: bool
    resulting_stock_quantity: Decimal | None


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
