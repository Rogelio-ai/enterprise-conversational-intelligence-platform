from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PreparationWorkItemProjection:
    id: int
    source_restaurant_order_item_id: int | None
    source_restaurant_order_item_component_id: int | None
    required_quantity: Decimal
    route_id: int


@dataclass(frozen=True, slots=True)
class PreparationWorkProjection:
    id: int
    preparation_area_id: int
    area_code: str
    area_name: str
    items: tuple[PreparationWorkItemProjection, ...]


@dataclass(frozen=True, slots=True)
class PreparationRoutingProjection:
    id: int
    restaurant_order_id: int
    preparation_owner: str | None
    state: str
    routing_schema_version: int
    routing_fingerprint: str | None
    error_code: str | None
    error_detail: str | None
    routed_at: datetime | None
    works: tuple[PreparationWorkProjection, ...]
