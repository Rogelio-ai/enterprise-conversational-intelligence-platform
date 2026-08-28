from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AcceptedComponent:
    kind: str
    position: int
    source_component_id: int | None
    source_choice_group_id: int | None
    source_choice_option_id: int | None
    choice_group_name: str | None
    product_id: int
    product_name: str
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class AcceptedPromotion:
    promotion_id: int
    application_order: int
    promotion_name: str
    promotion_type: str
    promotion_value: Decimal
    promotion_currency: str | None
    priority: int
    is_combinable: bool
    calculated_discount: Decimal


@dataclass(frozen=True, slots=True)
class AcceptedOrderItem:
    id: int
    source_order_draft_item_id: int
    product_id: int
    product_name: str
    composition_id: int | None
    quantity: Decimal
    position: int
    source_product_price_id: int
    price_source: str
    unit_price: Decimal
    base_amount: Decimal
    discount_amount: Decimal
    commercial_amount: Decimal
    components: tuple[AcceptedComponent, ...]
    promotions: tuple[AcceptedPromotion, ...]


@dataclass(frozen=True, slots=True)
class RestaurantOrderProjection:
    id: int
    status: str
    accepted_at: datetime
    source_order_draft_id: int
    accepted_draft_version: int
    currency: str
    tax_mode: str
    rounding_policy: str
    subtotal: Decimal
    total_discount: Decimal
    pre_round_total: Decimal
    rounding_adjustment: Decimal
    payable_total: Decimal
    items: tuple[AcceptedOrderItem, ...]


@dataclass(frozen=True, slots=True)
class ConfirmationResult:
    order: RestaurantOrderProjection
    replayed: bool
