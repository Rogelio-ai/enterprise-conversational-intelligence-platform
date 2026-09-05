from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CreateBillingDocumentCommand:
    restaurant_check_id: int
    organization_id: int
    location_id: int
    issuer_fiscal_profile_id: int
    recipient_fiscal_profile_id: int
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class BillingDocumentProjection:
    id: int
    tenant_id: int
    organization_id: int
    location_id: int
    restaurant_check_id: int
    source_check_version: int
    source_check_fingerprint: str
    document_type: str
    status: str
    currency: str
    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    issuer_snapshot: dict
    recipient_snapshot: dict
    issuer_fiscal_postal_code: str | None
    readiness_evidence_fingerprint: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class BillingDocumentLineTaxProjection:
    id: int
    tax_category: str
    tax_rate: Decimal
    taxable_base: Decimal
    tax_amount: Decimal
    tax_treatment: str
    jurisdiction_code: str | None
    tax_effect: str | None
    source_tax_evidence_fingerprint: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BillingDocumentLineProjection:
    id: int
    source_restaurant_order_id: int
    source_restaurant_order_item_id: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    base_amount: Decimal
    discount_amount: Decimal
    commercial_total: Decimal
    fiscal_product_classification_scheme: str | None
    fiscal_product_classification_code: str | None
    fiscal_unit_classification_scheme: str | None
    fiscal_unit_classification_code: str | None
    fiscal_unit_value: Decimal | None
    fiscal_line_amount: Decimal | None
    fiscal_discount_amount: Decimal | None
    source_fiscal_evidence_fingerprint: str | None
    created_at: datetime
    taxes: tuple[BillingDocumentLineTaxProjection, ...]


@dataclass(frozen=True, slots=True)
class BillingDocumentDetailProjection(BillingDocumentProjection):
    lines: tuple[BillingDocumentLineProjection, ...]
