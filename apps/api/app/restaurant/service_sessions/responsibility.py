"""Service-owned current waiter responsibility and append-only transitions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Resource,
    RestaurantServiceSession,
    ServiceResponsibleWaiter,
    ServiceResponsibilityTransition,
    TableWaiterAssignment,
)
from app.restaurant.waiter_eligibility import eligible_waiter_ids


class ServiceResponsibilityError(ValueError):
    pass


class ServiceResponsibilityValidationError(ServiceResponsibilityError):
    pass


class ServiceResponsibilityConflictError(ServiceResponsibilityError):
    pass


class ServiceResponsibilityNotFoundError(ServiceResponsibilityError):
    pass


class ServiceResponsibilityNotInitializedError(ServiceResponsibilityConflictError):
    code = 'SERVICE_RESPONSIBILITY_NOT_INITIALIZED'


class ServiceResponsibilityVersionConflictError(ServiceResponsibilityConflictError):
    pass


class ServiceResponsibilityIdempotencyConflictError(ServiceResponsibilityConflictError):
    pass


@dataclass(frozen=True, slots=True)
class ServiceResponsibilityValue:
    service_session_id: int
    location_id: int
    resource_id: int
    version: int
    responsible_membership_ids: tuple[int, ...]
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class ServiceResponsibilityTransitionValue:
    service_session_id: int
    operation: str
    result_version: int
    before_responsible_membership_ids: tuple[int, ...]
    after_responsible_membership_ids: tuple[int, ...]
    actor_membership_id: int
    correlation_id: str | None
    idempotency_key: str
    source_table_assignment_version: int | None
    recorded_at: datetime


def _complete_set(membership_ids: Sequence[int]) -> tuple[int, ...]:
    values = tuple(membership_ids)
    if not values:
        raise ServiceResponsibilityValidationError(
            'At least one responsible waiter is required',
        )
    if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in values):
        raise ServiceResponsibilityValidationError(
            'Responsible waiter identifiers must be positive integers',
        )
    if len(set(values)) != len(values):
        raise ServiceResponsibilityValidationError(
            'Responsible waiter identifiers must be unique',
        )
    return tuple(sorted(values))


def _idempotency_key(value: str) -> str:
    if value != value.strip() or not value or len(value) > 128 or not value.isascii():
        raise ServiceResponsibilityValidationError('Invalid idempotency key')
    return value


def _fingerprint(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _actor_scope(actor_membership_id: int) -> str:
    return f'MEMBERSHIP:{actor_membership_id}'


async def _locked_session(
    db: AsyncSession, *, tenant_id: int, service_session_id: int,
) -> RestaurantServiceSession:
    resource_id = await db.scalar(
        select(RestaurantServiceSession.resource_id).where(
            RestaurantServiceSession.id == service_session_id,
            RestaurantServiceSession.tenant_id == tenant_id,
        )
    )
    if resource_id is None:
        raise ServiceResponsibilityNotFoundError('Restaurant Service Session not found')
    resource = await db.scalar(
        select(Resource).where(
            Resource.id == resource_id, Resource.tenant_id == tenant_id,
        ).with_for_update()
    )
    if resource is None:
        raise ServiceResponsibilityNotFoundError('Restaurant Service Session not found')
    session = await db.scalar(
        select(RestaurantServiceSession).where(
            RestaurantServiceSession.id == service_session_id,
            RestaurantServiceSession.tenant_id == tenant_id,
            RestaurantServiceSession.resource_id == resource.id,
        ).with_for_update()
    )
    if session is None:
        raise ServiceResponsibilityNotFoundError('Restaurant Service Session not found')
    return session


async def _current_rows(
    db: AsyncSession, *, tenant_id: int, service_session_id: int, lock: bool = False,
) -> list[ServiceResponsibleWaiter]:
    statement = select(ServiceResponsibleWaiter).where(
        ServiceResponsibleWaiter.tenant_id == tenant_id,
        ServiceResponsibleWaiter.service_session_id == service_session_id,
    ).order_by(ServiceResponsibleWaiter.waiter_membership_id)
    if lock:
        statement = statement.with_for_update()
    return list((await db.scalars(statement)).all())


async def _latest_transition(
    db: AsyncSession, *, tenant_id: int, service_session_id: int, lock: bool = False,
) -> ServiceResponsibilityTransition | None:
    statement = (
        select(ServiceResponsibilityTransition)
        .where(
            ServiceResponsibilityTransition.tenant_id == tenant_id,
            ServiceResponsibilityTransition.service_session_id == service_session_id,
        )
        .order_by(ServiceResponsibilityTransition.result_version.desc())
        .limit(1)
    )
    if lock:
        statement = statement.with_for_update()
    return await db.scalar(statement)


async def _replay(
    db: AsyncSession, *, tenant_id: int, actor_scope: str, idempotency_key: str,
    operation: str, request_fingerprint: str,
) -> ServiceResponsibilityTransition | None:
    transition = await db.scalar(
        select(ServiceResponsibilityTransition).where(
            ServiceResponsibilityTransition.tenant_id == tenant_id,
            ServiceResponsibilityTransition.idempotency_actor_scope == actor_scope,
            ServiceResponsibilityTransition.idempotency_key == idempotency_key,
        ).with_for_update()
    )
    if transition is not None and (
        transition.operation != operation
        or transition.request_fingerprint != request_fingerprint
    ):
        raise ServiceResponsibilityIdempotencyConflictError(
            'Idempotency key was already used for a different responsibility request',
        )
    return transition


async def _validate_waiters(
    db: AsyncSession, *, session: RestaurantServiceSession,
    membership_ids: tuple[int, ...],
) -> None:
    eligible = await eligible_waiter_ids(
        db, tenant_id=session.tenant_id, location_id=session.location_id,
        membership_ids=membership_ids,
    )
    if eligible != set(membership_ids):
        raise ServiceResponsibilityValidationError(
            'Every responsible waiter must be eligible for the service location',
        )
    assigned = set((await db.scalars(
        select(TableWaiterAssignment.waiter_membership_id).where(
            TableWaiterAssignment.tenant_id == session.tenant_id,
            TableWaiterAssignment.location_id == session.location_id,
            TableWaiterAssignment.table_resource_id == session.resource_id,
            TableWaiterAssignment.waiter_membership_id.in_(membership_ids),
        ).with_for_update()
    )).all())
    if assigned != set(membership_ids):
        raise ServiceResponsibilityValidationError(
            'Every responsible waiter must be assigned to the service table',
        )


def _value(
    session: RestaurantServiceSession, *, version: int,
    membership_ids: Sequence[int], replayed: bool = False,
) -> ServiceResponsibilityValue:
    return ServiceResponsibilityValue(
        service_session_id=session.id,
        location_id=session.location_id,
        resource_id=session.resource_id,
        version=version,
        responsible_membership_ids=tuple(sorted(membership_ids)),
        replayed=replayed,
    )


def _add_transition(
    db: AsyncSession, *, session: RestaurantServiceSession, operation: str,
    result_version: int, before_ids: Sequence[int], after_ids: Sequence[int],
    actor_membership_id: int, correlation_id: str | None, actor_scope: str,
    idempotency_key: str, request_fingerprint: str,
    source_table_assignment_version: int | None,
) -> None:
    db.add(ServiceResponsibilityTransition(
        tenant_id=session.tenant_id,
        organization_id=session.organization_id,
        location_id=session.location_id,
        resource_id=session.resource_id,
        service_session_id=session.id,
        operation=operation,
        result_version=result_version,
        before_responsible_membership_ids=list(before_ids),
        after_responsible_membership_ids=list(after_ids),
        actor_membership_id=actor_membership_id,
        correlation_id=correlation_id,
        idempotency_actor_scope=actor_scope,
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
        source_table_assignment_version=source_table_assignment_version,
    ))


async def _commit(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ServiceResponsibilityConflictError(
            'Service responsibility changed concurrently; refresh and retry',
        ) from exc
    except OperationalError as exc:
        await db.rollback()
        code = exc.orig.args[0] if getattr(exc.orig, 'args', ()) else None
        if code in (1205, 1213):
            raise ServiceResponsibilityConflictError(
                'Concurrent service responsibility operation lost serialization',
            ) from exc
        raise


async def _raise_operational_conflict(
    db: AsyncSession, exc: OperationalError,
) -> NoReturn:
    await db.rollback()
    code = exc.orig.args[0] if getattr(exc.orig, 'args', ()) else None
    if code in (1205, 1213):
        raise ServiceResponsibilityConflictError(
            'Concurrent service responsibility operation lost serialization',
        ) from exc
    raise exc


async def initialize_service_responsibility(
    db: AsyncSession, *, tenant_id: int, service_session_id: int,
    responsible_membership_ids: Sequence[int], actor_membership_id: int,
    idempotency_key: str, correlation_id: str | None = None,
    source_table_assignment_version: int | None = None,
) -> ServiceResponsibilityValue:
    membership_ids = _complete_set(responsible_membership_ids)
    key = _idempotency_key(idempotency_key)
    if source_table_assignment_version is not None and source_table_assignment_version < 0:
        raise ServiceResponsibilityValidationError(
            'Source table assignment version cannot be negative',
        )
    actor_scope = _actor_scope(actor_membership_id)
    fingerprint = _fingerprint({
        'service_session_id': service_session_id,
        'operation': 'INITIALIZE',
        'responsible_membership_ids': membership_ids,
        'source_table_assignment_version': source_table_assignment_version,
    })
    try:
        session = await _locked_session(
            db, tenant_id=tenant_id, service_session_id=service_session_id,
        )
        rows = await _current_rows(
            db, tenant_id=tenant_id, service_session_id=service_session_id, lock=True,
        )
        latest = await _latest_transition(
            db, tenant_id=tenant_id, service_session_id=service_session_id, lock=True,
        )
        replay = await _replay(
            db, tenant_id=tenant_id, actor_scope=actor_scope, idempotency_key=key,
            operation='INITIALIZE', request_fingerprint=fingerprint,
        )
        if replay is not None:
            await db.commit()
            return _value(
                session, version=replay.result_version,
                membership_ids=replay.after_responsible_membership_ids, replayed=True,
            )
        if session.status != 'OPEN':
            raise ServiceResponsibilityConflictError(
                'Responsibility can only be initialized for an OPEN service',
            )
        if rows or latest is not None:
            raise ServiceResponsibilityConflictError(
                'Service responsibility is already initialized',
            )
        await _validate_waiters(db, session=session, membership_ids=membership_ids)
        for membership_id in membership_ids:
            db.add(ServiceResponsibleWaiter(
                tenant_id=session.tenant_id,
                organization_id=session.organization_id,
                location_id=session.location_id,
                resource_id=session.resource_id,
                service_session_id=session.id,
                waiter_membership_id=membership_id,
            ))
        _add_transition(
            db, session=session, operation='INITIALIZE', result_version=1,
            before_ids=(), after_ids=membership_ids,
            actor_membership_id=actor_membership_id, correlation_id=correlation_id,
            actor_scope=actor_scope, idempotency_key=key,
            request_fingerprint=fingerprint,
            source_table_assignment_version=source_table_assignment_version,
        )
        await _commit(db)
        return _value(session, version=1, membership_ids=membership_ids)
    except OperationalError as exc:
        await _raise_operational_conflict(db, exc)
    except Exception:
        if db.in_transaction():
            await db.rollback()
        raise


async def replace_service_responsibility(
    db: AsyncSession, *, tenant_id: int, service_session_id: int,
    responsible_membership_ids: Sequence[int], expected_version: int,
    actor_membership_id: int, idempotency_key: str,
    correlation_id: str | None = None,
) -> ServiceResponsibilityValue:
    membership_ids = _complete_set(responsible_membership_ids)
    key = _idempotency_key(idempotency_key)
    if expected_version < 1:
        raise ServiceResponsibilityValidationError('Expected version must be at least 1')
    actor_scope = _actor_scope(actor_membership_id)
    fingerprint = _fingerprint({
        'service_session_id': service_session_id,
        'operation': 'RESPONSIBILITY_UPDATE',
        'responsible_membership_ids': membership_ids,
        'expected_version': expected_version,
    })
    try:
        session = await _locked_session(
            db, tenant_id=tenant_id, service_session_id=service_session_id,
        )
        rows = await _current_rows(
            db, tenant_id=tenant_id, service_session_id=service_session_id, lock=True,
        )
        latest = await _latest_transition(
            db, tenant_id=tenant_id, service_session_id=service_session_id, lock=True,
        )
        replay = await _replay(
            db, tenant_id=tenant_id, actor_scope=actor_scope, idempotency_key=key,
            operation='RESPONSIBILITY_UPDATE', request_fingerprint=fingerprint,
        )
        if replay is not None:
            await db.commit()
            return _value(
                session, version=replay.result_version,
                membership_ids=replay.after_responsible_membership_ids, replayed=True,
            )
        if session.status != 'OPEN':
            raise ServiceResponsibilityConflictError(
                'Responsibility can only be changed for an OPEN service',
            )
        if latest is None or not rows:
            raise ServiceResponsibilityNotInitializedError(
                'Service responsibility is not initialized',
            )
        if latest.result_version != expected_version:
            raise ServiceResponsibilityVersionConflictError(
                'Service responsibility changed; refresh and retry',
            )
        before_ids = tuple(row.waiter_membership_id for row in rows)
        if tuple(sorted(latest.after_responsible_membership_ids)) != before_ids:
            raise ServiceResponsibilityConflictError(
                'Current responsibility state does not match its transition history',
            )
        await _validate_waiters(db, session=session, membership_ids=membership_ids)
        new_ids = set(membership_ids)
        for row in rows:
            if row.waiter_membership_id not in new_ids:
                await db.delete(row)
        existing_ids = set(before_ids)
        for membership_id in new_ids - existing_ids:
            db.add(ServiceResponsibleWaiter(
                tenant_id=session.tenant_id,
                organization_id=session.organization_id,
                location_id=session.location_id,
                resource_id=session.resource_id,
                service_session_id=session.id,
                waiter_membership_id=membership_id,
            ))
        result_version = latest.result_version + 1
        _add_transition(
            db, session=session, operation='RESPONSIBILITY_UPDATE',
            result_version=result_version, before_ids=before_ids,
            after_ids=membership_ids, actor_membership_id=actor_membership_id,
            correlation_id=correlation_id, actor_scope=actor_scope,
            idempotency_key=key, request_fingerprint=fingerprint,
            source_table_assignment_version=None,
        )
        await _commit(db)
        return _value(
            session, version=result_version, membership_ids=membership_ids,
        )
    except OperationalError as exc:
        await _raise_operational_conflict(db, exc)
    except Exception:
        if db.in_transaction():
            await db.rollback()
        raise


async def get_current_service_responsibility(
    db: AsyncSession, *, tenant_id: int, service_session_id: int,
) -> ServiceResponsibilityValue:
    session = await db.scalar(select(RestaurantServiceSession).where(
        RestaurantServiceSession.id == service_session_id,
        RestaurantServiceSession.tenant_id == tenant_id,
    ))
    if session is None:
        raise ServiceResponsibilityNotFoundError('Restaurant Service Session not found')
    rows = await _current_rows(
        db, tenant_id=tenant_id, service_session_id=service_session_id,
    )
    latest = await _latest_transition(
        db, tenant_id=tenant_id, service_session_id=service_session_id,
    )
    if latest is None or not rows:
        raise ServiceResponsibilityNotInitializedError(
            'Service responsibility is not initialized',
        )
    membership_ids = tuple(row.waiter_membership_id for row in rows)
    if tuple(sorted(latest.after_responsible_membership_ids)) != membership_ids:
        raise ServiceResponsibilityConflictError(
            'Current responsibility state does not match its transition history',
        )
    return _value(
        session, version=latest.result_version, membership_ids=membership_ids,
    )


async def get_service_responsibility_history(
    db: AsyncSession, *, tenant_id: int, service_session_id: int,
) -> tuple[ServiceResponsibilityTransitionValue, ...]:
    exists = await db.scalar(select(RestaurantServiceSession.id).where(
        RestaurantServiceSession.id == service_session_id,
        RestaurantServiceSession.tenant_id == tenant_id,
    ))
    if exists is None:
        raise ServiceResponsibilityNotFoundError('Restaurant Service Session not found')
    transitions = (await db.scalars(
        select(ServiceResponsibilityTransition).where(
            ServiceResponsibilityTransition.tenant_id == tenant_id,
            ServiceResponsibilityTransition.service_session_id == service_session_id,
        ).order_by(ServiceResponsibilityTransition.result_version)
    )).all()
    return tuple(ServiceResponsibilityTransitionValue(
        service_session_id=value.service_session_id,
        operation=value.operation,
        result_version=value.result_version,
        before_responsible_membership_ids=tuple(
            value.before_responsible_membership_ids
        ),
        after_responsible_membership_ids=tuple(value.after_responsible_membership_ids),
        actor_membership_id=value.actor_membership_id,
        correlation_id=value.correlation_id,
        idempotency_key=value.idempotency_key,
        source_table_assignment_version=value.source_table_assignment_version,
        recorded_at=value.recorded_at,
    ) for value in transitions)


async def assert_waiter_not_responsible_for_open_service(
    db: AsyncSession, *, tenant_id: int, table_resource_id: int,
    waiter_membership_id: int,
) -> None:
    """Protect only persisted responsibility for the table's OPEN service."""
    session = await db.scalar(
        select(RestaurantServiceSession).where(
            RestaurantServiceSession.tenant_id == tenant_id,
            RestaurantServiceSession.resource_id == table_resource_id,
            RestaurantServiceSession.open_slot == 1,
        ).with_for_update()
    )
    if session is None:
        return
    responsible = await db.scalar(
        select(ServiceResponsibleWaiter.id).where(
            ServiceResponsibleWaiter.tenant_id == tenant_id,
            ServiceResponsibleWaiter.service_session_id == session.id,
            ServiceResponsibleWaiter.waiter_membership_id == waiter_membership_id,
        ).with_for_update()
    )
    if responsible is not None:
        raise ServiceResponsibilityConflictError(
            'Waiter remains responsible for the open Restaurant Service Session',
        )
