"""Canonical provisioning authority for Product fiscal classifications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Product, ProductFiscalClassification
from app.restaurant.catalog import provisioning as product_provisioning
from app.restaurant.tax import provisioning as tax_provisioning


class FiscalClassificationProvisioningError(ValueError):
    pass


class FiscalClassificationScopeError(FiscalClassificationProvisioningError):
    pass


class FiscalClassificationConflictError(FiscalClassificationProvisioningError):
    pass


@dataclass(frozen=True, slots=True)
class FiscalClassificationProvisioningPlan:
    operation: str
    product_id: int | None
    classification_id: int | None
    expected_state: tuple[object, ...] | None


@dataclass(frozen=True, slots=True)
class FiscalClassificationProvisioningResult:
    classification: ProductFiscalClassification
    operation: str


def _text(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise FiscalClassificationProvisioningError(f'Invalid {field}')
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise FiscalClassificationProvisioningError(f'Invalid {field}')
    return normalized


def _status(value: object) -> str:
    normalized = _text(value, field='Fiscal Classification status', maximum=16).upper()
    if normalized not in {'ACTIVE', 'INACTIVE'}:
        raise FiscalClassificationProvisioningError(
            'Unsupported Fiscal Classification status'
        )
    return normalized


def _instant(value: object, *, field: str, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, datetime):
        raise FiscalClassificationProvisioningError(f'Invalid {field}')
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _values(
    *, fiscal_jurisdiction_code: str, product_classification_scheme: str,
    product_classification_code: str, unit_classification_scheme: str,
    unit_classification_code: str, effective_from: datetime,
    effective_to: datetime | None, status: str,
) -> dict[str, object]:
    start = _instant(effective_from, field='Fiscal Classification effective_from')
    end = _instant(
        effective_to, field='Fiscal Classification effective_to', optional=True,
    )
    assert start is not None
    if end is not None and start >= end:
        raise FiscalClassificationProvisioningError(
            'Fiscal Classification effective_to must be later than effective_from'
        )
    return {
        'fiscal_jurisdiction_code': _text(
            fiscal_jurisdiction_code, field='Fiscal jurisdiction code', maximum=16,
        ),
        'product_classification_scheme': _text(
            product_classification_scheme,
            field='Fiscal product classification scheme', maximum=64,
        ),
        'product_classification_code': _text(
            product_classification_code,
            field='Fiscal product classification code', maximum=64,
        ),
        'unit_classification_scheme': _text(
            unit_classification_scheme,
            field='Fiscal unit classification scheme', maximum=64,
        ),
        'unit_classification_code': _text(
            unit_classification_code,
            field='Fiscal unit classification code', maximum=64,
        ),
        'effective_from': start,
        'effective_to': end,
        'status': _status(status),
    }


def _state(value: ProductFiscalClassification) -> tuple[object, ...]:
    return (
        value.id, value.product_classification_scheme,
        value.product_classification_code, value.unit_classification_scheme,
        value.unit_classification_code, value.effective_to, value.status,
    )


def _overlaps(
    first_start: datetime, first_end: datetime | None,
    second_start: datetime, second_end: datetime | None,
) -> bool:
    return (
        (second_end is None or first_start < second_end)
        and (first_end is None or second_start < first_end)
    )


async def _location(
    db: AsyncSession, *, tenant_id: int, organization_id: int, location_id: int,
) -> Location:
    location = await db.scalar(select(Location).where(
        Location.id == location_id, Location.tenant_id == tenant_id,
        Location.organization_id == organization_id,
    ))
    if location is None:
        raise FiscalClassificationScopeError('Location not found')
    return location


async def _matching(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    product_id: int, jurisdiction: str, effective_from: datetime,
    lock: bool = False,
) -> tuple[ProductFiscalClassification, ...]:
    statement = select(ProductFiscalClassification).where(
        ProductFiscalClassification.tenant_id == tenant_id,
        ProductFiscalClassification.organization_id == organization_id,
        ProductFiscalClassification.product_id == product_id,
        ProductFiscalClassification.fiscal_jurisdiction_code == jurisdiction,
        ProductFiscalClassification.effective_from == effective_from,
    ).order_by(ProductFiscalClassification.id)
    if lock:
        statement = statement.with_for_update()
    return tuple((await db.scalars(statement)).all())


async def _assert_no_overlap(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    product_id: int, jurisdiction: str, effective_from: datetime,
    effective_to: datetime | None, exclude_id: int | None,
    lock: bool = False,
) -> None:
    statement = select(ProductFiscalClassification).where(
        ProductFiscalClassification.tenant_id == tenant_id,
        ProductFiscalClassification.organization_id == organization_id,
        ProductFiscalClassification.product_id == product_id,
        ProductFiscalClassification.fiscal_jurisdiction_code == jurisdiction,
        ProductFiscalClassification.status == 'ACTIVE',
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
        raise FiscalClassificationConflictError(
            'Product Fiscal Classification overlaps another active record'
        )


async def plan_product_fiscal_classification(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, binding_namespace: str, product_key: str,
    tax_classification_code: str, fiscal_jurisdiction_code: str,
    product_classification_scheme: str, product_classification_code: str,
    unit_classification_scheme: str, unit_classification_code: str,
    effective_from: datetime, effective_to: datetime | None, status: str,
    allow_unresolved_product: bool = False,
    allow_unresolved_tax_rule: bool = False,
    lock_rows: bool = False,
) -> FiscalClassificationProvisioningPlan:
    values = _values(
        fiscal_jurisdiction_code=fiscal_jurisdiction_code,
        product_classification_scheme=product_classification_scheme,
        product_classification_code=product_classification_code,
        unit_classification_scheme=unit_classification_scheme,
        unit_classification_code=unit_classification_code,
        effective_from=effective_from, effective_to=effective_to, status=status,
    )
    location = await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    if values['fiscal_jurisdiction_code'] != location.country_code:
        raise FiscalClassificationScopeError(
            'Fiscal jurisdiction must match the authorized Location country code'
        )
    tax_code = _text(
        tax_classification_code, field='Tax classification code', maximum=64,
    )
    product: Product | None
    try:
        product = await product_provisioning.resolve_product_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, product_key=product_key,
        )
    except product_provisioning.ProductProvisioningError as exc:
        if not allow_unresolved_product:
            raise FiscalClassificationScopeError(str(exc)) from exc
        product = None
    try:
        rule = await tax_provisioning.resolve_tax_rule_configuration(
            db, tenant_id=tenant_id, organization_id=organization_id,
            location_id=location_id, tax_classification_code=tax_code,
            effective_at=values['effective_from'],  # type: ignore[arg-type]
        )
        classification_end = values['effective_to']
        if rule.effective_to is not None and (
            classification_end is None or classification_end > rule.effective_to
        ):
            raise FiscalClassificationConflictError(
                'Tax Rule does not cover the Fiscal Classification effective period'
            )
    except tax_provisioning.TaxRuleScopeError as exc:
        if not allow_unresolved_tax_rule:
            raise FiscalClassificationScopeError(str(exc)) from exc
    except tax_provisioning.TaxRuleProvisioningError as exc:
        raise FiscalClassificationConflictError(str(exc)) from exc

    if product is None:
        return FiscalClassificationProvisioningPlan('CREATE', None, None, None)

    jurisdiction = str(values['fiscal_jurisdiction_code'])
    start = values['effective_from']
    assert isinstance(start, datetime)
    rows = await _matching(
        db, tenant_id=tenant_id, organization_id=organization_id,
        product_id=product.id, jurisdiction=jurisdiction, effective_from=start,
        lock=lock_rows,
    )
    if len(rows) > 1:
        raise FiscalClassificationConflictError(
            'Duplicate canonical Product Fiscal Classification identity'
        )
    current = rows[0] if rows else None
    if values['status'] == 'ACTIVE':
        await _assert_no_overlap(
            db, tenant_id=tenant_id, organization_id=organization_id,
            product_id=product.id, jurisdiction=jurisdiction,
            effective_from=start,
            effective_to=values['effective_to'],  # type: ignore[arg-type]
            exclude_id=None if current is None else current.id,
            lock=lock_rows,
        )
    if current is None:
        return FiscalClassificationProvisioningPlan(
            'CREATE', product.id, None, None,
        )
    comparable = (
        values['product_classification_scheme'],
        values['product_classification_code'],
        values['unit_classification_scheme'], values['unit_classification_code'],
        values['effective_to'], values['status'],
    )
    unchanged = _state(current)[1:] == comparable and product.tax_classification_code == tax_code
    return FiscalClassificationProvisioningPlan(
        'UNCHANGED' if unchanged else 'UPDATE',
        product.id, current.id, _state(current),
    )


async def provision_product_fiscal_classification(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, binding_namespace: str, product_key: str,
    tax_classification_code: str, fiscal_jurisdiction_code: str,
    product_classification_scheme: str, product_classification_code: str,
    unit_classification_scheme: str, unit_classification_code: str,
    effective_from: datetime, effective_to: datetime | None, status: str,
) -> FiscalClassificationProvisioningResult:
    arguments = {
        'tenant_id': tenant_id, 'organization_id': organization_id,
        'location_id': location_id, 'binding_namespace': binding_namespace,
        'product_key': product_key,
        'tax_classification_code': tax_classification_code,
        'fiscal_jurisdiction_code': fiscal_jurisdiction_code,
        'product_classification_scheme': product_classification_scheme,
        'product_classification_code': product_classification_code,
        'unit_classification_scheme': unit_classification_scheme,
        'unit_classification_code': unit_classification_code,
        'effective_from': effective_from, 'effective_to': effective_to,
        'status': status,
    }
    initial = await plan_product_fiscal_classification(db, **arguments)
    product = await product_provisioning.resolve_product_binding(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=binding_namespace, product_key=product_key,
    )
    locked = await db.scalar(select(Product).where(
        Product.id == product.id, Product.tenant_id == tenant_id,
        Product.organization_id == organization_id,
    ).with_for_update().execution_options(populate_existing=True))
    if locked is None:
        raise FiscalClassificationScopeError('Product not found')
    current = await plan_product_fiscal_classification(
        db, **arguments, lock_rows=True,
    )
    if initial.operation == 'CREATE' and current.operation == 'UNCHANGED':
        assert current.classification_id is not None
        classification = await db.scalar(select(ProductFiscalClassification).where(
            ProductFiscalClassification.id == current.classification_id,
            ProductFiscalClassification.tenant_id == tenant_id,
            ProductFiscalClassification.organization_id == organization_id,
            ProductFiscalClassification.product_id == locked.id,
        ).with_for_update())
        assert classification is not None
        await db.commit()
        return FiscalClassificationProvisioningResult(classification, 'UNCHANGED')
    if (
        initial.operation != current.operation
        or initial.product_id != current.product_id
        or initial.classification_id != current.classification_id
        or initial.expected_state != current.expected_state
    ):
        raise FiscalClassificationConflictError(
            'Product Fiscal Classification changed concurrently'
        )
    values = _values(
        fiscal_jurisdiction_code=fiscal_jurisdiction_code,
        product_classification_scheme=product_classification_scheme,
        product_classification_code=product_classification_code,
        unit_classification_scheme=unit_classification_scheme,
        unit_classification_code=unit_classification_code,
        effective_from=effective_from, effective_to=effective_to, status=status,
    )
    if current.operation == 'UNCHANGED':
        assert current.classification_id is not None
        classification = await db.scalar(select(ProductFiscalClassification).where(
            ProductFiscalClassification.id == current.classification_id,
            ProductFiscalClassification.tenant_id == tenant_id,
            ProductFiscalClassification.organization_id == organization_id,
            ProductFiscalClassification.product_id == locked.id,
        ).with_for_update())
        assert classification is not None
        await db.commit()
        return FiscalClassificationProvisioningResult(classification, 'UNCHANGED')
    locked.tax_classification_code = _text(
        tax_classification_code, field='Tax classification code', maximum=64,
    )
    if current.operation == 'CREATE':
        classification = ProductFiscalClassification(
            tenant_id=tenant_id, organization_id=organization_id,
            product_id=locked.id, **values,
        )
        db.add(classification)
    else:
        assert current.classification_id is not None
        classification = await db.scalar(select(ProductFiscalClassification).where(
            ProductFiscalClassification.id == current.classification_id,
            ProductFiscalClassification.tenant_id == tenant_id,
            ProductFiscalClassification.organization_id == organization_id,
            ProductFiscalClassification.product_id == locked.id,
        ).with_for_update())
        if classification is None or _state(classification) != current.expected_state:
            raise FiscalClassificationConflictError(
                'Product Fiscal Classification changed concurrently'
            )
        for key, value in values.items():
            setattr(classification, key, value)
    await db.commit()
    await db.refresh(classification)
    return FiscalClassificationProvisioningResult(classification, current.operation)
