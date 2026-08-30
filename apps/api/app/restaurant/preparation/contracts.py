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


@dataclass(frozen=True, slots=True)
class PreparationOrderContextProjection:
    restaurant_order_id: int
    accepted_at: datetime
    source_channel: str
    resource_id: int
    service_session_id: int
    diner_session_id: int
    current_resource_code: str | None
    current_resource_name: str | None


@dataclass(frozen=True, slots=True)
class PreparationExecutionItemProjection:
    id: int
    preparation_work_id: int
    source_type: str
    source_restaurant_order_item_id: int | None
    source_restaurant_order_item_component_id: int | None
    product_name: str
    parent_product_name: str | None
    required_quantity: Decimal
    execution_state: str
    execution_version: int


@dataclass(frozen=True, slots=True)
class PreparationExecutionWorkProjection:
    id: int
    preparation_area_id: int
    area_code: str
    area_name: str
    routed_at: datetime
    execution_state: str
    order: PreparationOrderContextProjection
    items: tuple[PreparationExecutionItemProjection, ...]


@dataclass(frozen=True, slots=True)
class PreparationItemTransitionProjection:
    id: int
    sequence: int
    from_state: str
    to_state: str
    actor_type: str
    actor_membership_id: int | None
    actor_principal_reference: str | None
    correlation_id: str | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class PreparationItemDetailProjection:
    item: PreparationExecutionItemProjection
    transitions: tuple[PreparationItemTransitionProjection, ...]


@dataclass(frozen=True, slots=True)
class PreparationTransitionResult:
    transition: PreparationItemTransitionProjection
    current_execution_state: str
    current_execution_version: int
    replayed: bool
