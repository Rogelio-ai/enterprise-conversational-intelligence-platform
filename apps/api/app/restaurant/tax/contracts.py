from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class TaxTreatment(str, Enum):
    TAXABLE = 'TAXABLE'
    ZERO_RATE = 'ZERO_RATE'
    EXEMPT = 'EXEMPT'


class TaxEffect(str, Enum):
    TRANSFERRED = 'TRANSFERRED'
    WITHHELD = 'WITHHELD'


@dataclass(frozen=True, slots=True)
class RestaurantTaxLineCandidate:
    tenant_id: int
    organization_id: int
    location_id: int
    product_id: int
    product_tax_classification_code: str | None
    effective_at: datetime
    tax_mode: str
    quantity: Decimal
    unit_price: Decimal
    base_amount: Decimal
    discount_amount: Decimal
    commercial_amount: Decimal
    component_tax_classification_codes: tuple[str | None, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedTaxEvidence:
    source_tax_rule_id: int
    tax_category: str
    tax_treatment: TaxTreatment
    tax_effect: TaxEffect
    tax_rate: Decimal
    fiscal_unit_value: Decimal
    fiscal_line_amount: Decimal
    fiscal_discount_amount: Decimal
    taxable_base: Decimal
    tax_amount: Decimal
    jurisdiction_code: str
    calculation_policy: str
    rounding_policy: str
    schema_version: int
    evidence_fingerprint: str
