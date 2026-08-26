from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ProductKnowledge:
    id: int
    organization_id: int
    category_id: int | None
    name: str
    description: str | None


@dataclass(frozen=True, slots=True)
class MenuItemKnowledge:
    id: int
    display_order: int
    product: ProductKnowledge


@dataclass(frozen=True, slots=True)
class MenuSectionKnowledge:
    id: int
    name: str
    display_order: int
    items: tuple[MenuItemKnowledge, ...]


@dataclass(frozen=True, slots=True)
class LocationMenuKnowledge:
    id: int
    organization_id: int
    name: str
    location_ids: tuple[int, ...]
    sections: tuple[MenuSectionKnowledge, ...]


@dataclass(frozen=True, slots=True)
class CurrentPriceKnowledge:
    price_id: int
    product_id: int
    location_id: int
    amount: Decimal
    currency: str
    source: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PromotionCandidateKnowledge:
    promotion_id: int
    name: str
    description: str | None
    promotion_type: str
    benefit_value: Decimal
    currency: str | None
    starts_at: datetime
    ends_at: datetime
    applies_to_all_locations: bool


@dataclass(frozen=True, slots=True)
class FixedComponentKnowledge:
    component_id: int
    product: ProductKnowledge
    quantity: Decimal
    display_order: int


@dataclass(frozen=True, slots=True)
class ChoiceOptionKnowledge:
    option_id: int
    product: ProductKnowledge
    quantity: Decimal
    display_order: int


@dataclass(frozen=True, slots=True)
class ChoiceGroupKnowledge:
    group_id: int
    name: str
    min_selections: int
    max_selections: int
    display_order: int
    options: tuple[ChoiceOptionKnowledge, ...]


@dataclass(frozen=True, slots=True)
class ProductCompositionKnowledge:
    composition_id: int
    product: ProductKnowledge
    fixed_components: tuple[FixedComponentKnowledge, ...]
    choice_groups: tuple[ChoiceGroupKnowledge, ...]
