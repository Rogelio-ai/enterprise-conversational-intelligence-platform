from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db.session import DatabaseManager
from app.restaurant.service_sessions import responsibility
from test_resource_foundation import _execute, _location
from test_table_waiter_assignments import (
    _membership_id,
    _setup,
    _waiter,
)


@dataclass(frozen=True)
class ResponsibilityScope:
    tenant_id: int
    organization_id: int
    location_id: int
    resource_id: int
    service_session_id: int
    actor_membership_id: int
    waiter_ids: tuple[int, ...]


def _service_scope(
    connection, prefix: str, *, waiter_count: int = 3,
    waiter_capabilities: tuple[str, ...] = (
        'order_draft.manage', 'restaurant_service.manage',
    ),
) -> ResponsibilityScope:
    actor, location_id, resource_id, _ = _setup(connection, prefix)
    actor_membership_id = _membership_id(connection, actor)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT organization_id FROM locations WHERE id=%s', (location_id,),
        )
        organization_id = int(cursor.fetchone()['organization_id'])
    waiter_ids = tuple(_waiter(
        connection, tenant_id=actor.tenant_id, location_id=location_id,
        prefix=prefix, label=f'responsibility-{index}',
        capabilities=waiter_capabilities,
    ) for index in range(1, waiter_count + 1))
    for waiter_id in waiter_ids:
        _execute(
            connection,
            'INSERT INTO table_waiter_assignments '
            '(tenant_id,location_id,table_resource_id,waiter_membership_id,is_responsible) '
            'VALUES (%s,%s,%s,%s,1)',
            (actor.tenant_id, location_id, resource_id, waiter_id),
        )
    service_session_id = _execute(
        connection,
        'INSERT INTO restaurant_service_sessions '
        '(tenant_id,organization_id,location_id,resource_id,party_size,status,open_slot,'
        'join_context_key,access_code_digest,access_code_version,failed_join_attempts,'
        'opened_by_membership_id,opened_at) '
        "VALUES (%s,%s,%s,%s,2,'OPEN',1,%s,%s,1,0,%s,%s)",
        (
            actor.tenant_id, organization_id, location_id, resource_id,
            uuid4().hex, 'a' * 64, actor_membership_id,
            datetime.now(UTC).replace(tzinfo=None),
        ),
    )
    return ResponsibilityScope(
        tenant_id=actor.tenant_id,
        organization_id=organization_id,
        location_id=location_id,
        resource_id=resource_id,
        service_session_id=service_session_id,
        actor_membership_id=actor_membership_id,
        waiter_ids=waiter_ids,
    )


def _call(settings, operation, **kwargs):
    async def execute():
        manager = DatabaseManager(settings)
        try:
            async with manager.session_factory() as db:
                return await operation(db, **kwargs)
        finally:
            await manager.dispose()

    return asyncio.run(execute())


@pytest.mark.parametrize('initial_count', [1, 2])
def test_initialize_current_and_history_support_shared_responsibility(
    sql_connection, integration_settings, initial_count,
) -> None:
    connection, prefix = sql_connection
    scope = _service_scope(connection, prefix)
    initial = scope.waiter_ids[:initial_count]
    value = _call(
        integration_settings, responsibility.initialize_service_responsibility,
        tenant_id=scope.tenant_id, service_session_id=scope.service_session_id,
        responsible_membership_ids=initial,
        actor_membership_id=scope.actor_membership_id,
        idempotency_key=f'initialize-{initial_count}', correlation_id='corr-initialize',
        source_table_assignment_version=7,
    )
    assert value.service_session_id == scope.service_session_id
    assert value.version == 1
    assert value.responsible_membership_ids == initial
    replay = _call(
        integration_settings, responsibility.initialize_service_responsibility,
        tenant_id=scope.tenant_id, service_session_id=scope.service_session_id,
        responsible_membership_ids=initial,
        actor_membership_id=scope.actor_membership_id,
        idempotency_key=f'initialize-{initial_count}',
        correlation_id='different-retry-correlation',
        source_table_assignment_version=7,
    )
    assert replay.version == 1
    assert replay.responsible_membership_ids == initial
    assert replay.replayed is True

    current = _call(
        integration_settings, responsibility.get_current_service_responsibility,
        tenant_id=scope.tenant_id, service_session_id=scope.service_session_id,
    )
    history = _call(
        integration_settings, responsibility.get_service_responsibility_history,
        tenant_id=scope.tenant_id, service_session_id=scope.service_session_id,
    )
    assert current == value
    assert len(history) == 1
    assert history[0].operation == 'INITIALIZE'
    assert history[0].result_version == 1
    assert history[0].before_responsible_membership_ids == ()
    assert history[0].after_responsible_membership_ids == initial
    assert history[0].actor_membership_id == scope.actor_membership_id
    assert history[0].correlation_id == 'corr-initialize'
    assert history[0].source_table_assignment_version == 7


def test_initialize_rejects_empty_duplicate_invalid_and_already_initialized(
    sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _service_scope(connection, prefix)
    common = {
        'tenant_id': scope.tenant_id,
        'service_session_id': scope.service_session_id,
        'actor_membership_id': scope.actor_membership_id,
    }
    with pytest.raises(responsibility.ServiceResponsibilityValidationError):
        _call(
            integration_settings, responsibility.initialize_service_responsibility,
            **common, responsible_membership_ids=[], idempotency_key='empty',
        )
    with pytest.raises(responsibility.ServiceResponsibilityValidationError):
        _call(
            integration_settings, responsibility.initialize_service_responsibility,
            **common,
            responsible_membership_ids=[scope.waiter_ids[0], scope.waiter_ids[0]],
            idempotency_key='duplicate',
        )
    with pytest.raises(responsibility.ServiceResponsibilityNotFoundError):
        _call(
            integration_settings, responsibility.initialize_service_responsibility,
            tenant_id=scope.tenant_id, service_session_id=999999999,
            responsible_membership_ids=[scope.waiter_ids[0]],
            actor_membership_id=scope.actor_membership_id,
            idempotency_key='missing-service',
        )
    _call(
        integration_settings, responsibility.initialize_service_responsibility,
        **common, responsible_membership_ids=[scope.waiter_ids[0]],
        idempotency_key='first-initialize',
    )
    with pytest.raises(responsibility.ServiceResponsibilityConflictError):
        _call(
            integration_settings, responsibility.initialize_service_responsibility,
            **common, responsible_membership_ids=[scope.waiter_ids[0]],
            idempotency_key='second-initialize',
        )


def test_complete_set_replacement_versions_history_and_idempotency(
    sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _service_scope(connection, prefix)
    first, second, third = scope.waiter_ids
    common = {
        'tenant_id': scope.tenant_id,
        'service_session_id': scope.service_session_id,
        'actor_membership_id': scope.actor_membership_id,
    }
    _call(
        integration_settings, responsibility.initialize_service_responsibility,
        **common, responsible_membership_ids=[first, second],
        idempotency_key='initialize-shared',
    )
    updated = _call(
        integration_settings, responsibility.replace_service_responsibility,
        **common, responsible_membership_ids=[second, third], expected_version=1,
        idempotency_key='replace-shared', correlation_id='corr-update',
    )
    assert updated.service_session_id == scope.service_session_id
    assert updated.version == 2
    assert updated.responsible_membership_ids == (second, third)
    replay = _call(
        integration_settings, responsibility.replace_service_responsibility,
        **common, responsible_membership_ids=[second, third], expected_version=1,
        idempotency_key='replace-shared', correlation_id='different-retry-correlation',
    )
    assert replay.version == 2
    assert replay.responsible_membership_ids == (second, third)
    assert replay.replayed is True
    with pytest.raises(responsibility.ServiceResponsibilityIdempotencyConflictError):
        _call(
            integration_settings, responsibility.replace_service_responsibility,
            **common, responsible_membership_ids=[third], expected_version=2,
            idempotency_key='replace-shared',
        )
    final = _call(
        integration_settings, responsibility.replace_service_responsibility,
        **common, responsible_membership_ids=[third], expected_version=2,
        idempotency_key='replace-one',
    )
    assert final.version == 3
    assert final.responsible_membership_ids == (third,)
    with pytest.raises(responsibility.ServiceResponsibilityVersionConflictError):
        _call(
            integration_settings, responsibility.replace_service_responsibility,
            **common, responsible_membership_ids=[first], expected_version=2,
            idempotency_key='stale-replace',
        )
    with pytest.raises(responsibility.ServiceResponsibilityValidationError):
        _call(
            integration_settings, responsibility.replace_service_responsibility,
            **common, responsible_membership_ids=[], expected_version=3,
            idempotency_key='empty-replace',
        )
    history = _call(
        integration_settings, responsibility.get_service_responsibility_history,
        tenant_id=scope.tenant_id, service_session_id=scope.service_session_id,
    )
    assert [event.result_version for event in history] == [1, 2, 3]
    assert [event.operation for event in history] == [
        'INITIALIZE', 'RESPONSIBILITY_UPDATE', 'RESPONSIBILITY_UPDATE',
    ]
    assert history[1].before_responsible_membership_ids == (first, second)
    assert history[1].after_responsible_membership_ids == (second, third)
    assert history[2].before_responsible_membership_ids == (second, third)
    assert history[2].after_responsible_membership_ids == (third,)
    assert {event.service_session_id for event in history} == {scope.service_session_id}


def test_waiter_must_be_eligible_same_scope_and_table_assigned(
    sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _service_scope(connection, prefix, waiter_count=1)
    ineligible = _waiter(
        connection, tenant_id=scope.tenant_id, location_id=scope.location_id,
        prefix=prefix, label='ineligible', capabilities=('restaurant_service.manage',),
    )
    _execute(
        connection,
        'INSERT INTO table_waiter_assignments '
        '(tenant_id,location_id,table_resource_id,waiter_membership_id,is_responsible) '
        'VALUES (%s,%s,%s,%s,0)',
        (scope.tenant_id, scope.location_id, scope.resource_id, ineligible),
    )
    unassigned = _waiter(
        connection, tenant_id=scope.tenant_id, location_id=scope.location_id,
        prefix=prefix, label='unassigned',
    )
    other_location = _location(
        connection, scope.tenant_id, scope.organization_id, 'OTHER-LOC',
    )
    wrong_location = _waiter(
        connection, tenant_id=scope.tenant_id, location_id=other_location,
        prefix=prefix, label='wrong-location',
    )
    foreign_actor, foreign_location, _, _ = _setup(connection, f'{prefix}-foreign')
    wrong_tenant = _waiter(
        connection, tenant_id=foreign_actor.tenant_id, location_id=foreign_location,
        prefix=prefix, label='wrong-tenant',
    )
    for label, waiter_id in (
        ('ineligible', ineligible),
        ('unassigned', unassigned),
        ('wrong-location', wrong_location),
        ('wrong-tenant', wrong_tenant),
    ):
        with pytest.raises(responsibility.ServiceResponsibilityValidationError):
            _call(
                integration_settings, responsibility.initialize_service_responsibility,
                tenant_id=scope.tenant_id,
                service_session_id=scope.service_session_id,
                responsible_membership_ids=[waiter_id],
                actor_membership_id=scope.actor_membership_id,
                idempotency_key=f'invalid-{label}',
            )


def test_closed_service_rejects_update_but_preserves_reads(
    sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _service_scope(connection, prefix, waiter_count=2)
    common = {
        'tenant_id': scope.tenant_id,
        'service_session_id': scope.service_session_id,
        'actor_membership_id': scope.actor_membership_id,
    }
    _call(
        integration_settings, responsibility.initialize_service_responsibility,
        **common, responsible_membership_ids=[scope.waiter_ids[0]],
        idempotency_key='initialize-before-close',
    )
    updated = _call(
        integration_settings, responsibility.replace_service_responsibility,
        **common, responsible_membership_ids=[scope.waiter_ids[1]],
        expected_version=1, idempotency_key='replace-before-close',
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE restaurant_service_sessions SET status='CLOSED',open_slot=NULL,"
            'access_code_digest=NULL,closed_by_membership_id=%s,closed_at=%s WHERE id=%s',
            (
                scope.actor_membership_id,
                datetime.now(UTC).replace(tzinfo=None),
                scope.service_session_id,
            ),
        )
    with pytest.raises(responsibility.ServiceResponsibilityConflictError):
        _call(
            integration_settings, responsibility.replace_service_responsibility,
            **common, responsible_membership_ids=[scope.waiter_ids[0]],
            expected_version=2, idempotency_key='replace-after-close',
        )
    replay = _call(
        integration_settings, responsibility.replace_service_responsibility,
        **common, responsible_membership_ids=[scope.waiter_ids[1]],
        expected_version=1, idempotency_key='replace-before-close',
    )
    assert replay.replayed is True
    assert replay.version == 2
    assert _call(
        integration_settings, responsibility.get_current_service_responsibility,
        tenant_id=scope.tenant_id, service_session_id=scope.service_session_id,
    ) == updated
    assert len(_call(
        integration_settings, responsibility.get_service_responsibility_history,
        tenant_id=scope.tenant_id, service_session_id=scope.service_session_id,
    )) == 2


def test_concurrent_replacements_from_same_version_have_one_winner(
    sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _service_scope(connection, prefix)
    first, second, third = scope.waiter_ids
    _call(
        integration_settings, responsibility.initialize_service_responsibility,
        tenant_id=scope.tenant_id, service_session_id=scope.service_session_id,
        responsible_membership_ids=[first, second],
        actor_membership_id=scope.actor_membership_id,
        idempotency_key='initialize-concurrent',
    )

    async def exercise():
        manager = DatabaseManager(integration_settings)

        async def replace(waiters, key):
            async with manager.session_factory() as db:
                try:
                    await responsibility.replace_service_responsibility(
                        db, tenant_id=scope.tenant_id,
                        service_session_id=scope.service_session_id,
                        responsible_membership_ids=waiters, expected_version=1,
                        actor_membership_id=scope.actor_membership_id,
                        idempotency_key=key,
                    )
                    return 'success'
                except responsibility.ServiceResponsibilityVersionConflictError:
                    return 'conflict'

        try:
            return await asyncio.gather(
                replace([second, third], 'concurrent-a'),
                replace([first, third], 'concurrent-b'),
            )
        finally:
            await manager.dispose()

    assert sorted(asyncio.run(exercise())) == ['conflict', 'success']
    current = _call(
        integration_settings, responsibility.get_current_service_responsibility,
        tenant_id=scope.tenant_id, service_session_id=scope.service_session_id,
    )
    assert current.version == 2
    assert current.responsible_membership_ids in ((second, third), (first, third))
