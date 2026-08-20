from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, Product, ProductExternalMapping
from app.restaurant.integrations.pos.contracts import ExternalEntityStatus, PosRequestContext
from app.restaurant.integrations.pos.errors import PosInvalidDataError, PosMappingError
from app.restaurant.integrations.pos.ports import CatalogPort


logger = logging.getLogger('ecip.products')


def _pos_error(
    error_type: type[PosInvalidDataError] | type[PosMappingError],
    message: str,
    context: PosRequestContext,
) -> PosInvalidDataError | PosMappingError:
    return error_type(
        message,
        operation='get_product',
        connector_key=context.connector_key,
        correlation_id=context.correlation_id,
        external_entity_type='product',
    )


def _normalize_external_id(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise ValueError('A valid external Product identifier is required')
    return normalized


async def _get_mapped_product(
    db: AsyncSession,
    *,
    tenant_id: int,
    connector_key: str,
    external_product_id: str,
) -> Product | None:
    return await db.scalar(
        select(Product)
        .join(
            ProductExternalMapping,
            (ProductExternalMapping.product_id == Product.id)
            & (ProductExternalMapping.tenant_id == Product.tenant_id),
        )
        .where(
            ProductExternalMapping.tenant_id == tenant_id,
            ProductExternalMapping.connector_key == connector_key,
            ProductExternalMapping.external_product_id == external_product_id,
        )
    )


def _verify_organization(product: Product, organization_id: int, context: PosRequestContext) -> None:
    if product.organization_id != organization_id:
        raise _pos_error(
            PosMappingError,
            'POS Product mapping belongs to a different Organization',
            context,
        )


def _normalize_name(value: str, context: PosRequestContext) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 200:
        raise _pos_error(PosInvalidDataError, 'POS Product name is invalid', context)
    return normalized


def _normalize_description(value: str | None, context: PosRequestContext) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 2000:
        raise _pos_error(PosInvalidDataError, 'POS Product description is invalid', context)
    return normalized


async def resolve_external_product(
    db: AsyncSession,
    catalog_port: CatalogPort,
    context: PosRequestContext,
    *,
    organization_id: int,
    external_product_id: str,
) -> Product:
    """Resolve one exact POS Product identity without merging or synchronization."""

    if organization_id <= 0:
        raise ValueError('A valid Organization identifier is required')
    normalized_external_id = _normalize_external_id(external_product_id)
    organization = await db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.tenant_id == context.tenant_id,
        )
    )
    if organization is None:
        raise ValueError('Organization does not belong to the trusted Tenant')

    existing = await _get_mapped_product(
        db,
        tenant_id=context.tenant_id,
        connector_key=context.connector_key,
        external_product_id=normalized_external_id,
    )
    if existing is not None:
        _verify_organization(existing, organization_id, context)
        logger.info(
            'Product external identity resolved',
            extra={
                'event': 'product_external_identity_resolved',
                'operation': 'resolve_external_product',
                'tenant_id': context.tenant_id,
                'organization_id': organization_id,
                'product_id': existing.id,
                'connector_key': context.connector_key,
                'correlation_id': context.correlation_id,
                'outcome': 'existing',
            },
        )
        return existing

    external = await catalog_port.get_product(
        context,
        product_external_id=normalized_external_id,
    )
    returned_external_id = external.external_id.strip()
    if returned_external_id != normalized_external_id:
        raise _pos_error(
            PosMappingError,
            'POS Product identifier did not match the requested identifier',
            context,
        )
    status = {
        ExternalEntityStatus.ACTIVE: 'ACTIVE',
        ExternalEntityStatus.INACTIVE: 'INACTIVE',
    }.get(external.status)
    if status is None:
        raise _pos_error(PosMappingError, 'POS Product status cannot be mapped', context)

    product = Product(
        tenant_id=context.tenant_id,
        organization_id=organization_id,
        category_id=None,
        name=_normalize_name(external.name, context),
        description=_normalize_description(external.description, context),
        status=status,
        source='POS',
    )
    db.add(product)
    await db.flush()
    db.add(
        ProductExternalMapping(
            tenant_id=context.tenant_id,
            product_id=product.id,
            connector_key=context.connector_key,
            external_product_id=returned_external_id,
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        winner = await _get_mapped_product(
            db,
            tenant_id=context.tenant_id,
            connector_key=context.connector_key,
            external_product_id=normalized_external_id,
        )
        if winner is None:
            raise
        _verify_organization(winner, organization_id, context)
        product = winner
        outcome = 'race_recovered'
    else:
        await db.refresh(product)
        outcome = 'created'

    logger.info(
        'Product external identity resolved',
        extra={
            'event': 'product_external_identity_resolved',
            'operation': 'resolve_external_product',
            'tenant_id': context.tenant_id,
            'organization_id': organization_id,
            'product_id': product.id,
            'connector_key': context.connector_key,
            'correlation_id': context.correlation_id,
            'outcome': outcome,
        },
    )
    return product
