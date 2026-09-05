from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductFiscalClassification
from app.restaurant.fiscal_product.contracts import (
    FiscalProductClassificationCandidate,
    ResolvedFiscalProductEvidence,
)
from app.restaurant.fiscal_product.errors import (
    FiscalProductEvidenceAmbiguousError,
    FiscalProductEvidenceUnavailableError,
    FiscalProductScopeError,
)


EVIDENCE_SCHEMA_VERSION = 1


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _jurisdiction(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise FiscalProductEvidenceUnavailableError(
            'Fiscal product jurisdiction is unavailable'
        )
    if len(value) > 16:
        raise FiscalProductEvidenceUnavailableError(
            'Fiscal product jurisdiction is invalid'
        )
    return value


async def resolve_fiscal_product_evidence(
    db: AsyncSession,
    candidate: FiscalProductClassificationCandidate,
) -> ResolvedFiscalProductEvidence:
    jurisdiction = _jurisdiction(candidate.fiscal_jurisdiction_code)
    if not isinstance(candidate.effective_at, datetime):
        raise FiscalProductEvidenceUnavailableError(
            'Fiscal product effective instant is invalid'
        )
    effective_at = candidate.effective_at
    if effective_at.tzinfo is not None:
        effective_at = effective_at.astimezone(timezone.utc).replace(tzinfo=None)

    product = await db.scalar(
        select(Product).where(
            Product.id == candidate.product_id,
            Product.tenant_id == candidate.tenant_id,
            Product.organization_id == candidate.organization_id,
        ).with_for_update()
    )
    if product is None:
        raise FiscalProductScopeError('Product was not found in the trusted fiscal scope')
    if (
        product.id != candidate.product_id
        or product.tenant_id != candidate.tenant_id
        or product.organization_id != candidate.organization_id
    ):
        raise FiscalProductScopeError('Product was returned outside the trusted fiscal scope')

    rows = tuple((await db.execute(
        select(ProductFiscalClassification).where(
            ProductFiscalClassification.tenant_id == candidate.tenant_id,
            ProductFiscalClassification.organization_id == candidate.organization_id,
            ProductFiscalClassification.product_id == candidate.product_id,
            ProductFiscalClassification.fiscal_jurisdiction_code == jurisdiction,
            ProductFiscalClassification.status == 'ACTIVE',
            ProductFiscalClassification.effective_from <= effective_at,
            or_(
                ProductFiscalClassification.effective_to.is_(None),
                effective_at < ProductFiscalClassification.effective_to,
            ),
        ).order_by(ProductFiscalClassification.id).with_for_update()
    )).scalars().all())
    for classification in rows:
        if (
            classification.tenant_id != candidate.tenant_id
            or classification.organization_id != candidate.organization_id
            or classification.product_id != candidate.product_id
            or classification.fiscal_jurisdiction_code != jurisdiction
        ):
            raise FiscalProductScopeError(
                'Fiscal product classification was returned outside the trusted scope'
            )
    applicable = tuple(
        classification
        for classification in rows
        if classification.status == 'ACTIVE'
        and classification.effective_from <= effective_at
        and (
            classification.effective_to is None
            or effective_at < classification.effective_to
        )
    )
    if not applicable:
        raise FiscalProductEvidenceUnavailableError(
            'No applicable fiscal product classification was found'
        )
    if len(applicable) != 1:
        raise FiscalProductEvidenceAmbiguousError(
            'Multiple applicable fiscal product classifications were found'
        )

    classification = applicable[0]
    configured_values = (
        classification.fiscal_jurisdiction_code,
        classification.product_classification_scheme,
        classification.product_classification_code,
        classification.unit_classification_scheme,
        classification.unit_classification_code,
    )
    if any(
        not isinstance(value, str) or not value.strip() or value != value.strip()
        for value in configured_values
    ):
        raise FiscalProductEvidenceUnavailableError(
            'Applicable fiscal product classification is incomplete'
        )
    values = {
        'schema_version': EVIDENCE_SCHEMA_VERSION,
        'tenant_id': candidate.tenant_id,
        'organization_id': candidate.organization_id,
        'product_id': candidate.product_id,
        'source_product_fiscal_classification_id': classification.id,
        'fiscal_jurisdiction_code': classification.fiscal_jurisdiction_code,
        'product_classification_scheme': classification.product_classification_scheme,
        'product_classification_code': classification.product_classification_code,
        'unit_classification_scheme': classification.unit_classification_scheme,
        'unit_classification_code': classification.unit_classification_code,
    }
    return ResolvedFiscalProductEvidence(
        source_product_fiscal_classification_id=classification.id,
        fiscal_jurisdiction_code=classification.fiscal_jurisdiction_code,
        product_classification_scheme=classification.product_classification_scheme,
        product_classification_code=classification.product_classification_code,
        unit_classification_scheme=classification.unit_classification_scheme,
        unit_classification_code=classification.unit_classification_code,
        schema_version=EVIDENCE_SCHEMA_VERSION,
        evidence_fingerprint=_fingerprint(values),
    )
