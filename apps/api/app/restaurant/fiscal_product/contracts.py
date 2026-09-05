from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FiscalProductClassificationCandidate:
    tenant_id: int
    organization_id: int
    product_id: int
    fiscal_jurisdiction_code: str
    effective_at: datetime


@dataclass(frozen=True, slots=True)
class ResolvedFiscalProductEvidence:
    source_product_fiscal_classification_id: int
    fiscal_jurisdiction_code: str
    product_classification_scheme: str
    product_classification_code: str
    unit_classification_scheme: str
    unit_classification_code: str
    schema_version: int
    evidence_fingerprint: str
