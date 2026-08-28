from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class CommercialResolutionStatus(StrEnum):
    COMPLETE = 'COMPLETE'


class TaxMode(StrEnum):
    INCLUDED = 'INCLUDED'


@dataclass(frozen=True, slots=True)
class AppliedPromotion:
    promotion_id: int
    name: str
    promotion_type: str
    promotion_value: Decimal
    currency: str | None
    priority: int
    is_combinable: bool
    calculated_discount: Decimal


@dataclass(frozen=True, slots=True)
class CheckoutPreviewLine:
    draft_item_id: int
    product_id: int
    product_name: str
    composition_id: int | None
    quantity: Decimal
    price_id: int
    price_source: str
    unit_price: Decimal
    base_amount: Decimal
    applied_promotions: tuple[AppliedPromotion, ...]
    discount_amount: Decimal
    commercial_amount: Decimal


@dataclass(frozen=True, slots=True)
class CheckoutPreview:
    status: CommercialResolutionStatus
    draft_id: int
    draft_version: int
    tenant_id: int
    organization_id: int
    location_id: int
    resolved_at: datetime
    currency: str
    tax_mode: TaxMode
    rounding_policy: str
    fingerprint_schema_version: int
    lines: tuple[CheckoutPreviewLine, ...]
    subtotal: Decimal
    total_discount: Decimal
    pre_round_total: Decimal
    rounding_adjustment: Decimal
    payable_total: Decimal
    commercial_fingerprint: str
