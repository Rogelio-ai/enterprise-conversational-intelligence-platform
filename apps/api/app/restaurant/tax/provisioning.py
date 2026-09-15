"""Canonical provisioning authority for effective Restaurant Tax Rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Organization, RestaurantTaxRule
from app.restaurant.tax import service as tax_service
from app.restaurant.tax.contracts import TaxEffect, TaxTreatment


class TaxRuleProvisioningError(ValueError):
    pass


class TaxRuleScopeError(TaxRuleProvisioningError):
    pass


class TaxRuleConflictError(TaxRuleProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class TaxRuleProvisioningPlan:
    operation: str
    rule_id: int | None
    expected_state: tuple[object, ...] | None


@dataclass(frozen=True, slots=True)
class TaxRuleProvisioningResult:
    rule: RestaurantTaxRule
    operation: str


def _text(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise TaxRuleProvisioningError(f'Invalid {field}')
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise TaxRuleProvisioningError(f'Invalid {field}')
    return normalized


def _choice(value: object, *, field: str, allowed: frozenset[str]) -> str:
    normalized = _text(value, field=field, maximum=64).upper()
    if normalized not in allowed:
        raise TaxRuleProvisioningError(f'Unsupported {field}')
    return normalized


def _instant(value: object, *, field: str, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, datetime):
        raise TaxRuleProvisioningError(f'Invalid {field}')
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _rate(value: object, treatment: str) -> Decimal:
    if isinstance(value, float) or not isinstance(value, Decimal) or not value.is_finite():
        raise TaxRuleProvisioningError('Tax rate must be an exact finite Decimal')
    if value < 0 or value > tax_service.MAX_RATE or value.quantize(tax_service.RATE_UNIT) != value:
        raise TaxRuleProvisioningError('Tax rate is outside supported precision')
    normalized = value.quantize(tax_service.RATE_UNIT)
    if treatment == TaxTreatment.TAXABLE.value and normalized <= 0:
        raise TaxRuleProvisioningError('TAXABLE treatment requires a positive Tax rate')
    if treatment in {TaxTreatment.ZERO_RATE.value, TaxTreatment.EXEMPT.value} and normalized != 0:
        raise TaxRuleProvisioningError(f'{treatment} treatment requires a zero Tax rate')
    return normalized


def _values(
    *, tax_classification_code: str, jurisdiction_code: str,
    tax_category: str, tax_treatment: str, tax_effect: str,
    tax_rate: Decimal, calculation_policy: str, rounding_policy: str,
    effective_from: datetime, effective_to: datetime | None, status: str,
) -> dict[str, object]:
    treatment = _choice(
        tax_treatment, field='Tax treatment',
        allowed=frozenset(value.value for value in TaxTreatment),
    )
    effect = _choice(
        tax_effect, field='Tax effect',
        allowed=frozenset(value.value for value in TaxEffect),
    )
    if effect != TaxEffect.TRANSFERRED.value:
        raise TaxRuleProvisioningError(
            'Configured Tax effect has no supported runtime calculation policy'
        )
    calculation = _text(
        calculation_policy, field='Tax calculation policy', maximum=64,
    )
    rounding = _text(rounding_policy, field='Tax rounding policy', maximum=64)
    if calculation != tax_service.CALCULATION_POLICY:
        raise TaxRuleProvisioningError('Unsupported Tax calculation policy')
    if rounding != tax_service.ROUNDING_POLICY:
        raise TaxRuleProvisioningError('Unsupported Tax rounding policy')
    start = _instant(effective_from, field='Tax effective_from')
    end = _instant(effective_to, field='Tax effective_to', optional=True)
    assert start is not None
    if end is not None and start >= end:
        raise TaxRuleProvisioningError('Tax effective_to must be later than effective_from')
    return {
        'tax_classification_code': _text(
            tax_classification_code, field='Tax classification code', maximum=64,
        ),
        'jurisdiction_code': _text(
            jurisdiction_code, field='Tax jurisdiction code', maximum=64,
        ),
        'tax_category': _text(tax_category, field='Tax category', maximum=64),
        'tax_treatment': treatment,
        'tax_effect': effect,
        'tax_rate': _rate(tax_rate, treatment),
        'calculation_policy': calculation,
        'rounding_policy': rounding,
        'effective_from': start,
        'effective_to': end,
        'status': _choice(
            status, field='Tax Rule status', allowed=frozenset({'ACTIVE', 'INACTIVE'}),
        ),
    }


def _state(rule: RestaurantTaxRule) -> tuple[object, ...]:
    return (
        rule.id, rule.jurisdiction_code, rule.tax_category, rule.tax_treatment,
        rule.tax_effect, rule.tax_rate, rule.calculation_policy,
        rule.rounding_policy, rule.effective_to, rule.status,
    )


def _overlaps(
    first_start: datetime, first_end: datetime | None,
    second_start: datetime, second_end: datetime | None,
) -> bool:
    return (
        (second_end is None or first_start < second_end)
        and (first_end is None or second_start < first_end)
    )


async def _scope(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int | None, lock: bool,
) -> None:
    statement = select(Organization).where(
        Organization.id == organization_id, Organization.tenant_id == tenant_id,
    )
    if lock:
        statement = statement.with_for_update()
    if await db.scalar(statement) is None:
        raise TaxRuleScopeError('Organization not found')
    if location_id is not None and await db.scalar(select(Location).where(
        Location.id == location_id, Location.tenant_id == tenant_id,
        Location.organization_id == organization_id,
    )) is None:
        raise TaxRuleScopeError('Location not found')


async def _matching(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int | None, classification: str, effective_from: datetime,
    lock: bool = False,
) -> tuple[RestaurantTaxRule, ...]:
    location_clause = (
        RestaurantTaxRule.location_id.is_(None)
        if location_id is None
        else RestaurantTaxRule.location_id == location_id
    )
    statement = select(RestaurantTaxRule).where(
        RestaurantTaxRule.tenant_id == tenant_id,
        RestaurantTaxRule.organization_id == organization_id,
        location_clause,
        RestaurantTaxRule.tax_classification_code == classification,
        RestaurantTaxRule.effective_from == effective_from,
    ).order_by(RestaurantTaxRule.id)
    if lock:
        statement = statement.with_for_update()
    return tuple((await db.scalars(statement)).all())


async def _assert_no_overlap(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int | None, classification: str, effective_from: datetime,
    effective_to: datetime | None, exclude_id: int | None,
    lock: bool = False,
) -> None:
    if location_id is None:
        location_clause = RestaurantTaxRule.location_id.is_(None)
    else:
        location_clause = RestaurantTaxRule.location_id == location_id
    statement = select(RestaurantTaxRule).where(
        RestaurantTaxRule.tenant_id == tenant_id,
        RestaurantTaxRule.organization_id == organization_id,
        location_clause,
        RestaurantTaxRule.tax_classification_code == classification,
        RestaurantTaxRule.status == 'ACTIVE',
    )
    if lock:
        statement = statement.with_for_update()
    rows = tuple((await db.scalars(statement)).all())
    if any(
        row.id != exclude_id and _overlaps(
            effective_from, effective_to, row.effective_from, row.effective_to,
        )
        for row in rows
    ):
        raise TaxRuleConflictError(
            'Tax Rule overlaps another active Rule at the same precedence'
        )


async def plan_tax_rule(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int | None, tax_classification_code: str,
    jurisdiction_code: str, tax_category: str, tax_treatment: str,
    tax_effect: str, tax_rate: Decimal, calculation_policy: str,
    rounding_policy: str, effective_from: datetime,
    effective_to: datetime | None, status: str, lock_scope: bool = False,
) -> TaxRuleProvisioningPlan:
    values = _values(
        tax_classification_code=tax_classification_code,
        jurisdiction_code=jurisdiction_code, tax_category=tax_category,
        tax_treatment=tax_treatment, tax_effect=tax_effect, tax_rate=tax_rate,
        calculation_policy=calculation_policy, rounding_policy=rounding_policy,
        effective_from=effective_from, effective_to=effective_to, status=status,
    )
    await _scope(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, lock=lock_scope,
    )
    rows = await _matching(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
        classification=str(values['tax_classification_code']),
        effective_from=values['effective_from'],  # type: ignore[arg-type]
        lock=lock_scope,
    )
    if len(rows) > 1:
        raise TaxRuleConflictError('Duplicate canonical Tax Rule identity')
    current = rows[0] if rows else None
    if values['status'] == 'ACTIVE':
        await _assert_no_overlap(
            db, tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id,
            classification=str(values['tax_classification_code']),
            effective_from=values['effective_from'],  # type: ignore[arg-type]
            effective_to=values['effective_to'],  # type: ignore[arg-type]
            exclude_id=None if current is None else current.id,
            lock=lock_scope,
        )
    if current is None:
        return TaxRuleProvisioningPlan('CREATE', None, None)
    comparable = (
        values['jurisdiction_code'], values['tax_category'], values['tax_treatment'],
        values['tax_effect'], values['tax_rate'], values['calculation_policy'],
        values['rounding_policy'], values['effective_to'], values['status'],
    )
    return TaxRuleProvisioningPlan(
        'UNCHANGED' if _state(current)[1:] == comparable else 'UPDATE',
        current.id, _state(current),
    )


async def provision_tax_rule(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int | None, tax_classification_code: str,
    jurisdiction_code: str, tax_category: str, tax_treatment: str,
    tax_effect: str, tax_rate: Decimal, calculation_policy: str,
    rounding_policy: str, effective_from: datetime,
    effective_to: datetime | None, status: str,
) -> TaxRuleProvisioningResult:
    initial = await plan_tax_rule(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, tax_classification_code=tax_classification_code,
        jurisdiction_code=jurisdiction_code, tax_category=tax_category,
        tax_treatment=tax_treatment, tax_effect=tax_effect, tax_rate=tax_rate,
        calculation_policy=calculation_policy, rounding_policy=rounding_policy,
        effective_from=effective_from, effective_to=effective_to, status=status,
    )
    current = await plan_tax_rule(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, tax_classification_code=tax_classification_code,
        jurisdiction_code=jurisdiction_code, tax_category=tax_category,
        tax_treatment=tax_treatment, tax_effect=tax_effect, tax_rate=tax_rate,
        calculation_policy=calculation_policy, rounding_policy=rounding_policy,
        effective_from=effective_from, effective_to=effective_to, status=status,
        lock_scope=True,
    )
    if initial.operation == 'CREATE' and current.operation == 'UNCHANGED':
        assert current.rule_id is not None
        rule = await db.scalar(select(RestaurantTaxRule).where(
            RestaurantTaxRule.id == current.rule_id,
            RestaurantTaxRule.tenant_id == tenant_id,
            RestaurantTaxRule.organization_id == organization_id,
        ).with_for_update())
        assert rule is not None
        await db.commit()
        return TaxRuleProvisioningResult(rule, 'UNCHANGED')
    if (
        initial.operation != current.operation
        or initial.rule_id != current.rule_id
        or initial.expected_state != current.expected_state
    ):
        raise TaxRuleConflictError('Tax Rule changed concurrently')
    values = _values(
        tax_classification_code=tax_classification_code,
        jurisdiction_code=jurisdiction_code, tax_category=tax_category,
        tax_treatment=tax_treatment, tax_effect=tax_effect, tax_rate=tax_rate,
        calculation_policy=calculation_policy, rounding_policy=rounding_policy,
        effective_from=effective_from, effective_to=effective_to, status=status,
    )
    if current.operation == 'UNCHANGED':
        assert current.rule_id is not None
        rule = await db.scalar(select(RestaurantTaxRule).where(
            RestaurantTaxRule.id == current.rule_id,
            RestaurantTaxRule.tenant_id == tenant_id,
            RestaurantTaxRule.organization_id == organization_id,
        ).with_for_update())
        assert rule is not None
        await db.commit()
        return TaxRuleProvisioningResult(rule, 'UNCHANGED')
    if current.operation == 'CREATE':
        rule = RestaurantTaxRule(
            tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id, **values,
        )
        db.add(rule)
    else:
        assert current.rule_id is not None
        rule = await db.scalar(select(RestaurantTaxRule).where(
            RestaurantTaxRule.id == current.rule_id,
            RestaurantTaxRule.tenant_id == tenant_id,
            RestaurantTaxRule.organization_id == organization_id,
        ).with_for_update())
        if rule is None or _state(rule) != current.expected_state:
            raise TaxRuleConflictError('Tax Rule changed concurrently')
        for key, value in values.items():
            setattr(rule, key, value)
    await db.commit()
    await db.refresh(rule)
    return TaxRuleProvisioningResult(rule, current.operation)


async def resolve_tax_rule_configuration(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, tax_classification_code: str, effective_at: datetime,
) -> RestaurantTaxRule:
    classification = _text(
        tax_classification_code, field='Tax classification code', maximum=64,
    )
    instant = _instant(effective_at, field='Tax effective instant')
    assert instant is not None
    await _scope(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, lock=False,
    )
    rows = tuple((await db.scalars(select(RestaurantTaxRule).where(
        RestaurantTaxRule.tenant_id == tenant_id,
        RestaurantTaxRule.organization_id == organization_id,
        RestaurantTaxRule.tax_classification_code == classification,
        RestaurantTaxRule.status == 'ACTIVE',
        RestaurantTaxRule.effective_from <= instant,
        or_(
            RestaurantTaxRule.effective_to.is_(None),
            instant < RestaurantTaxRule.effective_to,
        ),
        or_(
            RestaurantTaxRule.location_id == location_id,
            RestaurantTaxRule.location_id.is_(None),
        ),
    ).order_by(RestaurantTaxRule.id))).all())
    local = tuple(row for row in rows if row.location_id == location_id)
    applicable = local or tuple(row for row in rows if row.location_id is None)
    if not applicable:
        raise TaxRuleScopeError('Applicable Tax Rule not found')
    if len(applicable) != 1:
        raise TaxRuleConflictError('Applicable Tax Rule is ambiguous')
    return applicable[0]
