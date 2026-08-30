from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.core.security import create_diner_access_token, hash_password
from app.main import create_app
from test_pos_order_submission_recovery import (
    PASSWORD,
    _accepted_complex_order,
    _accepted_order,
    _execute,
    _headers,
    _scope,
)
from test_preparation_routing_foundation import _area, _owner, _route


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _native_item(client, connection, scope, *, name='Burger'):
    order_id, product_id, _ = _accepted_order(client, connection, scope, name=name)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, product_id, 'AREA', area['id'])
    routing = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert routing.status_code == 200, routing.text
    work = routing.json()['works'][0]
    return headers, order_id, area, work['id'], work['items'][0]['id']


def _employee(client, connection, scope, *, execute=True, active=True):
    email = f'{uuid4().hex}@example.test'
    user_id = _execute(connection, "INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,'Recorder','ACTIVE')", (email, hash_password(PASSWORD)))
    membership_id = _execute(connection, "INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,%s)", (scope.tenant_id, user_id, 'ACTIVE' if active else 'INACTIVE'))
    role_id = _execute(connection, "INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,'Preparation role','ACTIVE')", (scope.tenant_id, f'PREP_{uuid4().hex}'))
    _execute(connection, 'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)', (scope.tenant_id, membership_id, role_id))
    codes = ['preparation.read'] + (['preparation.execute'] if execute else [])
    for code in codes:
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = cursor.fetchone()['id']
        _execute(connection, 'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)', (role_id, permission_id))
    response = client.post('/auth/login', json={'email': email, 'password': PASSWORD})
    if not active:
        assert response.status_code == 403
        return membership_id, {}
    assert response.status_code == 200, response.text
    return membership_id, {'Authorization': f"Bearer {response.json()['access_token']}"}


def _transition(client, headers, item_id, key, expected_state, expected_version, to_state):
    return client.post(
        f'/preparation-work-items/{item_id}/transitions',
        headers={**headers, 'Idempotency-Key': key},
        json={
            'expected_state': expected_state,
            'expected_version': expected_version,
            'to_state': to_state,
        },
    )


def test_item_lifecycle_history_actor_and_no_observation(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers, _, _, work_id, item_id = _native_item(client, connection, scope)
    initial = client.get(f'/preparation-work-items/{item_id}', headers=headers)
    assert initial.status_code == 200
    assert initial.json()['item']['execution_state'] == 'NEW'
    assert initial.json()['item']['execution_version'] == 0
    assert initial.json()['transitions'] == []

    first_membership = initial_membership = None
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM tenant_memberships WHERE tenant_id=%s ORDER BY id LIMIT 1', (scope.tenant_id,))
        first_membership = initial_membership = cursor.fetchone()['id']
    started = _transition(client, headers, item_id, 'start-key', 'NEW', 0, 'IN_PROGRESS')
    assert started.status_code == 201, started.text
    assert started.json()['transition']['actor_type'] == 'EMPLOYEE'
    assert started.json()['transition']['actor_membership_id'] == first_membership
    assert started.json()['transition']['actor_principal_reference'] is None
    second_membership, second_headers = _employee(client, connection, scope)
    completed = _transition(client, second_headers, item_id, 'complete-key', 'IN_PROGRESS', 1, 'COMPLETED')
    assert completed.status_code == 201, completed.text
    detail = client.get(f'/preparation-work-items/{item_id}', headers=headers).json()
    assert detail['item']['execution_state'] == 'COMPLETED'
    assert detail['item']['execution_version'] == 2
    assert [value['sequence'] for value in detail['transitions']] == [1, 2]
    assert [value['actor_membership_id'] for value in detail['transitions']] == [initial_membership, second_membership]
    work = client.get(f'/preparation-works/{work_id}', headers=headers).json()
    assert work['execution_state'] == 'COMPLETED'


def test_state_machine_rejects_direct_backward_terminal_and_same_state(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers, _, _, _, item_id = _native_item(client, connection, scope)
    assert _transition(client, headers, item_id, 'direct', 'NEW', 0, 'COMPLETED').status_code == 409
    assert _transition(client, headers, item_id, 'same-new', 'NEW', 0, 'NEW').status_code == 409
    assert _transition(client, headers, item_id, 'start', 'NEW', 0, 'IN_PROGRESS').status_code == 201
    assert _transition(client, headers, item_id, 'backward', 'IN_PROGRESS', 1, 'NEW').status_code == 409
    assert _transition(client, headers, item_id, 'complete', 'IN_PROGRESS', 1, 'COMPLETED').status_code == 201
    assert _transition(client, headers, item_id, 'terminal', 'COMPLETED', 2, 'IN_PROGRESS').status_code == 409
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM preparation_item_transitions WHERE preparation_work_item_id=%s', (item_id,))
        assert cursor.fetchone()['count'] == 2


def test_durable_replay_and_idempotency_conflicts(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers, _, _, _, item_id = _native_item(client, connection, scope)
    key = 'CaseSensitive-Key'
    created = _transition(client, headers, item_id, key, 'NEW', 0, 'IN_PROGRESS')
    replayed = _transition(client, headers, item_id, key, 'NEW', 0, 'IN_PROGRESS')
    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.json()['replayed'] is True
    assert replayed.json()['transition']['id'] == created.json()['transition']['id']
    assert _transition(client, headers, item_id, key, 'NEW', 0, 'COMPLETED').status_code == 409
    assert _transition(client, headers, item_id, key, 'NEW', 9, 'IN_PROGRESS').status_code == 409
    assert _transition(client, headers, item_id, key, 'IN_PROGRESS', 0, 'IN_PROGRESS').status_code == 409
    _, other_headers = _employee(client, connection, scope)
    assert _transition(client, other_headers, item_id, key, 'NEW', 0, 'IN_PROGRESS').status_code == 409
    assert _transition(client, headers, item_id, 'different-key', 'NEW', 0, 'IN_PROGRESS').status_code == 409
    # Binary collation makes a differently-cased operation key independent.
    assert _transition(client, headers, item_id, 'casesensitive-key', 'NEW', 0, 'IN_PROGRESS').status_code == 409
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM preparation_item_transitions WHERE preparation_work_item_id=%s', (item_id,))
        assert cursor.fetchone()['count'] == 1


def test_simultaneous_start_and_complete_commit_one_transition(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers_a, _, _, _, item_id = _native_item(client, connection, scope)
    _, headers_b = _employee(client, connection, scope)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result()
            for future in (
                pool.submit(_transition, client, headers_a, item_id, 'start-a', 'NEW', 0, 'IN_PROGRESS'),
                pool.submit(_transition, client, headers_b, item_id, 'start-b', 'NEW', 0, 'IN_PROGRESS'),
            )
        ]
    assert sorted(value.status_code for value in results) == [201, 409]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result()
            for future in (
                pool.submit(_transition, client, headers_a, item_id, 'complete-a', 'IN_PROGRESS', 1, 'COMPLETED'),
                pool.submit(_transition, client, headers_b, item_id, 'complete-b', 'IN_PROGRESS', 1, 'COMPLETED'),
            )
        ]
    assert sorted(value.status_code for value in results) == [201, 409]
    detail = client.get(f'/preparation-work-items/{item_id}', headers=headers_a).json()
    assert detail['item']['execution_state'] == 'COMPLETED'
    assert detail['item']['execution_version'] == 2
    assert [value['sequence'] for value in detail['transitions']] == [1, 2]


def test_queue_filters_pagination_snapshots_and_component_execution(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, parent, fixed, option, _ = _accepted_complex_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, parent, 'COMPONENTS')
    _route(client, headers, scope.location_id, fixed, 'AREA', area['id'])
    _route(client, headers, scope.location_id, option, 'AREA', area['id'])
    routed = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers).json()
    work = routed['works'][0]
    first, second = work['items']
    queue = client.get('/preparation-works', headers=headers, params={'location_id': scope.location_id, 'preparation_area_id': area['id'], 'restaurant_order_id': order_id, 'limit': 1})
    assert queue.status_code == 200
    assert len(queue.json()) == 1
    assert queue.json()[0]['execution_state'] == 'NEW'
    assert {item['product_name'] for item in queue.json()[0]['items']} == {'Fries', 'Cola'}
    assert all(item['source_type'] == 'COMPONENT' for item in queue.json()[0]['items'])
    assert all(item['parent_product_name'] == 'Combo' for item in queue.json()[0]['items'])
    assert _transition(client, headers, first['id'], 'first-start', 'NEW', 0, 'IN_PROGRESS').status_code == 201
    assert _transition(client, headers, first['id'], 'first-done', 'IN_PROGRESS', 1, 'COMPLETED').status_code == 201
    mixed = client.get(f"/preparation-works/{work['id']}", headers=headers).json()
    assert mixed['execution_state'] == 'IN_PROGRESS'
    new = client.get('/preparation-works', headers=headers, params={'location_id': scope.location_id, 'execution_state': 'NEW'})
    assert new.json() == []
    in_progress = client.get('/preparation-works', headers=headers, params={'location_id': scope.location_id, 'execution_state': 'IN_PROGRESS'})
    assert [value['id'] for value in in_progress.json()] == [work['id']]
    completed = client.get('/preparation-works', headers=headers, params={'location_id': scope.location_id, 'execution_state': 'COMPLETED'})
    assert completed.json() == []
    assert _transition(client, headers, second['id'], 'second-start', 'NEW', 0, 'IN_PROGRESS').status_code == 201
    assert _transition(client, headers, second['id'], 'second-done', 'IN_PROGRESS', 1, 'COMPLETED').status_code == 201
    assert client.get(f"/preparation-works/{work['id']}", headers=headers).json()['execution_state'] == 'COMPLETED'
    completed = client.get('/preparation-works', headers=headers, params={'location_id': scope.location_id, 'execution_state': 'COMPLETED'})
    assert [value['id'] for value in completed.json()] == [work['id']]
    assert client.get('/preparation-works', headers=headers, params={'location_id': scope.location_id}).json() == []


def test_different_items_execute_concurrently_without_interference(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, parent, fixed, option, _ = _accepted_complex_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, parent, 'COMPONENTS')
    _route(client, headers, scope.location_id, fixed, 'AREA', area['id'])
    _route(client, headers, scope.location_id, option, 'AREA', area['id'])
    items = client.post(
        f'/restaurant-orders/{order_id}/preparation-routing', headers=headers
    ).json()['works'][0]['items']

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result()
            for future in (
                pool.submit(_transition, client, headers, items[0]['id'], 'item-a', 'NEW', 0, 'IN_PROGRESS'),
                pool.submit(_transition, client, headers, items[1]['id'], 'item-b', 'NEW', 0, 'IN_PROGRESS'),
            )
        ]

    assert [value.status_code for value in results] == [201, 201]
    for item in items:
        detail = client.get(f"/preparation-work-items/{item['id']}", headers=headers).json()
        assert detail['item']['execution_state'] == 'IN_PROGRESS'
        assert detail['item']['execution_version'] == 1
        assert len(detail['transitions']) == 1


def test_transitions_do_not_mutate_order_routing_area_or_pos_evidence(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, product_id, 'AREA', area['id'])
    routed = client.post(
        f'/restaurant-orders/{order_id}/preparation-routing', headers=headers
    ).json()
    item_id = routed['works'][0]['items'][0]['id']

    def evidence():
        statements = (
            ('restaurant_orders', 'restaurant_orders', 'id=%s', (order_id,)),
            ('restaurant_order_items', 'restaurant_order_items', 'order_id=%s', (order_id,)),
            ('restaurant_order_item_components', 'restaurant_order_item_components', 'order_id=%s', (order_id,)),
            ('preparation_routings', 'preparation_routings', 'restaurant_order_id=%s', (order_id,)),
            ('preparation_works', 'preparation_works', 'restaurant_order_id=%s', (order_id,)),
            ('preparation_areas', 'preparation_areas', 'id=%s', (area['id'],)),
            ('pos_order_submissions', 'pos_order_submissions', 'restaurant_order_id=%s', (order_id,)),
        )
        result = {}
        with connection.cursor() as cursor:
            for key, table, predicate, parameters in statements:
                cursor.execute(f'SELECT * FROM {table} WHERE {predicate} ORDER BY id', parameters)
                result[key] = cursor.fetchall()
        return result

    before = evidence()
    assert _transition(client, headers, item_id, 'immutable-start', 'NEW', 0, 'IN_PROGRESS').status_code == 201
    assert _transition(client, headers, item_id, 'immutable-complete', 'IN_PROGRESS', 1, 'COMPLETED').status_code == 201
    assert evidence() == before


def test_security_tenant_permission_inactive_diner_and_actor_spoofing(client, sql_connection, integration_settings):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers, _, _, _, item_id = _native_item(client, connection, scope)
    other = _scope(connection, f'{prefix}-other')
    assert client.get(f'/preparation-work-items/{item_id}', headers=_headers(client, other)).status_code == 404
    _, read_only = _employee(client, connection, scope, execute=False)
    assert _transition(client, read_only, item_id, 'forbidden', 'NEW', 0, 'IN_PROGRESS').status_code == 403
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM tenant_memberships WHERE tenant_id=%s ORDER BY id LIMIT 1', (scope.tenant_id,))
        membership_id = cursor.fetchone()['id']
        cursor.execute('SELECT id,service_session_id FROM diner_sessions WHERE tenant_id=%s ORDER BY id LIMIT 1', (scope.tenant_id,))
        diner = cursor.fetchone()
    diner_token, _ = create_diner_access_token(
        diner_session_id=diner['id'], tenant_id=scope.tenant_id,
        service_session_id=diner['service_session_id'], settings=integration_settings,
    )
    diner_response = _transition(client, {'Authorization': f'Bearer {diner_token}'}, item_id, 'diner', 'NEW', 0, 'IN_PROGRESS')
    assert diner_response.status_code == 401
    spoofed = client.post(
        f'/preparation-work-items/{item_id}/transitions',
        headers={**headers, 'Idempotency-Key': 'spoof'},
        json={'expected_state': 'NEW', 'expected_version': 0, 'to_state': 'IN_PROGRESS', 'actor_membership_id': membership_id + 999},
    )
    assert spoofed.status_code == 422
    with connection.cursor() as cursor:
        cursor.execute('UPDATE tenant_memberships SET status=\'INACTIVE\' WHERE id=%s', (membership_id,))
    assert _transition(client, headers, item_id, 'inactive', 'NEW', 0, 'IN_PROGRESS').status_code == 403
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM preparation_item_transitions WHERE preparation_work_item_id=%s', (item_id,))
        assert cursor.fetchone()['count'] == 0


def test_external_pos_owner_has_no_native_execution_item(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, _, _ = _accepted_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id, 'EXTERNAL_POS')
    result = client.post(f'/restaurant-orders/{order_id}/preparation-routing', headers=headers)
    assert result.status_code == 200
    assert result.json()['works'] == []
    queue = client.get('/preparation-works', headers=headers, params={'location_id': scope.location_id, 'restaurant_order_id': order_id})
    assert queue.status_code == 200 and queue.json() == []
