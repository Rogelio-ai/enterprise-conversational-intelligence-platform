from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from test_resource_foundation import PASSWORD, _assign_permission, _location, _login
from test_service_responsibility_api import _put
from test_service_responsibility_integration import _open, _scope
from test_table_waiter_assignments import _assign


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _grant_operational_permissions(connection, membership_ids: tuple[int, ...]) -> None:
    for membership_id in membership_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT role_id FROM membership_roles WHERE membership_id=%s ORDER BY role_id LIMIT 1',
                (membership_id,),
            )
            role_id = int(cursor.fetchone()['role_id'])
        _assign_permission(connection, role_id, 'operational_request.read')
        _assign_permission(connection, role_id, 'operational_request.manage')


def _waiter_headers(client: TestClient, prefix: str, index: int) -> dict[str, str]:
    response = client.post('/auth/login', json={
        'email': f'{prefix}-mp2-{index}@example.test',
        'password': PASSWORD,
    })
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _prepare(client: TestClient, connection, prefix: str):
    scope = _scope(connection, prefix, waiter_count=3)
    actor_headers = _login(client, scope.actor)
    _grant_operational_permissions(connection, scope.waiter_ids)
    for version, waiter_id in enumerate(scope.waiter_ids):
        assigned = _assign(
            client, actor_headers, scope.location_id, scope.table_id, waiter_id, version,
        )
        assert assigned.status_code == 201, assigned.text
    opened = _open(client, scope)
    assert opened.status_code == 201, opened.text
    joined = client.post('/diner-sessions/join', json={
        'join_context_key': opened.json()['join_context_key'],
        'access_code': opened.json()['access_code'],
        'display_name': 'Routing diner',
    })
    assert joined.status_code == 201, joined.text
    diner_headers = {'Authorization': f"Bearer {joined.json()['access_token']}"}
    waiter_headers = tuple(_waiter_headers(client, prefix, index) for index in (1, 2, 3))
    return scope, actor_headers, int(opened.json()['id']), diner_headers, waiter_headers


def _create_request(client: TestClient, diner_headers: dict[str, str], key: str) -> int:
    response = client.post(
        '/diner/operational-requests',
        headers={**diner_headers, 'Idempotency-Key': key},
        json={'request_type': 'HUMAN_ASSISTANCE'},
    )
    assert response.status_code == 201, response.text
    return int(response.json()['id'])


def _list(client: TestClient, headers: dict[str, str], location_id: int):
    return client.get(
        f'/waiter/operational-requests?location_id={location_id}', headers=headers,
    )


def _action(
    client: TestClient, headers: dict[str, str], location_id: int,
    request_id: int, action: str,
):
    return client.post(
        f'/waiter/operational-requests/{request_id}/{action}?location_id={location_id}',
        headers=headers,
    )


def test_dynamic_single_shared_and_new_request_routing(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope, actor_headers, session_id, diner_headers, waiters = _prepare(
        client, connection, prefix,
    )
    first, second, third = waiters
    request_id = _create_request(client, diner_headers, 'routed-before-transition')

    assert [item['id'] for item in _list(client, first, scope.location_id).json()['items']] == [request_id]
    assert _list(client, second, scope.location_id).json()['items'] == []
    assert client.get(
        f'/waiter/operational-requests/{request_id}?location_id={scope.location_id}',
        headers=second,
    ).status_code == 404

    shared = _put(
        client, scope, actor_headers, session_id,
        list(scope.waiter_ids[:2]), 1, 'routing-shared',
    )
    assert shared.status_code == 200, shared.text
    assert [item['id'] for item in _list(client, first, scope.location_id).json()['items']] == [request_id]
    assert [item['id'] for item in _list(client, second, scope.location_id).json()['items']] == [request_id]

    changed = _put(
        client, scope, actor_headers, session_id,
        list(scope.waiter_ids[1:]), 2, 'routing-changed',
    )
    assert changed.status_code == 200, changed.text
    assert _list(client, first, scope.location_id).json()['items'] == []
    for headers in (second, third):
        item = _list(client, headers, scope.location_id).json()['items'][0]
        assert (item['id'], item['status']) == (request_id, 'PENDING')

    new_request_id = _create_request(client, diner_headers, 'routed-after-transition')
    assert _list(client, first, scope.location_id).json()['items'] == []
    for headers in (second, third):
        assert [item['id'] for item in _list(client, headers, scope.location_id).json()['items']] == [
            request_id, new_request_id,
        ]

    denied = _action(client, first, scope.location_id, request_id, 'acknowledge')
    assert denied.status_code == 404
    with connection.cursor() as cursor:
        cursor.execute('SELECT status FROM diner_operational_requests WHERE id=%s', (request_id,))
        assert cursor.fetchone()['status'] == 'PENDING'

    ungranted_location = _location(
        connection, scope.actor.tenant_id, scope.organization_id, 'UNGRANTED',
    )
    assert _list(client, second, ungranted_location).status_code == 404


def test_shared_waiters_mutate_one_canonical_request(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope, actor_headers, session_id, diner_headers, waiters = _prepare(
        client, connection, prefix,
    )
    first, second, _ = waiters
    shared = _put(
        client, scope, actor_headers, session_id,
        list(scope.waiter_ids[:2]), 1, 'shared-lifecycle',
    )
    assert shared.status_code == 200, shared.text
    request_id = _create_request(client, diner_headers, 'shared-lifecycle-request')

    acknowledged = _action(client, first, scope.location_id, request_id, 'acknowledge')
    assert acknowledged.status_code == 200, acknowledged.text
    detail = client.get(
        f'/waiter/operational-requests/{request_id}?location_id={scope.location_id}',
        headers=second,
    )
    assert detail.status_code == 200
    assert detail.json()['status'] == 'ACKNOWLEDGED'

    with ThreadPoolExecutor(max_workers=2) as pool:
        completions = list(pool.map(
            lambda headers: _action(
                client, headers, scope.location_id, request_id, 'complete',
            ),
            (first, second),
        ))
    assert [response.status_code for response in completions] == [200, 200]
    assert {response.json()['status'] for response in completions} == {'COMPLETED'}
    completing_actor = completions[0].json()['resolved_by_membership_id']
    assert {response.json()['resolved_by_membership_id'] for response in completions} == {
        completing_actor,
    }
    changed = _put(
        client, scope, actor_headers, session_id,
        [scope.waiter_ids[1]], 2, 'after-completion-responsibility-change',
    )
    assert changed.status_code == 200, changed.text
    historical = client.get(
        f'/waiter/operational-requests/{request_id}?location_id={scope.location_id}',
        headers=second,
    )
    assert historical.status_code == 200
    assert historical.json()['status'] == 'COMPLETED'
    assert historical.json()['resolved_by_membership_id'] == completing_actor
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count,status,resolved_by_membership_id '
            'FROM diner_operational_requests WHERE id=%s GROUP BY status,resolved_by_membership_id',
            (request_id,),
        )
        row = cursor.fetchone()
    assert row['count'] == 1
    assert row['status'] == 'COMPLETED'
    assert row['resolved_by_membership_id'] in scope.waiter_ids[:2]


def test_waiter_action_and_responsibility_transition_serialize(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope, actor_headers, session_id, diner_headers, waiters = _prepare(
        client, connection, prefix,
    )
    first, second, _ = waiters
    assert _put(
        client, scope, actor_headers, session_id,
        list(scope.waiter_ids[:2]), 1, 'race-shared',
    ).status_code == 200
    request_id = _create_request(client, diner_headers, 'responsibility-race')
    barrier = Barrier(2)

    def act():
        barrier.wait()
        return _action(client, first, scope.location_id, request_id, 'acknowledge')

    def transition():
        barrier.wait()
        return _put(
            client, scope, actor_headers, session_id,
            [scope.waiter_ids[1]], 2, 'race-remove-first',
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        action_future = pool.submit(act)
        transition_future = pool.submit(transition)
        action_response = action_future.result()
        transition_response = transition_future.result()
    assert transition_response.status_code == 200, transition_response.text
    assert action_response.status_code in {200, 404}
    with connection.cursor() as cursor:
        cursor.execute('SELECT status FROM diner_operational_requests WHERE id=%s', (request_id,))
        persisted_status = cursor.fetchone()['status']
    assert persisted_status == ('ACKNOWLEDGED' if action_response.status_code == 200 else 'PENDING')
    assert _list(client, first, scope.location_id).json()['items'] == []
    assert [item['id'] for item in _list(client, second, scope.location_id).json()['items']] == [request_id]


def test_genuine_legacy_open_service_retains_location_wide_waiter_access(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope, _, session_id, diner_headers, waiters = _prepare(client, connection, prefix)
    request_id = _create_request(client, diner_headers, 'legacy-request')
    with connection.cursor() as cursor:
        cursor.execute(
            'DELETE FROM service_responsible_waiters WHERE service_session_id=%s',
            (session_id,),
        )

    # A service with initialization history never broadens to Location scope,
    # even if its current-set rows are inconsistent or missing.
    for headers in waiters:
        assert _list(client, headers, scope.location_id).json()['items'] == []
        assert _action(
            client, headers, scope.location_id, request_id, 'acknowledge',
        ).status_code == 404
    with connection.cursor() as cursor:
        cursor.execute('SELECT status FROM diner_operational_requests WHERE id=%s', (request_id,))
        assert cursor.fetchone()['status'] == 'PENDING'
        cursor.execute(
            'DELETE FROM service_responsibility_transitions WHERE service_session_id=%s',
            (session_id,),
        )

    for headers in waiters:
        assert [item['id'] for item in _list(client, headers, scope.location_id).json()['items']] == [request_id]
    acknowledged = _action(client, waiters[2], scope.location_id, request_id, 'acknowledge')
    assert acknowledged.status_code == 200, acknowledged.text
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM service_responsible_waiters '
            'WHERE service_session_id=%s',
            (session_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM service_responsibility_transitions '
            'WHERE service_session_id=%s',
            (session_id,),
        )
        assert cursor.fetchone()['count'] == 0
