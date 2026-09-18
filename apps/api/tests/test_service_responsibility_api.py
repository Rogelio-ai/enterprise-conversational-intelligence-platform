from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from test_resource_foundation import _execute, _grant_location, _location, _login
from test_service_responsibility_integration import _scope
from test_table_waiter_assignments import _assign, _responsible, _unassign, _waiter


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _url(location_id: int, session_id: int, suffix: str = '') -> str:
    return (
        f'/locations/{location_id}/restaurant-service-sessions/'
        f'{session_id}/responsibility{suffix}'
    )


def _open(client: TestClient, scope, headers: dict[str, str]) -> int:
    response = client.post(
        f'/resources/{scope.table_id}/service-sessions',
        headers=headers,
        json={'party_size': 2},
    )
    assert response.status_code == 201, response.text
    return int(response.json()['id'])


def _put(
    client: TestClient, scope, headers: dict[str, str], session_id: int,
    membership_ids: list[int], version: int, key: str,
):
    return client.put(
        _url(scope.location_id, session_id),
        headers={**headers, 'Idempotency-Key': key},
        json={
            'responsible_membership_ids': membership_ids,
            'expected_version': version,
        },
    )


def test_current_transition_and_history_expose_complete_ordered_state(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=3)
    headers = _login(client, scope.actor)
    first, second, third = scope.waiter_ids
    for version, waiter_id in enumerate(scope.waiter_ids):
        assert _assign(
            client, headers, scope.location_id, scope.table_id, waiter_id, version,
        ).status_code == 201
    session_id = _open(client, scope, headers)

    current = client.get(_url(scope.location_id, session_id), headers=headers)
    assert current.status_code == 200
    assert current.json() == {
        'service_session_id': session_id,
        'status': 'OPEN',
        'initialized': True,
        'version': 1,
        'responsible_membership_ids': [first],
        'responsible_waiters': [{
            'membership_id': first,
            'display_name': current.json()['responsible_waiters'][0]['display_name'],
            'email': current.json()['responsible_waiters'][0]['email'],
        }],
        'replayed': False,
    }

    shared = _put(
        client, scope, headers, session_id, [first, second], 1, 'api-shared',
    )
    assert shared.status_code == 200, shared.text
    assert shared.json()['version'] == 2
    assert shared.json()['responsible_membership_ids'] == [first, second]
    shared_read = client.get(_url(scope.location_id, session_id), headers=headers)
    assert shared_read.status_code == 200
    assert shared_read.json()['responsible_membership_ids'] == [first, second]
    assert len(shared_read.json()['responsible_waiters']) == 2
    replay = _put(
        client, scope, headers, session_id, [first, second], 1, 'api-shared',
    )
    assert replay.status_code == 200
    assert replay.json()['replayed'] is True
    changed = _put(
        client, scope, headers, session_id, [second, third], 2, 'api-changed',
    )
    assert changed.status_code == 200
    assert changed.json()['responsible_membership_ids'] == [second, third]
    assert changed.json()['version'] == 3

    history = client.get(
        _url(scope.location_id, session_id, '/history'), headers=headers,
    )
    assert history.status_code == 200
    assert [item['operation'] for item in history.json()['items']] == [
        'INITIALIZE', 'RESPONSIBILITY_UPDATE', 'RESPONSIBILITY_UPDATE',
    ]
    assert [item['version'] for item in history.json()['items']] == [1, 2, 3]
    assert history.json()['items'][1]['before_responsible_membership_ids'] == [first]
    assert history.json()['items'][2]['after_responsible_membership_ids'] == [second, third]
    assert all(item['actor_membership_id'] == scope.actor_membership_id
               for item in history.json()['items'])


def test_transition_maps_validation_version_and_idempotency_conflicts(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=3)
    headers = _login(client, scope.actor)
    first, second, unassigned = scope.waiter_ids
    assert _assign(
        client, headers, scope.location_id, scope.table_id, first, 0,
    ).status_code == 201
    assert _assign(
        client, headers, scope.location_id, scope.table_id, second, 1,
    ).status_code == 201
    ineligible = _waiter(
        connection, tenant_id=scope.actor.tenant_id, location_id=scope.location_id,
        prefix=prefix, label='api-ineligible',
        capabilities=('restaurant_service.manage',),
    )
    _execute(
        connection,
        'INSERT INTO table_waiter_assignments '
        '(tenant_id,location_id,table_resource_id,waiter_membership_id,is_responsible) '
        'VALUES (%s,%s,%s,%s,0)',
        (scope.actor.tenant_id, scope.location_id, scope.table_id, ineligible),
    )
    session_id = _open(client, scope, headers)

    for ids, version, key in (
        ([], 1, 'empty'),
        ([unassigned], 1, 'unassigned'),
        ([ineligible], 1, 'ineligible'),
        ([second], 99, 'stale'),
    ):
        response = _put(client, scope, headers, session_id, ids, version, key)
        assert response.status_code == 409

    accepted = _put(client, scope, headers, session_id, [second], 1, 'same-key')
    assert accepted.status_code == 200
    conflict = _put(client, scope, headers, session_id, [first], 2, 'same-key')
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == (
        'SERVICE_RESPONSIBILITY_IDEMPOTENCY_CONFLICT'
    )


def test_location_scope_is_enforced_for_reads_and_mutations(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=1)
    headers = _login(client, scope.actor)
    assert _assign(
        client, headers, scope.location_id, scope.table_id, scope.waiter_ids[0], 0,
    ).status_code == 201
    session_id = _open(client, scope, headers)
    assert client.get(_url(scope.location_id, session_id), headers=headers).status_code == 200

    ungranted = _location(
        connection, scope.actor.tenant_id, scope.organization_id, 'NO-GRANT',
    )
    assert client.get(_url(ungranted, session_id), headers=headers).status_code == 404
    granted_wrong = _location(
        connection, scope.actor.tenant_id, scope.organization_id, 'WRONG-LOC',
    )
    _grant_location(connection, scope.actor, granted_wrong)
    assert client.get(_url(granted_wrong, session_id), headers=headers).status_code == 404
    assert _put(
        client, scope, headers, session_id, [scope.waiter_ids[0]], 1,
        'missing-header-scope-check',
    ).status_code == 200

    foreign = _scope(connection, f'{prefix}-foreign', waiter_count=1)
    foreign_headers = _login(client, foreign.actor)
    assert _assign(
        client, foreign_headers, foreign.location_id, foreign.table_id,
        foreign.waiter_ids[0], 0,
    ).status_code == 201
    foreign_session_id = _open(client, foreign, foreign_headers)
    assert client.get(
        _url(foreign.location_id, foreign_session_id), headers=headers,
    ).status_code == 404


def test_service_responsibility_api_requires_read_and_manage_capabilities(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=1)
    headers = _login(client, scope.actor)
    waiter = scope.waiter_ids[0]
    assert _assign(
        client, headers, scope.location_id, scope.table_id, waiter, 0,
    ).status_code == 201
    session_id = _open(client, scope, headers)

    def revoke(code: str) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT rp.role_id,rp.permission_id FROM role_permissions rp '
                'JOIN permissions p ON p.id=rp.permission_id '
                'JOIN membership_roles mr ON mr.role_id=rp.role_id '
                'WHERE mr.membership_id=%s AND p.code=%s',
                (scope.actor_membership_id, code),
            )
            for row in cursor.fetchall():
                cursor.execute(
                    'DELETE FROM role_permissions WHERE role_id=%s AND permission_id=%s',
                    (row['role_id'], row['permission_id']),
                )

    revoke('restaurant_service.manage')
    assert _put(
        client, scope, headers, session_id, [waiter], 1, 'forbidden-manage',
    ).status_code == 403
    assert client.get(_url(scope.location_id, session_id), headers=headers).status_code == 200

    revoke('restaurant_service.read')
    assert client.get(_url(scope.location_id, session_id), headers=headers).status_code == 403
    assert client.get(
        _url(scope.location_id, session_id, '/history'), headers=headers,
    ).status_code == 403


def test_closed_service_is_readable_but_cannot_transition(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=1)
    headers = _login(client, scope.actor)
    waiter = scope.waiter_ids[0]
    assert _assign(
        client, headers, scope.location_id, scope.table_id, waiter, 0,
    ).status_code == 201
    session_id = _open(client, scope, headers)
    closed = client.post(
        f'/restaurant-service-sessions/{session_id}/close', headers=headers,
    )
    assert closed.status_code == 200, closed.text
    current = client.get(_url(scope.location_id, session_id), headers=headers)
    assert current.status_code == 200
    assert current.json()['status'] == 'CLOSED'
    assert current.json()['responsible_membership_ids'] == [waiter]
    blocked = _put(
        client, scope, headers, session_id, [waiter], 1, 'closed-change',
    )
    assert blocked.status_code == 409


def test_legacy_service_is_explicitly_uninitialized_without_synthetic_history(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=1)
    headers = _login(client, scope.actor)
    waiter = scope.waiter_ids[0]
    assert _assign(
        client, headers, scope.location_id, scope.table_id, waiter, 0,
    ).status_code == 201
    session_id = _execute(
        connection,
        'INSERT INTO restaurant_service_sessions '
        '(tenant_id,organization_id,location_id,resource_id,party_size,status,open_slot,'
        'join_context_key,access_code_digest,access_code_version,failed_join_attempts,'
        'opened_by_membership_id,opened_at) '
        "VALUES (%s,%s,%s,%s,2,'OPEN',1,%s,%s,1,0,%s,%s)",
        (
            scope.actor.tenant_id, scope.organization_id, scope.location_id,
            scope.table_id, uuid4().hex, 'c' * 64, scope.actor_membership_id,
            datetime.now(UTC).replace(tzinfo=None),
        ),
    )

    current = client.get(_url(scope.location_id, session_id), headers=headers)
    assert current.status_code == 200
    assert current.json()['initialized'] is False
    assert current.json()['version'] is None
    assert current.json()['responsible_membership_ids'] == []
    assert current.json()['responsible_waiters'] == []
    history = client.get(
        _url(scope.location_id, session_id, '/history'), headers=headers,
    )
    assert history.status_code == 200
    assert history.json()['items'] == []
    transition = _put(
        client, scope, headers, session_id, [waiter], 1, 'legacy-change',
    )
    assert transition.status_code == 409
    assert transition.json()['error']['code'] == (
        'SERVICE_RESPONSIBILITY_NOT_INITIALIZED'
    )


def test_mp4_canonical_integrated_responsibility_scenario(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, waiter_count=3)
    headers = _login(client, scope.actor)
    juan, maria, pedro = scope.waiter_ids
    for version, waiter_id in enumerate(scope.waiter_ids):
        assert _assign(
            client, headers, scope.location_id, scope.table_id, waiter_id, version,
        ).status_code == 201
    seeded = _responsible(
        client, headers, scope.location_id, scope.table_id, [juan, maria], 3,
    )
    assert seeded.status_code == 200
    assert {
        item['membership_id'] for item in seeded.json()['assignments']
        if item['is_responsible']
    } == {juan, maria}

    session_id = _open(client, scope, headers)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT resource_id,opened_by_membership_id,status FROM '
            'restaurant_service_sessions WHERE id=%s', (session_id,),
        )
        opened = cursor.fetchone()
    assert opened == {
        'resource_id': scope.table_id,
        'opened_by_membership_id': scope.actor_membership_id,
        'status': 'OPEN',
    }
    current = client.get(_url(scope.location_id, session_id), headers=headers)
    assert current.status_code == 200
    assert current.json()['initialized'] is True
    assert current.json()['version'] == 1
    assert current.json()['responsible_membership_ids'] == [juan, maria]

    v2 = _put(
        client, scope, headers, session_id, [maria, pedro], 1,
        'mp4-canonical-v2',
    )
    assert v2.status_code == 200
    assert v2.json()['service_session_id'] == session_id
    assert v2.json()['version'] == 2
    assert v2.json()['responsible_membership_ids'] == [maria, pedro]
    table_after_v2 = client.get(
        f'/locations/{scope.location_id}/tables/{scope.table_id}/waiter-assignments',
        headers=headers,
    )
    assert table_after_v2.status_code == 200
    assert {item['membership_id'] for item in table_after_v2.json()['assignments']} == {
        juan, maria, pedro,
    }
    assert {
        item['membership_id'] for item in table_after_v2.json()['assignments']
        if item['is_responsible']
    } == {juan, maria}

    blocked = _unassign(
        client, headers, scope.location_id, scope.table_id, pedro, 4,
    )
    assert blocked.status_code == 409
    assert client.get(
        f'/locations/{scope.location_id}/tables/{scope.table_id}/waiter-assignments',
        headers=headers,
    ).json() == table_after_v2.json()
    assert client.get(
        _url(scope.location_id, session_id), headers=headers,
    ).json()['responsible_membership_ids'] == [maria, pedro]

    v3 = _put(
        client, scope, headers, session_id, [maria], 2, 'mp4-canonical-v3',
    )
    assert v3.status_code == 200
    assert v3.json()['version'] == 3
    assert v3.json()['responsible_membership_ids'] == [maria]
    allowed = _unassign(
        client, headers, scope.location_id, scope.table_id, pedro, 4,
    )
    assert allowed.status_code == 200
    assert {item['membership_id'] for item in allowed.json()['assignments']} == {
        juan, maria,
    }
    assert client.get(
        _url(scope.location_id, session_id), headers=headers,
    ).json()['responsible_membership_ids'] == [maria]

    history = client.get(
        _url(scope.location_id, session_id, '/history'), headers=headers,
    )
    assert history.status_code == 200
    assert [
        (
            item['version'], item['operation'],
            item['before_responsible_membership_ids'],
            item['after_responsible_membership_ids'],
        ) for item in history.json()['items']
    ] == [
        (1, 'INITIALIZE', [], [juan, maria]),
        (2, 'RESPONSIBILITY_UPDATE', [juan, maria], [maria, pedro]),
        (3, 'RESPONSIBILITY_UPDATE', [maria, pedro], [maria]),
    ]
    assert all(item['actor_membership_id'] == scope.actor_membership_id
               for item in history.json()['items'])
    assert all(item['recorded_at'] for item in history.json()['items'])
    assert all(item['correlation_id'] for item in history.json()['items'])
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT result_version,idempotency_key FROM '
            'service_responsibility_transitions WHERE service_session_id=%s '
            'ORDER BY result_version', (session_id,),
        )
        evidence = cursor.fetchall()
    assert evidence == [
        {'result_version': 1, 'idempotency_key': f'SERVICE_OPEN:{session_id}'},
        {'result_version': 2, 'idempotency_key': 'mp4-canonical-v2'},
        {'result_version': 3, 'idempotency_key': 'mp4-canonical-v3'},
    ]

    closed = client.post(
        f'/restaurant-service-sessions/{session_id}/close', headers=headers,
    )
    assert closed.status_code == 200
    closed_read = client.get(_url(scope.location_id, session_id), headers=headers)
    assert closed_read.status_code == 200
    assert closed_read.json()['status'] == 'CLOSED'
    assert closed_read.json()['responsible_membership_ids'] == [maria]
    assert _put(
        client, scope, headers, session_id, [juan], 3, 'mp4-after-close',
    ).status_code == 409
    assert _unassign(
        client, headers, scope.location_id, scope.table_id, maria, 5,
    ).status_code == 200
