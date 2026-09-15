"""Canonical PLATFORM Price provisioning authority."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Product, ProductPrice
from app.restaurant.catalog import provisioning as product_provisioning


MAX_AMOUNT = Decimal('999999999999999.9999')
PRICE_STATUSES = frozenset({'ACTIVE', 'INACTIVE'})
_DUPLICATE_KEY_PATTERN = re.compile(
    r"for key [`'\"]([^`'\"]+)[`'\"]", re.IGNORECASE,
)
_PRICE_CONSTRAINT = 'uq_product_prices_tenant_product_location'


class PriceProvisioningError(ValueError):
    pass


class PriceScopeNotFoundError(PriceProvisioningError):
    pass


class PriceConflictError(PriceProvisioningError):
    pass


PriceState = tuple[Decimal, str, str, str]


@dataclass(frozen=True, slots=True)
class PriceProvisioningPlan:
    operation: str
    product_id: int | None
    location_id: int
    price_id: int | None
    observed_state: PriceState | None


@dataclass(frozen=True, slots=True)
class PriceProvisioningResult:
    product: Product
    location: Location
    price: ProductPrice
    operation: str


def _amount(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise PriceProvisioningError('Price amount must be an exact Decimal')
    if (
        not value.is_finite()
        or value < 0
        or value.as_tuple().exponent < -4
        or value > MAX_AMOUNT
    ):
        raise PriceProvisioningError('Price amount is outside DECIMAL(19,4)')
    return value


def _currency(value: object) -> str:
    if not isinstance(value, str):
        raise PriceProvisioningError('Invalid Price currency')
    normalized = value.strip().upper()
    if (
        len(normalized) != 3
        or not normalized.isascii()
        or not normalized.isalpha()
    ):
        raise PriceProvisioningError(
            'Price currency must be a three-letter ASCII code'
        )
    return normalized


def _status(value: object) -> str:
    if not isinstance(value, str):
        raise PriceProvisioningError('Invalid Price status')
    normalized = value.strip().upper()
    if normalized not in PRICE_STATUSES:
        raise PriceProvisioningError('Unsupported Price status')
    return normalized


def _state(price: ProductPrice) -> PriceState:
    return price.amount, price.currency, price.status, price.source


def _requested_state(
    *, amount: Decimal, currency: str, status: str,
) -> PriceState:
    return amount, currency, status, 'PLATFORM'


def _is_constraint(exc: IntegrityError, constraint_name: str) -> bool:
    arguments = getattr(exc.orig, 'args', ())
    if len(arguments) < 2 or arguments[0] != 1062:
        return False
    match = _DUPLICATE_KEY_PATTERN.search(str(arguments[1]))
    return match is not None and match.group(1).rsplit('.', 1)[-1] == constraint_name


async def _location(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, for_update: bool = False,
) -> Location:
    statement = select(Location).where(
        Location.id == location_id,
        Location.tenant_id == tenant_id,
        Location.organization_id == organization_id,
    )
    if for_update:
        statement = statement.with_for_update()
    location = await db.scalar(statement)
    if location is None:
        raise PriceScopeNotFoundError('Location not found')
    return location


async def _product(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    product_id: int,
) -> Product:
    product = await db.scalar(select(Product).where(
        Product.id == product_id,
        Product.tenant_id == tenant_id,
        Product.organization_id == organization_id,
    ))
    if product is None:
        raise PriceScopeNotFoundError('Product not found')
    return product


async def _price(
    db: AsyncSession, *, tenant_id: int, product_id: int, location_id: int,
    for_update: bool = False,
) -> ProductPrice | None:
    statement = select(ProductPrice).where(
        ProductPrice.tenant_id == tenant_id,
        ProductPrice.product_id == product_id,
        ProductPrice.location_id == location_id,
    )
    if for_update:
        statement = statement.with_for_update()
    return await db.scalar(statement)


def _verify_platform(price: ProductPrice) -> None:
    if price.source != 'PLATFORM':
        raise PriceConflictError('Onboarding cannot overwrite a POS Price')


async def create_price(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    product_id: int, location_id: int, amount: Decimal, currency: str,
    commit: bool = True,
) -> ProductPrice:
    product = await _product(
        db, tenant_id=tenant_id, organization_id=organization_id,
        product_id=product_id,
    )
    location = await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    price = ProductPrice(
        tenant_id=tenant_id, organization_id=organization_id,
        product_id=product.id, location_id=location.id,
        amount=_amount(amount), currency=_currency(currency),
        status='ACTIVE', source='PLATFORM',
    )
    db.add(price)
    try:
        if commit:
            await db.commit()
            await db.refresh(price)
        else:
            await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if _is_constraint(exc, _PRICE_CONSTRAINT):
            raise PriceConflictError(
                'Price already exists for Product and Location'
            ) from exc
        raise
    return price


async def update_price(
    db: AsyncSession, *, tenant_id: int, price_id: int,
    changes: dict[str, object], commit: bool = True,
) -> ProductPrice:
    allowed = {'amount', 'currency', 'status'}
    if not changes or not set(changes) <= allowed:
        raise PriceProvisioningError('Invalid Price update fields')
    price = await db.scalar(select(ProductPrice).where(
        ProductPrice.id == price_id,
        ProductPrice.tenant_id == tenant_id,
    ).with_for_update())
    if price is None:
        raise PriceScopeNotFoundError('Price not found')
    updates = dict(changes)
    if 'amount' in updates:
        updates['amount'] = _amount(updates['amount'])
    if 'currency' in updates:
        updates['currency'] = _currency(updates['currency'])
    if 'status' in updates:
        updates['status'] = _status(updates['status'])
    for field, value in updates.items():
        setattr(price, field, value)
    if commit:
        await db.commit()
        await db.refresh(price)
    else:
        await db.flush()
    return price


async def plan_price(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, binding_namespace: str, product_key: str,
    amount: Decimal, currency: str, status: str,
    allow_unresolved_product: bool = False,
) -> PriceProvisioningPlan:
    normalized_amount = _amount(amount)
    normalized_currency = _currency(currency)
    normalized_status = _status(status)
    location = await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id,
    )
    try:
        product = await product_provisioning.resolve_product_binding(
            db, tenant_id=tenant_id, organization_id=organization_id,
            binding_namespace=binding_namespace, product_key=product_key,
        )
    except product_provisioning.ProductProvisioningError as exc:
        if not allow_unresolved_product:
            raise PriceScopeNotFoundError(str(exc)) from exc
        if normalized_status != 'ACTIVE':
            raise PriceConflictError('New Prices must be ACTIVE')
        return PriceProvisioningPlan('CREATE', None, location.id, None, None)
    price = await _price(
        db, tenant_id=tenant_id, product_id=product.id,
        location_id=location.id,
    )
    if price is None:
        if normalized_status != 'ACTIVE':
            raise PriceConflictError('New Prices must be ACTIVE')
        return PriceProvisioningPlan(
            'CREATE', product.id, location.id, None, None,
        )
    _verify_platform(price)
    observed = _state(price)
    requested = _requested_state(
        amount=normalized_amount, currency=normalized_currency,
        status=normalized_status,
    )
    return PriceProvisioningPlan(
        'UNCHANGED' if observed == requested else 'UPDATE',
        product.id, location.id, price.id, observed,
    )


async def provision_price(
    db: AsyncSession, *, tenant_id: int, organization_id: int,
    location_id: int, binding_namespace: str, product_key: str,
    amount: Decimal, currency: str, status: str,
) -> PriceProvisioningResult:
    normalized_amount = _amount(amount)
    normalized_currency = _currency(currency)
    normalized_status = _status(status)
    plan = await plan_price(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, binding_namespace=binding_namespace,
        product_key=product_key, amount=normalized_amount,
        currency=normalized_currency, status=normalized_status,
    )
    product = await product_provisioning.resolve_product_binding(
        db, tenant_id=tenant_id, organization_id=organization_id,
        binding_namespace=binding_namespace, product_key=product_key,
    )
    location = await _location(
        db, tenant_id=tenant_id, organization_id=organization_id,
        location_id=location_id, for_update=True,
    )
    current = await _price(
        db, tenant_id=tenant_id, product_id=product.id,
        location_id=location.id, for_update=True,
    )
    requested = _requested_state(
        amount=normalized_amount, currency=normalized_currency,
        status=normalized_status,
    )
    if plan.operation == 'CREATE':
        if current is not None:
            _verify_platform(current)
            if _state(current) != requested:
                raise PriceConflictError(
                    'A conflicting Price was created concurrently'
                )
            await db.commit()
            return PriceProvisioningResult(
                product, location, current, 'UNCHANGED',
            )
        if normalized_status != 'ACTIVE':
            raise PriceConflictError('New Prices must be ACTIVE')
        price = ProductPrice(
            tenant_id=tenant_id, organization_id=organization_id,
            product_id=product.id, location_id=location.id,
            amount=normalized_amount, currency=normalized_currency,
            status='ACTIVE', source='PLATFORM',
        )
        db.add(price)
        operation = 'CREATE'
    else:
        if current is None:
            raise PriceConflictError('Planned Price no longer exists')
        _verify_platform(current)
        current_state = _state(current)
        if current_state != plan.observed_state:
            if current_state == requested:
                await db.commit()
                return PriceProvisioningResult(
                    product, location, current, 'UNCHANGED',
                )
            raise PriceConflictError('Price changed concurrently')
        operation = 'UNCHANGED' if current_state == requested else 'UPDATE'
        if operation == 'UPDATE':
            current.amount = normalized_amount
            current.currency = normalized_currency
            current.status = normalized_status
        price = current
    try:
        if operation != 'UNCHANGED':
            await db.commit()
            await db.refresh(price)
        else:
            await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_constraint(exc, _PRICE_CONSTRAINT):
            raise PriceConflictError(
                'Price already exists for Product and Location'
            ) from exc
        raise
    return PriceProvisioningResult(product, location, price, operation)
