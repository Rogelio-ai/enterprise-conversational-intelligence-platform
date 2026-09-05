from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Product, RestaurantTaxRule
from app.restaurant.tax.contracts import (
    RestaurantTaxLineCandidate,
    ResolvedTaxEvidence,
    TaxEffect,
    TaxTreatment,
)
from app.restaurant.tax.errors import (
    TaxCalculationError,
    TaxClassificationUnavailableError,
    TaxEffectUnsupportedError,
    TaxPolicyUnsupportedError,
    TaxRuleAmbiguousError,
    TaxRuleUnavailableError,
    TaxScopeViolationError,
    TaxTreatmentUnsupportedError,
)


CALCULATION_POLICY = 'INCLUDED_PRICE_SINGLE_TAX'
ROUNDING_POLICY = 'DECIMAL_4_HALF_UP'
EVIDENCE_SCHEMA_VERSION = 2
MONEY_UNIT = Decimal('0.0001')
RATE_UNIT = Decimal('0.000001')
MAX_MONEY = Decimal('999999999999999.9999')
MAX_RATE = Decimal('999.999999')


def _decimal(value: Decimal) -> str:
    return format(value, 'f')


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _money(name: str, value: Decimal, *, positive: bool = False) -> Decimal:
    if isinstance(value, float) or not isinstance(value, Decimal) or not value.is_finite():
        raise TaxCalculationError(f'{name} must be an exact finite Decimal')
    if value < 0 or value > MAX_MONEY or (positive and value == 0):
        qualifier = 'positive' if positive else 'non-negative'
        raise TaxCalculationError(f'{name} must be {qualifier}')
    normalized = value.quantize(MONEY_UNIT, rounding=ROUND_HALF_UP)
    if normalized != value:
        raise TaxCalculationError(f'{name} supports at most four fractional digits')
    return normalized


def _validated_candidate(
    candidate: RestaurantTaxLineCandidate,
) -> tuple[str, dict[str, Decimal]]:
    if candidate.tax_mode != 'INCLUDED':
        raise TaxPolicyUnsupportedError('Only INCLUDED tax mode is supported')

    values = {
        'quantity': _money('quantity', candidate.quantity, positive=True),
        'unit_price': _money('unit_price', candidate.unit_price),
        'base_amount': _money('base_amount', candidate.base_amount),
        'discount_amount': _money('discount_amount', candidate.discount_amount),
        'commercial_amount': _money('commercial_amount', candidate.commercial_amount),
    }
    with localcontext() as context:
        context.prec = 50
        expected_base = values['unit_price'] * values['quantity']
    if values['base_amount'] != expected_base:
        raise TaxCalculationError('base_amount does not match unit_price times quantity')
    if values['discount_amount'] > values['base_amount']:
        raise TaxCalculationError('discount_amount exceeds base_amount')
    if values['commercial_amount'] != values['base_amount'] - values['discount_amount']:
        raise TaxCalculationError(
            'commercial_amount does not match base_amount minus discount_amount'
        )
    return candidate.tax_mode, values


def _classification(candidate: RestaurantTaxLineCandidate) -> str:
    classification = candidate.product_tax_classification_code
    if classification is None or not classification.strip():
        raise TaxClassificationUnavailableError(
            'Product tax classification is required for authoritative resolution'
        )
    if any(value != classification for value in candidate.component_tax_classification_codes):
        raise TaxPolicyUnsupportedError(
            'Priced composition contains incompatible tax classifications'
        )
    return classification


def _rate(rule: RestaurantTaxRule, treatment: TaxTreatment) -> Decimal:
    value = rule.tax_rate
    if isinstance(value, float) or not isinstance(value, Decimal) or not value.is_finite():
        raise TaxCalculationError('Configured tax rate must be an exact finite Decimal')
    if value < 0 or value > MAX_RATE or value.quantize(RATE_UNIT) != value:
        raise TaxCalculationError('Configured tax rate is outside supported precision')
    normalized = value.quantize(RATE_UNIT)
    if treatment is TaxTreatment.TAXABLE and normalized <= 0:
        raise TaxCalculationError('TAXABLE treatment requires a positive configured rate')
    if treatment in (TaxTreatment.ZERO_RATE, TaxTreatment.EXEMPT) and normalized != 0:
        raise TaxCalculationError(f'{treatment.value} treatment requires a zero configured rate')
    return normalized


def _select_rule(
    candidate: RestaurantTaxLineCandidate,
    classification: str,
    effective_at: datetime,
    rules: tuple[RestaurantTaxRule, ...],
) -> RestaurantTaxRule:
    applicable: list[RestaurantTaxRule] = []
    for rule in rules:
        if (
            rule.tenant_id != candidate.tenant_id
            or rule.organization_id != candidate.organization_id
            or rule.tax_classification_code != classification
            or rule.location_id not in (None, candidate.location_id)
        ):
            raise TaxScopeViolationError('Tax rule was returned outside the trusted scope')
        if (
            rule.status == 'ACTIVE'
            and rule.effective_from <= effective_at
            and (rule.effective_to is None or effective_at < rule.effective_to)
        ):
            applicable.append(rule)

    location_rules = [rule for rule in applicable if rule.location_id == candidate.location_id]
    candidates = location_rules or [rule for rule in applicable if rule.location_id is None]
    if not candidates:
        raise TaxRuleUnavailableError('No applicable authoritative tax rule was found')
    if len(candidates) > 1:
        raise TaxRuleAmbiguousError(
            'Multiple equally-precedent authoritative tax rules are applicable'
        )
    return candidates[0]


def _pre_tax(amount: Decimal, tax_rate: Decimal, treatment: TaxTreatment) -> Decimal:
    if treatment in (TaxTreatment.ZERO_RATE, TaxTreatment.EXEMPT):
        return amount
    with localcontext() as context:
        context.prec = 50
        return (amount / (Decimal('1') + tax_rate)).quantize(
            MONEY_UNIT, rounding=ROUND_HALF_UP
        )


def _calculate(
    *, money: dict[str, Decimal], tax_rate: Decimal, treatment: TaxTreatment
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    fiscal_unit_value = _pre_tax(money['unit_price'], tax_rate, treatment)
    fiscal_line_amount = _pre_tax(money['base_amount'], tax_rate, treatment)
    taxable_base = _pre_tax(money['commercial_amount'], tax_rate, treatment)
    fiscal_discount_amount = fiscal_line_amount - taxable_base
    tax_amount = money['commercial_amount'] - taxable_base
    if (
        fiscal_unit_value < 0
        or fiscal_line_amount < 0
        or fiscal_discount_amount < 0
        or taxable_base < 0
        or tax_amount < 0
        or fiscal_line_amount - fiscal_discount_amount != taxable_base
        or taxable_base + tax_amount != money['commercial_amount']
    ):
        raise TaxCalculationError('Included-price tax decomposition is inconsistent')
    return (
        fiscal_unit_value,
        fiscal_line_amount,
        fiscal_discount_amount,
        taxable_base,
        tax_amount,
    )


async def resolve_tax_evidence(
    db: AsyncSession,
    candidate: RestaurantTaxLineCandidate,
) -> ResolvedTaxEvidence:
    classification = _classification(candidate)
    tax_mode, money = _validated_candidate(candidate)
    if not isinstance(candidate.effective_at, datetime):
        raise TaxCalculationError('effective_at must be a datetime')
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
        raise TaxScopeViolationError('Product was not found in the trusted scope')
    if product.tax_classification_code is None:
        raise TaxClassificationUnavailableError(
            'Persisted Product tax classification is unavailable'
        )
    if product.tax_classification_code != classification:
        raise TaxScopeViolationError(
            'Candidate tax classification does not match the persisted Product'
        )

    location = await db.scalar(
        select(Location).where(
            Location.id == candidate.location_id,
            Location.tenant_id == candidate.tenant_id,
            Location.organization_id == candidate.organization_id,
        ).with_for_update()
    )
    if location is None:
        raise TaxScopeViolationError('Location was not found in the trusted scope')

    result = await db.execute(
        select(RestaurantTaxRule)
        .where(
            RestaurantTaxRule.tenant_id == candidate.tenant_id,
            RestaurantTaxRule.organization_id == candidate.organization_id,
            RestaurantTaxRule.tax_classification_code == classification,
            RestaurantTaxRule.status == 'ACTIVE',
            RestaurantTaxRule.effective_from <= effective_at,
            or_(
                RestaurantTaxRule.effective_to.is_(None),
                effective_at < RestaurantTaxRule.effective_to,
            ),
            or_(
                RestaurantTaxRule.location_id == candidate.location_id,
                RestaurantTaxRule.location_id.is_(None),
            ),
        )
        .order_by(RestaurantTaxRule.id)
        .with_for_update()
    )
    rule = _select_rule(
        candidate, classification, effective_at, tuple(result.scalars().all())
    )

    if rule.calculation_policy != CALCULATION_POLICY:
        raise TaxPolicyUnsupportedError('Configured tax calculation policy is unsupported')
    if rule.rounding_policy != ROUNDING_POLICY:
        raise TaxPolicyUnsupportedError('Configured tax rounding policy is unsupported')
    try:
        treatment = TaxTreatment(rule.tax_treatment)
    except (TypeError, ValueError) as exc:
        raise TaxTreatmentUnsupportedError('Configured tax treatment is unsupported') from exc
    try:
        tax_effect = TaxEffect(rule.tax_effect)
    except (TypeError, ValueError) as exc:
        raise TaxEffectUnsupportedError('Configured tax effect is unsupported') from exc
    if tax_effect is not TaxEffect.TRANSFERRED:
        raise TaxEffectUnsupportedError(
            'Configured tax effect has no supported calculation policy'
        )
    tax_rate = _rate(rule, treatment)
    (
        fiscal_unit_value,
        fiscal_line_amount,
        fiscal_discount_amount,
        taxable_base,
        tax_amount,
    ) = _calculate(
        money=money, tax_rate=tax_rate, treatment=treatment
    )

    fingerprint = _fingerprint(
        {
            'schema_version': EVIDENCE_SCHEMA_VERSION,
            'tenant_id': candidate.tenant_id,
            'organization_id': candidate.organization_id,
            'location_id': candidate.location_id,
            'product_id': candidate.product_id,
            'tax_classification_code': classification,
            'tax_mode': tax_mode,
            'quantity': _decimal(money['quantity']),
            'unit_price': _decimal(money['unit_price']),
            'base_amount': _decimal(money['base_amount']),
            'discount_amount': _decimal(money['discount_amount']),
            'commercial_amount': _decimal(money['commercial_amount']),
            'component_tax_classification_codes': list(
                candidate.component_tax_classification_codes
            ),
            'source_tax_rule_id': rule.id,
            'tax_category': rule.tax_category,
            'tax_treatment': treatment.value,
            'tax_effect': tax_effect.value,
            'tax_rate': _decimal(tax_rate),
            'fiscal_unit_value': _decimal(fiscal_unit_value),
            'fiscal_line_amount': _decimal(fiscal_line_amount),
            'fiscal_discount_amount': _decimal(fiscal_discount_amount),
            'taxable_base': _decimal(taxable_base),
            'tax_amount': _decimal(tax_amount),
            'jurisdiction_code': rule.jurisdiction_code,
            'calculation_policy': rule.calculation_policy,
            'rounding_policy': rule.rounding_policy,
        }
    )
    return ResolvedTaxEvidence(
        source_tax_rule_id=rule.id,
        tax_category=rule.tax_category,
        tax_treatment=treatment,
        tax_effect=tax_effect,
        tax_rate=tax_rate,
        fiscal_unit_value=fiscal_unit_value,
        fiscal_line_amount=fiscal_line_amount,
        fiscal_discount_amount=fiscal_discount_amount,
        taxable_base=taxable_base,
        tax_amount=tax_amount,
        jurisdiction_code=rule.jurisdiction_code,
        calculation_policy=rule.calculation_policy,
        rounding_policy=rule.rounding_policy,
        schema_version=EVIDENCE_SCHEMA_VERSION,
        evidence_fingerprint=fingerprint,
    )
