from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import CashSession, Location, Resource
from app.restaurant.cash_management import errors
from app.restaurant.cash_management.contracts import CashSessionProjection


REQUEST_SCHEMA_VERSION = 1


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _actor_scope(context: ExecutionContext) -> str:
    identity = (
        str(context.principal_id)
        if context.principal_id is not None
        else context.principal_reference
    )
    return f'{context.actor_type.value}:{identity}'


def _fingerprint(*, resource_id: int, currency: str, cashier_membership_id: int) -> str:
    value = {
        'schema_version': REQUEST_SCHEMA_VERSION,
        'resource_id': resource_id,
        'currency': currency,
        'cashier_membership_id': cashier_membership_id,
    }
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False
    ).encode()).hexdigest()


def _projection(value: CashSession) -> CashSessionProjection:
    return CashSessionProjection(
        id=value.id,
        tenant_id=value.tenant_id,
        organization_id=value.organization_id,
        location_id=value.location_id,
        resource_id=value.resource_id,
        cashier_membership_id=value.cashier_membership_id,
        currency=value.currency,
        status=value.status,
        movement_version=value.movement_version,
        opened_at=value.opened_at,
        opened_by_actor_type=value.opened_by_actor_type,
        opened_by_actor_id=value.opened_by_actor_id,
        opened_by_actor_reference=value.opened_by_actor_reference,
    )


def _canonical_currency(value: str) -> str:
    currency = value.strip().upper()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise errors.InvalidCashSessionRequestError(
            'Currency must be a three-letter ASCII code'
        )
    return currency


def _translate_operational(exc: OperationalError) -> None:
    code = exc.orig.args[0] if getattr(exc.orig, 'args', ()) else None
    if code in (1205, 1213):
        raise errors.CashSessionConcurrencyConflictError(
            'Concurrent CashSession operation lost serialization'
        ) from exc
    raise exc


async def _by_open_key(
    db: AsyncSession,
    *,
    context: ExecutionContext,
    idempotency_key: str,
    lock: bool = False,
) -> CashSession | None:
    statement = select(CashSession).where(
        CashSession.tenant_id == context.tenant_id,
        CashSession.open_actor_scope == _actor_scope(context),
        CashSession.open_idempotency_key == idempotency_key,
    )
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


def _assert_replay(value: CashSession, fingerprint: str) -> CashSessionProjection:
    if value.open_request_fingerprint != fingerprint:
        raise errors.CashSessionIdempotencyConflictError()
    return _projection(value)


async def open_cash_session(
    db: AsyncSession,
    *,
    context: ExecutionContext,
    resource_id: int,
    currency: str,
    idempotency_key: str,
) -> tuple[CashSessionProjection, bool]:
    if context.actor_type is not ActorType.EMPLOYEE or context.principal_id is None:
        raise errors.CashSessionPermissionError(
            'Only an authenticated tenant member may open a CashSession'
        )
    currency = _canonical_currency(currency)
    fingerprint = _fingerprint(
        resource_id=resource_id,
        currency=currency,
        cashier_membership_id=context.principal_id,
    )
    existing = await _by_open_key(
        db, context=context, idempotency_key=idempotency_key
    )
    if existing is not None:
        return _assert_replay(existing, fingerprint), True

    try:
        resource_identity = await db.scalar(select(Resource).where(
            Resource.id == resource_id,
            Resource.tenant_id == context.tenant_id,
        ))
        if resource_identity is None:
            raise errors.CashRegisterNotFoundError()
        location = await db.scalar(select(Location).where(
            Location.id == resource_identity.location_id,
            Location.tenant_id == context.tenant_id,
        ).with_for_update())
        if location is None:
            raise errors.CashRegisterNotFoundError()
        resource = await db.scalar(select(Resource).where(
            Resource.id == resource_id,
            Resource.tenant_id == context.tenant_id,
            Resource.location_id == location.id,
        ).with_for_update())
        if resource is None:
            raise errors.CashRegisterNotFoundError()
        replay = await _by_open_key(
            db, context=context, idempotency_key=idempotency_key, lock=True
        )
        if replay is not None:
            projection = _assert_replay(replay, fingerprint)
            await db.commit()
            return projection, True
        if resource.resource_type != 'CASH_REGISTER':
            raise errors.InvalidCashRegisterError(
                'Resource is not a CASH_REGISTER'
            )
        if resource.status != 'ACTIVE':
            raise errors.CashRegisterInactiveError()
        if location.cash_management_activated_at is None:
            raise errors.CashManagementNotActivatedError()
        current = await db.scalar(select(CashSession).where(
            CashSession.resource_id == resource.id,
            CashSession.open_slot == 1,
        ).with_for_update())
        if current is not None:
            raise errors.ActiveCashSessionExistsError()
        opened = CashSession(
            tenant_id=context.tenant_id,
            organization_id=location.organization_id,
            location_id=location.id,
            resource_id=resource.id,
            cashier_membership_id=context.principal_id,
            currency=currency,
            status='OPEN',
            opened_at=_now(),
            opened_by_actor_type=context.actor_type.value,
            opened_by_actor_id=context.principal_id,
            opened_by_actor_reference=context.principal_reference,
            movement_version=0,
            open_slot=1,
            open_actor_scope=_actor_scope(context),
            open_idempotency_key=idempotency_key,
            open_request_schema_version=REQUEST_SCHEMA_VERSION,
            open_request_fingerprint=fingerprint,
        )
        db.add(opened)
        await db.commit()
        await db.refresh(opened)
        return _projection(opened), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await _by_open_key(
            db, context=context, idempotency_key=idempotency_key
        )
        if winner is not None:
            return _assert_replay(winner, fingerprint), True
        raise errors.ActiveCashSessionExistsError() from exc
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise
    raise AssertionError('CashSession opening did not return a result')


async def get_cash_session(
    db: AsyncSession, *, tenant_id: int, cash_session_id: int
) -> CashSessionProjection:
    value = await db.scalar(select(CashSession).where(
        CashSession.id == cash_session_id,
        CashSession.tenant_id == tenant_id,
    ))
    if value is None:
        raise errors.CashSessionNotFoundError()
    return _projection(value)
