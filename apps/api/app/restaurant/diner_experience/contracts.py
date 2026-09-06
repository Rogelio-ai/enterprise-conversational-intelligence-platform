from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class ExperienceState(StrEnum):
    OK = 'OK'
    CLARIFICATION_REQUIRED = 'CLARIFICATION_REQUIRED'
    PRODUCT_UNAVAILABLE = 'PRODUCT_UNAVAILABLE'
    CONFIGURATION_REQUIRED = 'CONFIGURATION_REQUIRED'
    ACTION_BLOCKED = 'ACTION_BLOCKED'
    STAFF_ASSISTANCE_REQUIRED = 'STAFF_ASSISTANCE_REQUIRED'
    CONTINUATION_REQUIRED = 'CONTINUATION_REQUIRED'
    PAYMENT_UNCERTAIN = 'PAYMENT_UNCERTAIN'
    SESSION_CLOSED = 'SESSION_CLOSED'


@dataclass(frozen=True, slots=True)
class ExperienceGuidance:
    state: ExperienceState
    code: str
    required_input: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    next_action: str | None = None


@dataclass(frozen=True, slots=True)
class DinerPrice:
    amount: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class DinerCategory:
    id: int
    name: str


@dataclass(frozen=True, slots=True)
class DinerProductSummary:
    id: int
    name: str
    description: str | None
    category_path: tuple[DinerCategory, ...]
    price: DinerPrice | None
    orderable: bool
    configuration_available: bool
    configuration_required: bool


@dataclass(frozen=True, slots=True)
class DinerMenuSection:
    id: int
    name: str
    products: tuple[DinerProductSummary, ...]


@dataclass(frozen=True, slots=True)
class DinerMenu:
    id: int
    name: str
    sections: tuple[DinerMenuSection, ...]


@dataclass(frozen=True, slots=True)
class DinerFixedComponent:
    product_id: int
    name: str
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class DinerChoiceOption:
    id: int
    product_id: int
    name: str
    description: str | None
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class DinerChoiceGroup:
    id: int
    name: str
    min_selections: int
    max_selections: int
    required: bool
    options: tuple[DinerChoiceOption, ...]


@dataclass(frozen=True, slots=True)
class DinerProductDetail:
    product: DinerProductSummary
    fixed_components: tuple[DinerFixedComponent, ...]
    choice_groups: tuple[DinerChoiceGroup, ...]


@dataclass(frozen=True, slots=True)
class AccountPreviewLine:
    order_id: int
    order_item_id: int
    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    commercial_amount: Decimal


@dataclass(frozen=True, slots=True)
class DinerAccountPreview:
    diner_session_id: int
    display_name: str
    currency: str | None
    eligible_order_ids: tuple[int, ...]
    lines: tuple[AccountPreviewLine, ...]
    eligible_total: Decimal
    active_check_id: int | None
    has_active_nonempty_draft: bool


@dataclass(frozen=True, slots=True)
class OperationalRequestProjection:
    id: int
    request_type: str
    status: str
    related_restaurant_check_id: int | None
    created_at: datetime
    resolved_at: datetime | None


class ProductUnavailableError(LookupError):
    pass


class OperationalRequestNotFoundError(LookupError):
    pass


class OperationalRequestInvalidError(ValueError):
    pass


class OperationalRequestIdempotencyConflictError(RuntimeError):
    pass
