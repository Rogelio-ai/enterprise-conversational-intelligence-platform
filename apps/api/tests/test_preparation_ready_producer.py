from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.restaurant.operational_requests import service as operational_request_service
from test_pos_order_submission_recovery import _accepted_complex_order, _headers, _scope
from test_preparation_execution_foundation import _native_item, _transition
from test_preparation_routing_foundation import _area, _owner, _route
from test_staff_operational_requests import _enable_staff


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _two_item_work(client, connection, scope):
    order_id, parent, fixed, option, _ = _accepted_complex_order(client, connection, scope)
    headers = _headers(client, scope)
    _owner(client, headers, scope.location_id)
    area = _area(client, headers, scope.location_id)
    _route(client, headers, scope.location_id, parent, 'COMPONENTS')
    _route(client, headers, scope.location_id, fixed, 'AREA', area['id'])
    _route(client, headers, scope.location_id, option, 'AREA', area['id'])
    response = client.post(
        f'/restaurant-orders/{order_id}/preparation-routing', headers=headers,
    )
    assert response.status_code == 200, response.text
    work = response.json()['works'][0]
    return headers, order_id, area, work


def _requests(connection, work_id: int):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT * FROM diner_operational_requests WHERE preparation_work_id=%s',
            (work_id,),
        )
        return cursor.fetchall()


def test_final_completion_atomically_creates_one_projectable_request(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers, order_id, area, work_id, item_id = _native_item(
        client, connection, scope,
    )

    assert _transition(
        client, headers, item_id, 'ready-start', 'NEW', 0, 'IN_PROGRESS',
    ).status_code == 201
    assert _requests(connection, work_id) == ()

    completed = _transition(
        client, headers, item_id, 'ready-complete', 'IN_PROGRESS', 1, 'COMPLETED',
    )
    assert completed.status_code == 201, completed.text
    rows = _requests(connection, work_id)
    assert len(rows) == 1
    request = rows[0]
    assert request['request_type'] == 'PREPARATION_READY'
    assert request['status'] == 'PENDING'
    assert request['diner_session_id'] is None
    assert request['related_restaurant_check_id'] is None
    assert request['preparation_work_id'] == work_id
    assert request['resource_id'] == scope.resource_id
    assert request['idempotency_key'] == f'PREPARATION_READY:{work_id}'

    replay = _transition(
        client, headers, item_id, 'ready-complete', 'IN_PROGRESS', 1, 'COMPLETED',
    )
    assert replay.status_code == 200
    assert replay.json()['replayed'] is True
    assert len(_requests(connection, work_id)) == 1

    _enable_staff(
        connection,
        scope,
        permissions=('operational_request.read', 'operational_request.manage'),
    )
    projected = client.get(
        f'/staff/operational-requests/{request["id"]}',
        headers=headers,
        params={'location_id': scope.location_id},
    )
    assert projected.status_code == 200, projected.text
    body = projected.json()
    assert body['diner_session_id'] is None
    assert body['diner_display_name'] is None
    assert body['restaurant_order_id'] == order_id
    assert body['preparation_area_id'] == area['id']
    assert body['preparation_area_code'] == area['code']
    assert body['preparation_area_name'] == area['name']

    waiter_path = (
        f'/waiter/operational-requests/{request["id"]}'
        f'?location_id={scope.location_id}'
    )
    waiter_read = client.get(waiter_path, headers=headers)
    assert waiter_read.status_code == 200, waiter_read.text
    assert waiter_read.json()['id'] == request['id']
    entered = client.post(waiter_path.replace('?', '/entered?'), headers=headers)
    assert entered.status_code == 200
    assert entered.json()['current_waiter_entered_at'] is not None
    hidden = client.post(waiter_path.replace('?', '/hide?'), headers=headers)
    assert hidden.status_code == 200
    assert hidden.json()['current_waiter_hidden_at'] is not None
    active = client.get(
        '/waiter/operational-requests', headers=headers,
        params={'location_id': scope.location_id},
    )
    hidden_list = client.get(
        '/waiter/operational-requests', headers=headers,
        params={'location_id': scope.location_id, 'view': 'hidden'},
    )
    assert request['id'] not in {item['id'] for item in active.json()['items']}
    assert request['id'] in {item['id'] for item in hidden_list.json()['items']}
    shown = client.post(waiter_path.replace('?', '/show?'), headers=headers)
    assert shown.status_code == 200
    assert shown.json()['current_waiter_hidden_at'] is None


def test_concurrent_final_siblings_serialize_and_create_exactly_one_request(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers, _, _, work = _two_item_work(client, connection, scope)
    items = work['items']
    for index, item in enumerate(items):
        assert _transition(
            client, headers, item['id'], f'sibling-start-{index}',
            'NEW', 0, 'IN_PROGRESS',
        ).status_code == 201
    assert _requests(connection, work['id']) == ()

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [future.result(timeout=15) for future in (
            pool.submit(
                _transition, client, headers, items[0]['id'], 'sibling-complete-0',
                'IN_PROGRESS', 1, 'COMPLETED',
            ),
            pool.submit(
                _transition, client, headers, items[1]['id'], 'sibling-complete-1',
                'IN_PROGRESS', 1, 'COMPLETED',
            ),
        )]
    assert [response.status_code for response in responses] == [201, 201]
    assert len(_requests(connection, work['id'])) == 1
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT execution_state FROM preparation_work_items '
            'WHERE preparation_work_id=%s ORDER BY id',
            (work['id'],),
        )
        assert [row['execution_state'] for row in cursor.fetchall()] == [
            'COMPLETED', 'COMPLETED',
        ]


def test_request_creation_failure_rolls_back_final_completion(
    client, sql_connection, monkeypatch,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers, _, _, work_id, item_id = _native_item(client, connection, scope)
    assert _transition(
        client, headers, item_id, 'rollback-start', 'NEW', 0, 'IN_PROGRESS',
    ).status_code == 201

    async def fail_request(*args, **kwargs):
        raise RuntimeError('forced readiness persistence failure')

    monkeypatch.setattr(
        operational_request_service, 'ensure_preparation_ready_request', fail_request,
    )
    failed = _transition(
        client, headers, item_id, 'rollback-complete',
        'IN_PROGRESS', 1, 'COMPLETED',
    )
    assert failed.status_code == 500

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT execution_state,execution_version FROM preparation_work_items WHERE id=%s',
            (item_id,),
        )
        assert cursor.fetchone() == {
            'execution_state': 'IN_PROGRESS', 'execution_version': 1,
        }
        cursor.execute(
            'SELECT COUNT(*) AS count FROM preparation_item_transitions '
            'WHERE preparation_work_item_id=%s',
            (item_id,),
        )
        assert cursor.fetchone()['count'] == 1
    assert _requests(connection, work_id) == ()
