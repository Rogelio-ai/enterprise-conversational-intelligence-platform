from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.models import Location, Product, RestaurantTaxRule
from app.restaurant.tax.contracts import (
    RestaurantTaxLineCandidate,
    TaxEffect,
    TaxTreatment,
)
from app.restaurant.tax.errors import (
    TaxClassificationUnavailableError,
    TaxEffectUnsupportedError,
    TaxPolicyUnsupportedError,
    TaxRuleAmbiguousError,
    TaxRuleUnavailableError,
)
from app.restaurant.tax.service import (
    CALCULATION_POLICY,
    ROUNDING_POLICY,
    resolve_tax_evidence,
)


NOW = datetime(2026, 9, 3, 18, 0, 0)


class _Scalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _Scalars(self._values)


class FakeSession:
    def __init__(self, *, product=None, location=None, rules=()):
        self._scalar_values = [product, location]
        self._rules = rules
        self.read_count = 0

    async def scalar(self, statement):
        self.read_count += 1
        return self._scalar_values.pop(0)

    async def execute(self, statement):
        self.read_count += 1
        return _Result(self._rules)


def _product(classification: str | None = 'FOOD') -> Product:
    return Product(
        id=40,
        tenant_id=10,
        organization_id=20,
        tax_classification_code=classification,
    )


def _location() -> Location:
    return Location(id=30, tenant_id=10, organization_id=20)


def _rule(
    rule_id: int,
    *,
    location_id: int | None = None,
    treatment: str = 'TAXABLE',
    rate: str = '0.160000',
    effective_from: datetime = NOW - timedelta(days=1),
    effective_to: datetime | None = None,
    calculation_policy: str = CALCULATION_POLICY,
    rounding_policy: str = ROUNDING_POLICY,
    effect: str | None = 'TRANSFERRED',
) -> RestaurantTaxRule:
    return RestaurantTaxRule(
        id=rule_id,
        tenant_id=10,
        organization_id=20,
        location_id=location_id,
        tax_classification_code='FOOD',
        jurisdiction_code='JURISDICTION-A',
        tax_category='SALES_TAX',
        tax_treatment=treatment,
        tax_effect=effect,
        tax_rate=Decimal(rate),
        calculation_policy=calculation_policy,
        rounding_policy=rounding_policy,
        effective_from=effective_from,
        effective_to=effective_to,
        status='ACTIVE',
    )


def _candidate(
    *,
    classification: str | None = 'FOOD',
    effective_at: datetime = NOW,
    amount: str = '116.0000',
    quantity: str = '1.0000',
    unit_price: str | None = None,
    discount: str = '0.0000',
) -> RestaurantTaxLineCandidate:
    base_amount = Decimal(amount)
    quantity_value = Decimal(quantity)
    unit_price_value = (
        Decimal(unit_price) if unit_price is not None else base_amount / quantity_value
    )
    discount_amount = Decimal(discount)
    return RestaurantTaxLineCandidate(
        tenant_id=10,
        organization_id=20,
        location_id=30,
        product_id=40,
        product_tax_classification_code=classification,
        effective_at=effective_at,
        tax_mode='INCLUDED',
        quantity=quantity_value,
        unit_price=unit_price_value,
        base_amount=base_amount,
        discount_amount=discount_amount,
        commercial_amount=base_amount - discount_amount,
    )


def _resolve(candidate=None, *, rules=(), product=None):
    session = FakeSession(
        product=product if product is not None else _product(),
        location=_location(),
        rules=rules,
    )
    evidence = asyncio.run(resolve_tax_evidence(session, candidate or _candidate()))
    return evidence, session


def test_missing_product_tax_classification_fails_closed_before_reads() -> None:
    session = FakeSession()
    with pytest.raises(TaxClassificationUnavailableError):
        asyncio.run(resolve_tax_evidence(session, _candidate(classification=None)))
    assert session.read_count == 0


def test_missing_applicable_rule_fails_closed() -> None:
    with pytest.raises(TaxRuleUnavailableError):
        _resolve(rules=())


def test_location_rule_overrides_organization_default() -> None:
    evidence, _ = _resolve(rules=(_rule(1), _rule(2, location_id=30, rate='0.100000')))
    assert evidence.source_tax_rule_id == 2
    assert evidence.tax_rate == Decimal('0.100000')


def test_organization_default_is_used_without_location_override() -> None:
    evidence, _ = _resolve(rules=(_rule(1),))
    assert evidence.source_tax_rule_id == 1


def test_effective_from_boundary_is_inclusive() -> None:
    evidence, _ = _resolve(rules=(_rule(1, effective_from=NOW),))
    assert evidence.source_tax_rule_id == 1


def test_effective_to_boundary_is_exclusive() -> None:
    with pytest.raises(TaxRuleUnavailableError):
        _resolve(rules=(_rule(1, effective_to=NOW),))


def test_ambiguous_same_precedence_rules_fail_closed() -> None:
    with pytest.raises(TaxRuleAmbiguousError):
        _resolve(rules=(_rule(1, location_id=30), _rule(2, location_id=30)))


def test_taxable_included_price_has_deterministic_base_and_tax() -> None:
    evidence, _ = _resolve(rules=(_rule(1),))
    assert evidence.tax_treatment is TaxTreatment.TAXABLE
    assert evidence.tax_effect is TaxEffect.TRANSFERRED
    assert evidence.tax_rate == Decimal('0.160000')
    assert evidence.fiscal_unit_value == Decimal('100.0000')
    assert evidence.fiscal_line_amount == Decimal('100.0000')
    assert evidence.fiscal_discount_amount == Decimal('0.0000')
    assert evidence.taxable_base == Decimal('100.0000')
    assert evidence.tax_amount == Decimal('16.0000')
    assert evidence.taxable_base + evidence.tax_amount == Decimal('116.0000')


def test_zero_rate_preserves_taxable_basis_and_produces_zero_tax() -> None:
    evidence, _ = _resolve(
        _candidate(amount='100.0000'),
        rules=(_rule(1, treatment='ZERO_RATE', rate='0.000000'),),
    )
    assert evidence.tax_treatment is TaxTreatment.ZERO_RATE
    assert evidence.fiscal_unit_value == Decimal('100.0000')
    assert evidence.fiscal_line_amount == Decimal('100.0000')
    assert evidence.fiscal_discount_amount == Decimal('0.0000')
    assert evidence.taxable_base == Decimal('100.0000')
    assert evidence.tax_amount == Decimal('0.0000')


def test_exempt_preserves_explicit_treatment_and_produces_zero_tax() -> None:
    evidence, _ = _resolve(
        _candidate(amount='100.0000'),
        rules=(_rule(1, treatment='EXEMPT', rate='0.000000'),),
    )
    assert evidence.tax_treatment is TaxTreatment.EXEMPT
    assert evidence.fiscal_unit_value == Decimal('100.0000')
    assert evidence.fiscal_line_amount == Decimal('100.0000')
    assert evidence.fiscal_discount_amount == Decimal('0.0000')
    assert evidence.taxable_base == Decimal('100.0000')
    assert evidence.tax_amount == Decimal('0.0000')


@pytest.mark.parametrize(
    ('rule', 'message'),
    [
        (_rule(1, calculation_policy='UNKNOWN'), 'calculation'),
        (_rule(1, rounding_policy='UNKNOWN'), 'rounding'),
    ],
)
def test_unsupported_calculation_or_rounding_policy_fails_closed(rule, message) -> None:
    with pytest.raises(TaxPolicyUnsupportedError, match=message):
        _resolve(rules=(rule,))


def test_tax_rate_comes_from_rule_and_is_not_inferred_from_gross() -> None:
    first, _ = _resolve(rules=(_rule(1, rate='0.100000'),))
    second, _ = _resolve(rules=(_rule(2, rate='0.250000'),))
    assert first.tax_rate == Decimal('0.100000')
    assert first.tax_amount != second.tax_amount


def test_discounted_included_price_freezes_pre_tax_fiscal_values() -> None:
    evidence, _ = _resolve(
        _candidate(amount='116.0000', discount='11.6000'), rules=(_rule(1),)
    )
    assert evidence.fiscal_unit_value == Decimal('100.0000')
    assert evidence.fiscal_line_amount == Decimal('100.0000')
    assert evidence.fiscal_discount_amount == Decimal('10.0000')
    assert evidence.taxable_base == Decimal('90.0000')
    assert evidence.fiscal_line_amount - evidence.fiscal_discount_amount == (
        evidence.taxable_base
    )


def test_quantity_greater_than_one_preserves_deterministic_fiscal_unit_value() -> None:
    candidate = _candidate(
        amount='348.0000', quantity='3.0000', unit_price='116.0000'
    )
    first, _ = _resolve(candidate, rules=(_rule(1),))
    second, _ = _resolve(candidate, rules=(_rule(1),))
    assert first.fiscal_unit_value == Decimal('100.0000')
    assert first.fiscal_line_amount == Decimal('300.0000')
    assert first == second


def test_fingerprint_changes_with_fiscal_monetary_evidence() -> None:
    undiscounted, _ = _resolve(
        _candidate(amount='116.0000'), rules=(_rule(1),)
    )
    discounted, _ = _resolve(
        _candidate(amount='232.0000', discount='116.0000'), rules=(_rule(1),)
    )
    assert undiscounted.taxable_base == discounted.taxable_base
    assert undiscounted.fiscal_line_amount != discounted.fiscal_line_amount
    assert undiscounted.fiscal_discount_amount != discounted.fiscal_discount_amount
    assert undiscounted.evidence_fingerprint != discounted.evidence_fingerprint


@pytest.mark.parametrize('effect', [None, 'INVALID', 'WITHHELD'])
def test_missing_invalid_or_uncalculable_tax_effect_fails_closed(effect) -> None:
    with pytest.raises(TaxEffectUnsupportedError):
        _resolve(rules=(_rule(1, effect=effect),))


def test_output_fingerprint_is_deterministic_and_evidence_is_immutable() -> None:
    first, _ = _resolve(rules=(_rule(1),))
    second, _ = _resolve(rules=(_rule(1),))
    assert first.evidence_fingerprint == second.evidence_fingerprint
    assert len(first.evidence_fingerprint) == 64
    with pytest.raises(FrozenInstanceError):
        first.tax_amount = Decimal('0.0000')


def test_resolver_performs_reads_only_and_does_not_modify_other_domains() -> None:
    _, session = _resolve(rules=(_rule(1),))
    assert session.read_count == 3
    assert not hasattr(session, 'add')
    assert not hasattr(session, 'commit')


def test_incompatible_component_tax_classification_fails_closed() -> None:
    candidate = _candidate()
    incompatible = RestaurantTaxLineCandidate(
        **{
            field: getattr(candidate, field)
            for field in candidate.__dataclass_fields__
            if field != 'component_tax_classification_codes'
        },
        component_tax_classification_codes=('FOOD', 'OTHER'),
    )
    with pytest.raises(TaxPolicyUnsupportedError, match='composition'):
        _resolve(incompatible, rules=(_rule(1),))
