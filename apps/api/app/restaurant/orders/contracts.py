from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class DraftReadiness(StrEnum):
    EMPTY = 'EMPTY'
    INCOMPLETE = 'INCOMPLETE'
    INVALID = 'INVALID'
    READY = 'READY'


@dataclass(frozen=True, slots=True)
class DraftIssue:
    code: str
    group_id: int | None = None
    option_id: int | None = None
    product_id: int | None = None


@dataclass(frozen=True, slots=True)
class FixedComponentProjection:
    product_id: int
    product_name: str
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class SelectionProjection:
    group_id: int
    group_name: str
    choice_option_id: int
    selected_product_id: int
    selected_product_name: str


@dataclass(frozen=True, slots=True)
class MissingChoiceGroupProjection:
    group_id: int
    group_name: str
    min_selections: int
    max_selections: int
    selected_option_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class DraftItemProjection:
    item_id: int
    product_id: int
    product_name: str
    composition_id: int | None
    quantity: Decimal
    position: int
    readiness: DraftReadiness
    issues: tuple[DraftIssue, ...]
    selections: tuple[SelectionProjection, ...]
    missing_choice_groups: tuple[MissingChoiceGroupProjection, ...]
    fixed_components: tuple[FixedComponentProjection, ...]


@dataclass(frozen=True, slots=True)
class DraftProjection:
    draft_id: int
    tenant_id: int
    organization_id: int
    location_id: int
    conversation_id: int
    version: int
    status: str
    readiness: DraftReadiness
    items: tuple[DraftItemProjection, ...]
