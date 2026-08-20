from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Product, ProductExternalMapping, ProductPrice
from app.restaurant.integrations.pos.contracts import LocationScopedPosRequestContext
from app.restaurant.integrations.pos.errors import PosInvalidDataError, PosMappingError
from app.restaurant.integrations.pos.ports import PricingPort

logger = logging.getLogger('ecip.pricing')


class PriceAuthorityConflictError(RuntimeError):
    """A POS projection attempted to replace a platform-authored Price."""


def _pos_error(error_type, message: str, context: LocationScopedPosRequestContext):
    return error_type(message, operation='get_price', connector_key=context.connector_key, correlation_id=context.correlation_id, external_entity_type='price')


def _validate_money(amount: Decimal, currency: str, context: LocationScopedPosRequestContext) -> tuple[Decimal, str]:
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -4 or amount > Decimal('999999999999999.9999'):
        raise _pos_error(PosInvalidDataError, 'POS Price amount is invalid', context)
    normalized = currency.strip().upper()
    if len(normalized) != 3 or not normalized.isascii() or not normalized.isalpha():
        raise _pos_error(PosInvalidDataError, 'POS Price currency is invalid', context)
    return amount, normalized


async def resolve_external_price(
    db: AsyncSession,
    pricing_port: PricingPort,
    context: LocationScopedPosRequestContext,
    *,
    product_id: int,
    external_product_id: str,
) -> ProductPrice:
    """Explicitly project one exact POS Price into the current canonical Price."""
    external_product_id = external_product_id.strip()
    if not external_product_id or len(external_product_id) > 200:
        raise ValueError('A valid external Product identifier is required')
    product = await db.scalar(select(Product).where(Product.id == product_id, Product.tenant_id == context.tenant_id))
    location = await db.scalar(select(Location).where(Location.id == context.location_id, Location.tenant_id == context.tenant_id))
    if product is None or location is None or product.organization_id != location.organization_id:
        raise ValueError('Product and Location must belong to the trusted Tenant and same Organization')
    tenant_id = context.tenant_id
    organization_id = product.organization_id
    canonical_product_id = product.id
    location_id = location.id
    connector_key = context.connector_key
    correlation_id = context.correlation_id
    mapping = await db.scalar(select(ProductExternalMapping).where(
        ProductExternalMapping.tenant_id == tenant_id,
        ProductExternalMapping.connector_key == connector_key,
        ProductExternalMapping.external_product_id == external_product_id,
        ProductExternalMapping.product_id == canonical_product_id,
    ))
    if mapping is None:
        raise _pos_error(PosMappingError, 'Exact POS Product mapping was not found', context)
    external = await pricing_port.get_price(context, product_external_id=external_product_id)
    if external.product_external_id.strip() != external_product_id:
        raise _pos_error(PosMappingError, 'POS Product identifier did not match the requested identifier', context)
    amount, currency = _validate_money(external.amount, external.currency, context)
    price = await db.scalar(select(ProductPrice).where(
        ProductPrice.tenant_id == tenant_id,
        ProductPrice.product_id == canonical_product_id,
        ProductPrice.location_id == location_id,
    ).with_for_update())
    if price is not None and price.source == 'PLATFORM':
        raise PriceAuthorityConflictError('POS Price cannot overwrite a PLATFORM Price')
    if price is None:
        price = ProductPrice(tenant_id=tenant_id, organization_id=organization_id, product_id=canonical_product_id, location_id=location_id, amount=amount, currency=currency, status='ACTIVE', source='POS')
        db.add(price)
        outcome = 'created'
    else:
        price.amount = amount
        price.currency = currency
        price.status = 'ACTIVE'
        outcome = 'updated'
    try:
        await db.commit()
    except (IntegrityError, OperationalError) as exc:
        await db.rollback()
        error_args = getattr(getattr(exc, 'orig', None), 'args', ())
        error_code = error_args[0] if error_args else None
        if isinstance(exc, OperationalError) and error_code not in {1205, 1213}:
            raise
        winner = await db.scalar(select(ProductPrice).where(ProductPrice.tenant_id == tenant_id, ProductPrice.product_id == canonical_product_id, ProductPrice.location_id == location_id))
        if winner is None:
            raise
        if winner.source == 'PLATFORM':
            raise PriceAuthorityConflictError('POS Price cannot overwrite a PLATFORM Price')
        price, outcome = winner, 'race_recovered'
    else:
        await db.refresh(price)
    logger.info('Product Price resolved', extra={'event': 'price_resolved', 'operation': 'resolve_external_price', 'tenant_id': tenant_id, 'organization_id': organization_id, 'location_id': location_id, 'product_id': canonical_product_id, 'price_id': price.id, 'connector_key': connector_key, 'correlation_id': correlation_id, 'outcome': outcome})
    return price
