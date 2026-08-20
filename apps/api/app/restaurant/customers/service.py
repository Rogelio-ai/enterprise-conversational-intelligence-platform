from __future__ import annotations

import logging
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, CustomerExternalIdentity
from app.restaurant.integrations.pos.contracts import ExternalEntityStatus, PosRequestContext
from app.restaurant.integrations.pos.ports import CustomerPort


logger = logging.getLogger('ecip.customers')
_PHONE_SEPARATORS = re.compile(r'[\s().-]+')
_CANONICAL_PHONE = re.compile(r'^\+[0-9]{8,15}$')


def normalize_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 200:
        raise ValueError('Display name must contain at most 200 characters')
    return normalized


def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    if not normalized:
        return None
    if (
        len(normalized) > 320
        or normalized.count('@') != 1
        or normalized.startswith('@')
        or normalized.endswith('@')
    ):
        raise ValueError('A valid email is required')
    return normalized


def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _PHONE_SEPARATORS.sub('', value.strip())
    if not normalized:
        return None
    if not _CANONICAL_PHONE.fullmatch(normalized):
        raise ValueError('Phone must use international format with a leading plus sign')
    return normalized


async def _get_mapped_customer(
    db: AsyncSession,
    *,
    tenant_id: int,
    connector_key: str,
    external_customer_id: str,
) -> Customer | None:
    return await db.scalar(
        select(Customer)
        .join(
            CustomerExternalIdentity,
            (CustomerExternalIdentity.customer_id == Customer.id)
            & (CustomerExternalIdentity.tenant_id == Customer.tenant_id),
        )
        .where(
            CustomerExternalIdentity.tenant_id == tenant_id,
            CustomerExternalIdentity.connector_key == connector_key,
            CustomerExternalIdentity.external_customer_id == external_customer_id,
        )
    )


async def resolve_external_customer(
    db: AsyncSession,
    customer_port: CustomerPort,
    context: PosRequestContext,
    *,
    external_customer_id: str,
) -> Customer:
    """Resolve one POS identity without contact-based matching or synchronization."""

    normalized_external_id = external_customer_id.strip()
    if not normalized_external_id or len(normalized_external_id) > 200:
        raise ValueError('A valid external Customer identifier is required')

    existing = await _get_mapped_customer(
        db,
        tenant_id=context.tenant_id,
        connector_key=context.connector_key,
        external_customer_id=normalized_external_id,
    )
    if existing is not None:
        logger.info(
            'Customer external identity resolved',
            extra={
                'event': 'customer_external_identity_resolved',
                'operation': 'resolve_external_customer',
                'tenant_id': context.tenant_id,
                'customer_id': existing.id,
                'connector_key': context.connector_key,
                'correlation_id': context.correlation_id,
                'outcome': 'existing',
            },
        )
        return existing

    external = await customer_port.get_customer(
        context,
        external_customer_id=normalized_external_id,
    )
    returned_external_id = external.external_id.strip()
    if returned_external_id != normalized_external_id:
        raise ValueError('POS Customer identifier did not match the requested identifier')

    customer = Customer(
        tenant_id=context.tenant_id,
        display_name=normalize_display_name(external.name),
        email=normalize_email(external.email),
        phone=normalize_phone(external.phone),
        status=(
            'ACTIVE' if external.status is ExternalEntityStatus.ACTIVE else 'INACTIVE'
        ),
        source='POS',
    )
    db.add(customer)
    await db.flush()
    db.add(
        CustomerExternalIdentity(
            tenant_id=context.tenant_id,
            customer_id=customer.id,
            connector_key=context.connector_key,
            external_customer_id=returned_external_id,
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        winner = await _get_mapped_customer(
            db,
            tenant_id=context.tenant_id,
            connector_key=context.connector_key,
            external_customer_id=normalized_external_id,
        )
        if winner is None:
            raise
        customer = winner
        outcome = 'race_recovered'
    else:
        await db.refresh(customer)
        outcome = 'created'

    logger.info(
        'Customer external identity resolved',
        extra={
            'event': 'customer_external_identity_resolved',
            'operation': 'resolve_external_customer',
            'tenant_id': context.tenant_id,
            'customer_id': customer.id,
            'connector_key': context.connector_key,
            'correlation_id': context.correlation_id,
            'outcome': outcome,
        },
    )
    return customer
