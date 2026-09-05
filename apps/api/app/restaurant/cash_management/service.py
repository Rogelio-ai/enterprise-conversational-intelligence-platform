from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.execution import ActorType, ExecutionContext
from app.models import CashCount, CashMovement, CashSession, Location, Resource
from app.restaurant.cash_management import errors
from app.restaurant.cash_management.contracts import (
    CashCountProjection,
    CashMovementProjection,
    CashSessionProjection,
)


REQUEST_SCHEMA_VERSION = 1
ZERO = Decimal('0.0000')
MONEY_UNIT = Decimal('0.0001')
MANUAL_MOVEMENT_TYPES = frozenset({
    'OPENING_FLOAT', 'CASH_IN', 'CASH_OUT', 'WITHDRAWAL', 'ADJUSTMENT',
})
REASON_REQUIRED_TYPES = frozenset({
    'CASH_IN', 'CASH_OUT', 'WITHDRAWAL', 'ADJUSTMENT',
})


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _actor_scope(context: ExecutionContext) -> str:
    identity = (
        str(context.principal_id)
        if context.principal_id is not None
        else context.principal_reference
    )
    return f'{context.actor_type.value}:{identity}'


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':'), ensure_ascii=False
    ).encode()).hexdigest()


def _money(value: Decimal) -> str:
    return format(value.quantize(MONEY_UNIT), 'f')


def _canonical_currency(value: str) -> str:
    currency = value.strip().upper()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise errors.InvalidCashSessionRequestError(
            'Currency must be a three-letter ASCII code'
        )
    return currency


def _exact_money(value: Decimal, *, allow_zero: bool, count: bool = False) -> Decimal:
    error = errors.InvalidCashCountError if count else errors.InvalidCashMovementError
    if isinstance(value, float) or not isinstance(value, Decimal) or not value.is_finite():
        raise error('Amount must be an exact Decimal')
    if value != value.quantize(MONEY_UNIT):
        raise error('Amount supports at most four decimal places')
    if value < ZERO or (value == ZERO and not allow_zero):
        raise error('Amount is outside the allowed range')
    return value


def _text(value: str | None, *, maximum: int, field: str) -> str | None:
    canonical = value.strip() if value is not None else None
    canonical = canonical or None
    if canonical is not None and len(canonical) > maximum:
        raise errors.InvalidCashMovementError(f'{field} is too long')
    return canonical


def _translate_operational(exc: OperationalError) -> None:
    code = exc.orig.args[0] if getattr(exc.orig, 'args', ()) else None
    if code in (1205, 1213):
        raise errors.CashSessionConcurrencyConflictError(
            'Concurrent cash operation lost serialization'
        ) from exc
    raise exc


async def _expected_cash(db: AsyncSession, cash_session_id: int) -> Decimal:
    value = await db.scalar(select(func.sum(CashMovement.amount)).where(
        CashMovement.cash_session_id == cash_session_id
    ))
    return ZERO if value is None else Decimal(value).quantize(MONEY_UNIT)


async def _session_projection(
    db: AsyncSession, value: CashSession
) -> CashSessionProjection:
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
        expected_cash=await _expected_cash(db, value.id),
        opened_at=value.opened_at,
        opened_by_actor_type=value.opened_by_actor_type,
        opened_by_actor_id=value.opened_by_actor_id,
        opened_by_actor_reference=value.opened_by_actor_reference,
        selected_cash_count_id=value.selected_cash_count_id,
        final_movement_version=value.final_movement_version,
        frozen_expected_cash=value.frozen_expected_cash,
        frozen_variance=value.frozen_variance,
        variance_reason=value.variance_reason,
        closed_at=value.closed_at,
        closed_by_actor_type=value.closed_by_actor_type,
        closed_by_actor_id=value.closed_by_actor_id,
        closed_by_actor_reference=value.closed_by_actor_reference,
    )


def _movement_projection(value: CashMovement) -> CashMovementProjection:
    return CashMovementProjection(
        id=value.id,
        cash_session_id=value.cash_session_id,
        movement_type=value.movement_type,
        amount=value.amount,
        currency=value.currency,
        reason=value.reason,
        reference=value.reference,
        recorded_at=value.recorded_at,
        actor_type=value.actor_type,
        actor_id=value.actor_id,
        actor_reference=value.actor_reference,
        authorized_by_actor_type=value.authorized_by_actor_type,
        authorized_by_actor_id=value.authorized_by_actor_id,
        authorized_by_actor_reference=value.authorized_by_actor_reference,
    )


def _count_projection(value: CashCount) -> CashCountProjection:
    return CashCountProjection(
        id=value.id,
        cash_session_id=value.cash_session_id,
        counted_amount=value.counted_amount,
        currency=value.currency,
        captured_movement_version=value.captured_movement_version,
        counted_at=value.counted_at,
        actor_type=value.actor_type,
        actor_id=value.actor_id,
        actor_reference=value.actor_reference,
    )


async def _by_open_key(
    db: AsyncSession, *, context: ExecutionContext,
    idempotency_key: str, lock: bool = False,
) -> CashSession | None:
    statement = select(CashSession).where(
        CashSession.tenant_id == context.tenant_id,
        CashSession.open_actor_scope == _actor_scope(context),
        CashSession.open_idempotency_key == idempotency_key,
    )
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


async def _assert_open_replay(
    db: AsyncSession, value: CashSession, fingerprint: str
) -> CashSessionProjection:
    if value.open_request_fingerprint != fingerprint:
        raise errors.CashSessionIdempotencyConflictError()
    return await _session_projection(db, value)


async def open_cash_session(
    db: AsyncSession, *, context: ExecutionContext, resource_id: int,
    currency: str, idempotency_key: str,
) -> tuple[CashSessionProjection, bool]:
    if context.actor_type is not ActorType.EMPLOYEE or context.principal_id is None:
        raise errors.CashSessionPermissionError(
            'Only an authenticated tenant member may open a CashSession'
        )
    currency = _canonical_currency(currency)
    fingerprint = _sha({
        'schema_version': REQUEST_SCHEMA_VERSION,
        'resource_id': resource_id,
        'currency': currency,
        'cashier_membership_id': context.principal_id,
    })
    existing = await _by_open_key(
        db, context=context, idempotency_key=idempotency_key
    )
    if existing is not None:
        return await _assert_open_replay(db, existing, fingerprint), True
    try:
        resource_identity = await db.scalar(select(Resource).where(
            Resource.id == resource_id, Resource.tenant_id == context.tenant_id,
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
            projection = await _assert_open_replay(db, replay, fingerprint)
            await db.commit()
            return projection, True
        if resource.resource_type != 'CASH_REGISTER':
            raise errors.InvalidCashRegisterError('Resource is not a CASH_REGISTER')
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
        return await _session_projection(db, opened), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await _by_open_key(
            db, context=context, idempotency_key=idempotency_key
        )
        if winner is not None:
            return await _assert_open_replay(db, winner, fingerprint), True
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
    return await _session_projection(db, value)


def _validate_manual_movement(
    *, movement_type: str, amount: Decimal, currency: str,
    reason: str | None, reference: str | None,
) -> tuple[str, Decimal, str, str | None, str | None]:
    movement_type = movement_type.strip().upper()
    if movement_type not in MANUAL_MOVEMENT_TYPES:
        raise errors.InvalidCashMovementError(
            'Movement type is not available for manual creation'
        )
    if isinstance(amount, float) or not isinstance(amount, Decimal) or not amount.is_finite():
        raise errors.InvalidCashMovementError('Amount must be an exact Decimal')
    if amount != amount.quantize(MONEY_UNIT) or amount == ZERO:
        raise errors.InvalidCashMovementError(
            'Movement amount must be non-zero with at most four decimal places'
        )
    if movement_type in ('OPENING_FLOAT', 'CASH_IN') and amount <= ZERO:
        raise errors.InvalidCashMovementError('Movement amount has the wrong sign')
    if movement_type in ('CASH_OUT', 'WITHDRAWAL') and amount >= ZERO:
        raise errors.InvalidCashMovementError('Movement amount has the wrong sign')
    currency = _canonical_currency(currency)
    reason = _text(reason, maximum=500, field='Reason')
    reference = _text(reference, maximum=200, field='Reference')
    if movement_type in REASON_REQUIRED_TYPES and reason is None:
        raise errors.InvalidCashMovementError('Movement reason is required')
    return movement_type, amount, currency, reason, reference


async def _movement_by_key(
    db: AsyncSession, *, context: ExecutionContext,
    idempotency_key: str, lock: bool = False,
) -> CashMovement | None:
    statement = select(CashMovement).where(
        CashMovement.tenant_id == context.tenant_id,
        CashMovement.idempotency_actor_scope == _actor_scope(context),
        CashMovement.idempotency_key == idempotency_key,
    )
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


def _assert_movement_replay(
    value: CashMovement, fingerprint: str
) -> CashMovementProjection:
    if value.request_fingerprint != fingerprint:
        raise errors.CashMovementIdempotencyConflictError()
    return _movement_projection(value)


async def create_manual_movement(
    db: AsyncSession, *, context: ExecutionContext, cash_session_id: int,
    movement_type: str, amount: Decimal, currency: str,
    reason: str | None, reference: str | None, idempotency_key: str,
) -> tuple[CashMovementProjection, bool]:
    movement_type, amount, currency, reason, reference = _validate_manual_movement(
        movement_type=movement_type, amount=amount, currency=currency,
        reason=reason, reference=reference,
    )
    fingerprint = _sha({
        'schema_version': REQUEST_SCHEMA_VERSION,
        'cash_session_id': cash_session_id,
        'movement_type': movement_type,
        'amount': _money(amount),
        'currency': currency,
        'reason': reason,
        'reference': reference,
    })
    existing = await _movement_by_key(
        db, context=context, idempotency_key=idempotency_key
    )
    if existing is not None:
        return _assert_movement_replay(existing, fingerprint), True
    try:
        session = await db.scalar(select(CashSession).where(
            CashSession.id == cash_session_id,
            CashSession.tenant_id == context.tenant_id,
        ).with_for_update())
        if session is None:
            raise errors.CashSessionNotFoundError()
        replay = await _movement_by_key(
            db, context=context, idempotency_key=idempotency_key, lock=True
        )
        if replay is not None:
            projection = _assert_movement_replay(replay, fingerprint)
            await db.commit()
            return projection, True
        if session.status != 'OPEN':
            raise errors.CashSessionClosedError()
        if session.currency != currency:
            raise errors.InvalidCashMovementError(
                'Movement currency differs from CashSession currency'
            )
        if movement_type == 'OPENING_FLOAT':
            prior = await db.scalar(select(CashMovement.id).where(
                CashMovement.cash_session_id == session.id,
                CashMovement.opening_float_slot == 1,
            ).with_for_update())
            if prior is not None:
                raise errors.DuplicateOpeningFloatError()
        now = _now()
        movement = CashMovement(
            tenant_id=session.tenant_id,
            organization_id=session.organization_id,
            location_id=session.location_id,
            cash_session_id=session.id,
            movement_type=movement_type,
            amount=amount,
            currency=currency,
            reason=reason,
            reference=reference,
            recorded_at=now,
            actor_type=context.actor_type.value,
            actor_id=context.principal_id,
            actor_reference=context.principal_reference,
            authorized_by_actor_type=context.actor_type.value,
            authorized_by_actor_id=context.principal_id,
            authorized_by_actor_reference=context.principal_reference,
            opening_float_slot=1 if movement_type == 'OPENING_FLOAT' else None,
            idempotency_actor_scope=_actor_scope(context),
            idempotency_key=idempotency_key,
            request_schema_version=REQUEST_SCHEMA_VERSION,
            request_fingerprint=fingerprint,
        )
        db.add(movement)
        session.movement_version += 1
        await db.commit()
        await db.refresh(movement)
        return _movement_projection(movement), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await _movement_by_key(
            db, context=context, idempotency_key=idempotency_key
        )
        if winner is not None:
            return _assert_movement_replay(winner, fingerprint), True
        if movement_type == 'OPENING_FLOAT':
            raise errors.DuplicateOpeningFloatError() from exc
        raise
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise
    raise AssertionError('CashMovement creation did not return a result')


async def _count_by_key(
    db: AsyncSession, *, context: ExecutionContext,
    idempotency_key: str, lock: bool = False,
) -> CashCount | None:
    statement = select(CashCount).where(
        CashCount.tenant_id == context.tenant_id,
        CashCount.idempotency_actor_scope == _actor_scope(context),
        CashCount.idempotency_key == idempotency_key,
    )
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


def _assert_count_replay(value: CashCount, fingerprint: str) -> CashCountProjection:
    if value.request_fingerprint != fingerprint:
        raise errors.CashCountIdempotencyConflictError()
    return _count_projection(value)


async def create_cash_count(
    db: AsyncSession, *, context: ExecutionContext, cash_session_id: int,
    counted_amount: Decimal, currency: str, idempotency_key: str,
) -> tuple[CashCountProjection, bool]:
    counted_amount = _exact_money(counted_amount, allow_zero=True, count=True)
    currency = _canonical_currency(currency)
    fingerprint = _sha({
        'schema_version': REQUEST_SCHEMA_VERSION,
        'cash_session_id': cash_session_id,
        'counted_amount': _money(counted_amount),
        'currency': currency,
    })
    existing = await _count_by_key(
        db, context=context, idempotency_key=idempotency_key
    )
    if existing is not None:
        return _assert_count_replay(existing, fingerprint), True
    try:
        session = await db.scalar(select(CashSession).where(
            CashSession.id == cash_session_id,
            CashSession.tenant_id == context.tenant_id,
        ).with_for_update())
        if session is None:
            raise errors.CashSessionNotFoundError()
        replay = await _count_by_key(
            db, context=context, idempotency_key=idempotency_key, lock=True
        )
        if replay is not None:
            projection = _assert_count_replay(replay, fingerprint)
            await db.commit()
            return projection, True
        if session.status != 'OPEN':
            raise errors.CashSessionClosedError()
        if session.currency != currency:
            raise errors.InvalidCashCountError(
                'Count currency differs from CashSession currency'
            )
        count = CashCount(
            tenant_id=session.tenant_id,
            organization_id=session.organization_id,
            location_id=session.location_id,
            cash_session_id=session.id,
            counted_amount=counted_amount,
            currency=currency,
            captured_movement_version=session.movement_version,
            counted_at=_now(),
            actor_type=context.actor_type.value,
            actor_id=context.principal_id,
            actor_reference=context.principal_reference,
            idempotency_actor_scope=_actor_scope(context),
            idempotency_key=idempotency_key,
            request_schema_version=REQUEST_SCHEMA_VERSION,
            request_fingerprint=fingerprint,
        )
        db.add(count)
        await db.commit()
        await db.refresh(count)
        return _count_projection(count), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await _count_by_key(
            db, context=context, idempotency_key=idempotency_key
        )
        if winner is not None:
            return _assert_count_replay(winner, fingerprint), True
        raise exc
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise
    raise AssertionError('CashCount creation did not return a result')


def _close_fingerprint(
    *, cash_session_id: int, cash_count_id: int, variance_reason: str | None
) -> str:
    return _sha({
        'schema_version': REQUEST_SCHEMA_VERSION,
        'cash_session_id': cash_session_id,
        'cash_count_id': cash_count_id,
        'variance_reason': variance_reason,
    })


async def _close_by_key(
    db: AsyncSession, *, context: ExecutionContext, idempotency_key: str
) -> CashSession | None:
    return await db.scalar(select(CashSession).where(
        CashSession.tenant_id == context.tenant_id,
        CashSession.close_actor_scope == _actor_scope(context),
        CashSession.close_idempotency_key == idempotency_key,
    ))


async def close_cash_session(
    db: AsyncSession, *, context: ExecutionContext, cash_session_id: int,
    cash_count_id: int, variance_reason: str | None, idempotency_key: str,
) -> tuple[CashSessionProjection, bool]:
    reason = _text(variance_reason, maximum=500, field='Variance reason')
    try:
        session = await db.scalar(select(CashSession).where(
            CashSession.id == cash_session_id,
            CashSession.tenant_id == context.tenant_id,
        ).with_for_update())
        if session is None:
            raise errors.CashSessionNotFoundError()
        if session.status == 'CLOSED':
            effective_reason = None if session.frozen_variance == ZERO else reason
            fingerprint = _close_fingerprint(
                cash_session_id=cash_session_id,
                cash_count_id=cash_count_id,
                variance_reason=effective_reason,
            )
            if (
                session.close_actor_scope == _actor_scope(context)
                and session.close_idempotency_key == idempotency_key
            ):
                if session.close_request_fingerprint != fingerprint:
                    raise errors.CashSessionCloseIdempotencyConflictError()
                await db.commit()
                return await _session_projection(db, session), True
            raise errors.CashSessionCloseConflictError(
                'CashSession is already CLOSED'
            )
        count = await db.scalar(select(CashCount).where(
            CashCount.id == cash_count_id,
            CashCount.tenant_id == context.tenant_id,
        ).with_for_update())
        if count is None:
            raise errors.CashCountNotFoundError()
        if count.cash_session_id != session.id:
            raise errors.CashCountSessionConflictError()
        if count.currency != session.currency:
            raise errors.CashCountSessionConflictError(
                'CashCount currency differs from CashSession currency'
            )
        if count.captured_movement_version != session.movement_version:
            raise errors.StaleCashCountError()
        expected = await _expected_cash(db, session.id)
        variance = (Decimal(count.counted_amount) - expected).quantize(MONEY_UNIT)
        effective_reason = None if variance == ZERO else reason
        if variance != ZERO and effective_reason is None:
            raise errors.CashSessionVarianceReasonRequiredError()
        fingerprint = _close_fingerprint(
            cash_session_id=session.id,
            cash_count_id=count.id,
            variance_reason=effective_reason,
        )
        other = await _close_by_key(
            db, context=context, idempotency_key=idempotency_key
        )
        if other is not None:
            if other.close_request_fingerprint != fingerprint:
                raise errors.CashSessionCloseIdempotencyConflictError()
            await db.commit()
            return await _session_projection(db, other), True
        now = _now()
        session.selected_cash_count_id = count.id
        session.final_movement_version = session.movement_version
        session.frozen_expected_cash = expected
        session.frozen_variance = variance
        session.variance_reason = effective_reason
        session.closed_at = now
        session.closed_by_actor_type = context.actor_type.value
        session.closed_by_actor_id = context.principal_id
        session.closed_by_actor_reference = context.principal_reference
        session.close_actor_scope = _actor_scope(context)
        session.close_idempotency_key = idempotency_key
        session.close_request_schema_version = REQUEST_SCHEMA_VERSION
        session.close_request_fingerprint = fingerprint
        session.status = 'CLOSED'
        session.open_slot = None
        await db.commit()
        await db.refresh(session)
        return await _session_projection(db, session), False
    except IntegrityError as exc:
        await db.rollback()
        winner = await _close_by_key(
            db, context=context, idempotency_key=idempotency_key
        )
        if winner is not None:
            effective_reason = None if winner.frozen_variance == ZERO else reason
            fingerprint = _close_fingerprint(
                cash_session_id=cash_session_id,
                cash_count_id=cash_count_id,
                variance_reason=effective_reason,
            )
            if winner.close_request_fingerprint != fingerprint:
                raise errors.CashSessionCloseIdempotencyConflictError() from exc
            return await _session_projection(db, winner), True
        raise
    except OperationalError as exc:
        await db.rollback()
        _translate_operational(exc)
    except Exception:
        await db.rollback()
        raise
    raise AssertionError('CashSession close did not return a result')
