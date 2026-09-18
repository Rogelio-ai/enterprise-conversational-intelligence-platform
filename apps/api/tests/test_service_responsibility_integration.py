from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.db.session import DatabaseManager
from app.main import create_app
from app.restaurant import table_waiter_assignments
from app.restaurant.service_sessions import responsibility, service as session_service
from test_canonical_order_commercial_acceptance import (
    _confirm as _commercial_confirm,
    _open_and_join as _commercial_open_and_join,
    _preview as _commercial_preview,
    _product as _commercial_product,
    _scope as _commercial_scope,
    _staff_headers as _commercial_staff_headers,
)
from test_restaurant_payment_settlement_foundation import (
    _check as _payment_check,
    _grant as _grant_payment_permissions,
)
from test_resource_foundation import (
    PASSWORD,
    Authority,
    _execute,
    _grant_location,
    _location,
    _login,
    _organization,
    _resource,
    _seed_authority,
)
from test_table_waiter_assignments import (
    _assign,
    _membership_id,
    _responsible,
    _unassign,
    _waiter,
)


@dataclass(frozen=True)
class IntegrationScope:
    actor: Authority
    actor_membership_id: int
    organization_id: int
    location_id: int
    table_id: int
    waiter_ids: tuple[int, ...]


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _scope(connection, prefix: str, *, waiter_count: int = 3) -> IntegrationScope:
    actor = _seed_authority(
        connection,
        prefix,
        ('resource.read', 'resource.manage', 'restaurant_service.read',
         'restaurant_service.manage'),
    )
    organization_id = _organization(connection, actor.tenant_id, 'ORG')
    location_id = _location(connection, actor.tenant_id, organization_id, 'LOC')
    _grant_location(connection, actor, location_id)
    table_id = _resource(connection, actor.tenant_id, location_id, 'TABLE', 'TABLE')
    waiters = tuple(_waiter(
        connection,
        tenant_id=actor.tenant_id,
        location_id=location_id,
        prefix=prefix,
        label=f'mp2-{index}',
    ) for index in range(1, waiter_count + 1))
    return IntegrationScope(
        actor=actor,
        actor_membership_id=_membership_id(connection, actor),
        organization_id=organization_id,
        location_id=location_id,
        table_id=table_id,
        waiter_ids=waiters,
    )


def _open(client: TestClient, scope: IntegrationScope):
    return client.post(
        f'/resources/{scope.table_id}/service-sessions',
        headers=_login(client, scope.actor),
        json={'party_size': 2},
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


@pytest.mark.parametrize('responsible_count', [1, 2])
def test_open_initializes_exact_table_responsible_set_and_source_version(
    client, sql_connection, integration_settings, responsible_count,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _login(client, scope.actor)
    for version, waiter_id in enumerate(scope.waiter_ids):
        assert _assign(
            client, headers, scope.location_id, scope.table_id, waiter_id, version,
        ).status_code == 201
    expected = scope.waiter_ids[:responsible_count]
    source_version = 3
    if responsible_count == 2:
        changed = _responsible(
            client, headers, scope.location_id, scope.table_id, list(expected), 3,
        )
        assert changed.status_code == 200
        source_version = 4

    opened = _open(client, scope)
    assert opened.status_code == 201, opened.text
    service_session_id = opened.json()['id']
    current = _call(
        integration_settings, responsibility.get_current_service_responsibility,
        tenant_id=scope.actor.tenant_id,
        service_session_id=service_session_id,
    )
    history = _call(
        integration_settings, responsibility.get_service_responsibility_history,
        tenant_id=scope.actor.tenant_id,
        service_session_id=service_session_id,
    )
    assert current.responsible_membership_ids == expected
    assert scope.waiter_ids[-1] not in current.responsible_membership_ids
    assert current.version == 1
    assert len(history) == 1
    assert history[0].operation == 'INITIALIZE'
    assert history[0].before_responsible_membership_ids == ()
    assert history[0].after_responsible_membership_ids == expected
    assert history[0].source_table_assignment_version == source_version
    assert history[0].actor_membership_id == scope.actor_membership_id
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT opened_by_membership_id FROM restaurant_service_sessions WHERE id=%s',
            (service_session_id,),
        )
        assert cursor.fetchone()['opened_by_membership_id'] == scope.actor_membership_id
    assert scope.actor_membership_id not in expected


@pytest.mark.parametrize('staffing', ['missing', 'empty-responsible', 'ineligible'])
def test_invalid_staffing_rejects_open_atomically(
    client, sql_connection, staffing,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=0)
    if staffing != 'missing':
        capabilities = (
            ('restaurant_service.manage',)
            if staffing == 'ineligible'
            else ('order_draft.manage', 'restaurant_service.manage')
        )
        waiter_id = _waiter(
            connection,
            tenant_id=scope.actor.tenant_id,
            location_id=scope.location_id,
            prefix=prefix,
            label=staffing,
            capabilities=capabilities,
        )
        _execute(
            connection,
            'INSERT INTO table_waiter_assignments '
            '(tenant_id,location_id,table_resource_id,waiter_membership_id,is_responsible) '
            'VALUES (%s,%s,%s,%s,%s)',
            (
                scope.actor.tenant_id,
                scope.location_id,
                scope.table_id,
                waiter_id,
                staffing == 'ineligible',
            ),
        )

    response = _open(client, scope)
    assert response.status_code == 409
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_service_sessions '
            'WHERE resource_id=%s',
            (scope.table_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM service_responsible_waiters '
            'WHERE resource_id=%s',
            (scope.table_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM service_responsibility_transitions '
            'WHERE resource_id=%s',
            (scope.table_id,),
        )
        assert cursor.fetchone()['count'] == 0


def test_table_mutations_are_independent_but_open_service_blocks_unassignment(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=4)
    first, second, third, fourth = scope.waiter_ids
    headers = _login(client, scope.actor)
    for version, waiter_id in enumerate((first, second, third)):
        assert _assign(
            client, headers, scope.location_id, scope.table_id, waiter_id, version,
        ).status_code == 201
    assert _responsible(
        client, headers, scope.location_id, scope.table_id, [first, second], 3,
    ).status_code == 200
    opened = _open(client, scope)
    assert opened.status_code == 201
    service_session_id = opened.json()['id']

    assert _responsible(
        client, headers, scope.location_id, scope.table_id, [second, third], 4,
    ).status_code == 200
    assert _assign(
        client, headers, scope.location_id, scope.table_id, fourth, 5,
    ).status_code == 201
    blocked = _unassign(
        client, headers, scope.location_id, scope.table_id, first, 6,
    )
    assert blocked.status_code == 409
    allowed = _unassign(
        client, headers, scope.location_id, scope.table_id, third, 6,
    )
    assert allowed.status_code == 200
    current = _call(
        integration_settings, responsibility.get_current_service_responsibility,
        tenant_id=scope.actor.tenant_id,
        service_session_id=service_session_id,
    )
    assert current.responsible_membership_ids == (first, second)

    closed = client.post(
        f'/restaurant-service-sessions/{service_session_id}/close', headers=headers,
    )
    assert closed.status_code == 200
    after_close = _unassign(
        client, headers, scope.location_id, scope.table_id, first, 7,
    )
    assert after_close.status_code == 200
    history = _call(
        integration_settings, responsibility.get_service_responsibility_history,
        tenant_id=scope.actor.tenant_id,
        service_session_id=service_session_id,
    )
    assert history[0].after_responsible_membership_ids == (first, second)


def test_legacy_open_service_is_not_backfilled_and_preserves_continuity(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=2)
    first, second = scope.waiter_ids
    headers = _login(client, scope.actor)
    assert _assign(
        client, headers, scope.location_id, scope.table_id, first, 0,
    ).status_code == 201
    assert _assign(
        client, headers, scope.location_id, scope.table_id, second, 1,
    ).status_code == 201
    service_session_id = _execute(
        connection,
        'INSERT INTO restaurant_service_sessions '
        '(tenant_id,organization_id,location_id,resource_id,party_size,status,open_slot,'
        'join_context_key,access_code_digest,access_code_version,failed_join_attempts,'
        'opened_by_membership_id,opened_at) '
        "VALUES (%s,%s,%s,%s,2,'OPEN',1,%s,%s,1,0,%s,%s)",
        (
            scope.actor.tenant_id,
            scope.organization_id,
            scope.location_id,
            scope.table_id,
            uuid4().hex,
            'b' * 64,
            scope.actor_membership_id,
            datetime.now(UTC).replace(tzinfo=None),
        ),
    )
    current = client.get(
        f'/resources/{scope.table_id}/service-sessions/current', headers=headers,
    )
    assert current.status_code == 200
    with pytest.raises(responsibility.ServiceResponsibilityNotInitializedError) as exc:
        _call(
            integration_settings, responsibility.get_current_service_responsibility,
            tenant_id=scope.actor.tenant_id,
            service_session_id=service_session_id,
        )
    assert exc.value.code == 'SERVICE_RESPONSIBILITY_NOT_INITIALIZED'
    assert _call(
        integration_settings, responsibility.get_service_responsibility_history,
        tenant_id=scope.actor.tenant_id,
        service_session_id=service_session_id,
    ) == ()
    assert _unassign(
        client, headers, scope.location_id, scope.table_id, first, 2,
    ).status_code == 200
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM service_responsibility_transitions '
            'WHERE service_session_id=%s',
            (service_session_id,),
        )
        assert cursor.fetchone()['count'] == 0
    closed = client.post(
        f'/restaurant-service-sessions/{service_session_id}/close', headers=headers,
    )
    assert closed.status_code == 200


def test_legacy_uninitialized_service_preserves_order_check_and_payment(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _commercial_scope(connection, prefix)
    _grant_payment_permissions(connection, scope.tenant_id)
    opened, diner_headers = _commercial_open_and_join(client, scope)
    service_session_id = opened['id']
    with connection.cursor() as cursor:
        cursor.execute(
            'DELETE FROM service_responsible_waiters WHERE service_session_id=%s',
            (service_session_id,),
        )
        cursor.execute(
            'DELETE FROM service_responsibility_transitions WHERE service_session_id=%s',
            (service_session_id,),
        )

    product_id = _commercial_product(connection, scope, amount='100')
    preview = _commercial_preview(client, diner_headers, product_id)
    order = _commercial_confirm(client, diner_headers, preview, 'legacy-order')
    assert order.status_code == 201, order.text
    check = _payment_check(client, diner_headers, key='legacy-check')
    diner_id = client.get('/diner-session', headers=diner_headers).json()['id']
    payment = client.post(
        f"/restaurant-checks/{check['id']}/payments",
        headers={
            **_commercial_staff_headers(client, scope),
            'Idempotency-Key': 'legacy-cash-payment',
        },
        params={'location_id': scope.location_id},
        json={
            'expected_check_version': check['version'],
            'expected_check_fingerprint': check['fingerprint'],
            'amount': '100',
            'currency': 'MXN',
            'method_category': 'CASH',
            'payer_type': 'DINER',
            'payer_diner_session_id': diner_id,
            'cash_tendered_amount': '100',
        },
    )
    assert payment.status_code == 201, payment.text
    settlement = client.get(
        f"/diner/restaurant-checks/{check['id']}/settlement",
        headers=diner_headers,
    )
    assert settlement.status_code == 200, settlement.text
    assert settlement.json()['check_status'] == 'SETTLED'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM service_responsible_waiters '
            'WHERE service_session_id=%s',
            (service_session_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM service_responsibility_transitions '
            'WHERE service_session_id=%s',
            (service_session_id,),
        )
        assert cursor.fetchone()['count'] == 0


def test_concurrent_open_and_table_responsibility_change_use_one_snapshot(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=2)
    first, second = scope.waiter_ids
    headers = _login(client, scope.actor)
    assert _assign(
        client, headers, scope.location_id, scope.table_id, first, 0,
    ).status_code == 201
    assert _assign(
        client, headers, scope.location_id, scope.table_id, second, 1,
    ).status_code == 201

    with ThreadPoolExecutor(max_workers=2) as executor:
        opening = executor.submit(_open, client, scope)
        changing = executor.submit(
            _responsible,
            client,
            headers,
            scope.location_id,
            scope.table_id,
            [second],
            2,
        )
        opened = opening.result()
        changed = changing.result()
    assert opened.status_code == 201
    assert changed.status_code == 200
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT source_table_assignment_version,after_responsible_membership_ids '
            'FROM service_responsibility_transitions '
            'WHERE service_session_id=%s AND result_version=1',
            (opened.json()['id'],),
        )
        transition = cursor.fetchone()
        cursor.execute(
            'SELECT responsible_membership_ids FROM table_waiter_assignment_audits '
            'WHERE table_resource_id=%s AND result_version=%s',
            (scope.table_id, transition['source_table_assignment_version']),
        )
        source = cursor.fetchone()
    assert source is not None
    assert json.loads(transition['after_responsible_membership_ids']) == json.loads(
        source['responsible_membership_ids'],
    )


def test_concurrent_transition_and_close_preserve_lifecycle(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=2)
    first, second = scope.waiter_ids
    headers = _login(client, scope.actor)
    assert _assign(
        client, headers, scope.location_id, scope.table_id, first, 0,
    ).status_code == 201
    assert _assign(
        client, headers, scope.location_id, scope.table_id, second, 1,
    ).status_code == 201
    opened = _open(client, scope).json()

    async def exercise():
        manager = DatabaseManager(integration_settings)

        async def transition():
            async with manager.session_factory() as db:
                try:
                    await responsibility.replace_service_responsibility(
                        db,
                        tenant_id=scope.actor.tenant_id,
                        service_session_id=opened['id'],
                        responsible_membership_ids=[second],
                        expected_version=1,
                        actor_membership_id=scope.actor_membership_id,
                        idempotency_key='mp2-close-race',
                    )
                    return 'transition-success'
                except responsibility.ServiceResponsibilityConflictError:
                    return 'transition-conflict'

        async def close():
            async with manager.session_factory() as db:
                await session_service.close_service_session(
                    db,
                    tenant_id=scope.actor.tenant_id,
                    membership_id=scope.actor_membership_id,
                    session_id=opened['id'],
                )
                return 'close-success'

        try:
            return await asyncio.gather(transition(), close())
        finally:
            await manager.dispose()

    outcomes = asyncio.run(exercise())
    assert 'close-success' in outcomes
    assert outcomes[0] in ('transition-success', 'transition-conflict')
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT status FROM restaurant_service_sessions WHERE id=%s',
            (opened['id'],),
        )
        assert cursor.fetchone()['status'] == 'CLOSED'
        cursor.execute(
            'SELECT result_version FROM service_responsibility_transitions '
            'WHERE service_session_id=%s ORDER BY result_version',
            (opened['id'],),
        )
        versions = [row['result_version'] for row in cursor.fetchall()]
    assert versions in ([1], [1, 2])


def test_concurrent_unassign_and_transition_never_orphan_responsibility(
    client, sql_connection, integration_settings,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    first, second, third = scope.waiter_ids
    headers = _login(client, scope.actor)
    for version, waiter_id in enumerate(scope.waiter_ids):
        assert _assign(
            client, headers, scope.location_id, scope.table_id, waiter_id, version,
        ).status_code == 201
    assert _responsible(
        client, headers, scope.location_id, scope.table_id, [first, second], 3,
    ).status_code == 200
    service_session_id = _open(client, scope).json()['id']

    async def exercise():
        manager = DatabaseManager(integration_settings)

        async def unassign():
            async with manager.session_factory() as db:
                try:
                    await table_waiter_assignments.unassign_waiter(
                        db,
                        tenant_id=scope.actor.tenant_id,
                        location_id=scope.location_id,
                        table_resource_id=scope.table_id,
                        waiter_membership_id=third,
                        replacement_responsible_membership_ids=set(),
                        expected_version=4,
                        actor_membership_id=scope.actor_membership_id,
                        correlation_id=None,
                    )
                    return 'unassign-success'
                except table_waiter_assignments.AssignmentConflictError:
                    return 'unassign-conflict'

        async def transition():
            async with manager.session_factory() as db:
                try:
                    await responsibility.replace_service_responsibility(
                        db,
                        tenant_id=scope.actor.tenant_id,
                        service_session_id=service_session_id,
                        responsible_membership_ids=[second, third],
                        expected_version=1,
                        actor_membership_id=scope.actor_membership_id,
                        idempotency_key='mp2-unassign-race',
                    )
                    return 'transition-success'
                except responsibility.ServiceResponsibilityError:
                    return 'transition-conflict'

        try:
            return await asyncio.gather(unassign(), transition())
        finally:
            await manager.dispose()

    outcomes = asyncio.run(exercise())
    assert sorted(outcomes) in (
        ['transition-conflict', 'unassign-success'],
        ['transition-success', 'unassign-conflict'],
    )
    current = _call(
        integration_settings, responsibility.get_current_service_responsibility,
        tenant_id=scope.actor.tenant_id,
        service_session_id=service_session_id,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT waiter_membership_id FROM table_waiter_assignments '
            'WHERE table_resource_id=%s',
            (scope.table_id,),
        )
        assigned = {row['waiter_membership_id'] for row in cursor.fetchall()}
    assert set(current.responsible_membership_ids) <= assigned
