from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.restaurant.preparation import service as preparation_service
from test_pos_order_submission_recovery import _scope
from test_preparation_execution_foundation import _employee, _native_item, _transition
from test_service_responsibility_api import _put
from test_staff_operational_requests import _enable_staff


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _ready(client, connection, prefix):
    scope = _scope(connection, prefix)
    headers, _, _, work_id, item_id = _native_item(client, connection, scope)
    membership_id = _enable_staff(
        connection,
        scope,
        permissions=('operational_request.read', 'operational_request.manage'),
    )
    assert _transition(
        client, headers, item_id, 'mp6-start', 'NEW', 0, 'IN_PROGRESS',
    ).status_code == 201
    assert _transition(
        client, headers, item_id, 'mp6-complete', 'IN_PROGRESS', 1, 'COMPLETED',
    ).status_code == 201
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM diner_operational_requests WHERE preparation_work_id=%s',
            (work_id,),
        )
        request_id = int(cursor.fetchone()['id'])
    return scope, headers, membership_id, work_id, item_id, request_id


def _action(client, headers, scope, request_id: int, action: str):
    return client.post(
        f'/waiter/operational-requests/{request_id}/{action}',
        headers=headers,
        params={'location_id': scope.location_id},
    )


def _evidence(connection, work_id: int, request_id: int):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT picked_up_by_membership_id,picked_up_at,'
            'delivered_by_membership_id,delivered_at '
            'FROM preparation_works WHERE id=%s',
            (work_id,),
        )
        work = cursor.fetchone()
        cursor.execute(
            'SELECT status,resolved_by_membership_id,resolved_at '
            'FROM diner_operational_requests WHERE id=%s',
            (request_id,),
        )
        request = cursor.fetchone()
    return work, request


def test_pickup_delivery_lifecycle_replays_and_manual_completion_guard(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, headers, membership_id, work_id, _, request_id = _ready(
        client, connection, prefix,
    )

    waiter_complete = _action(client, headers, scope, request_id, 'complete')
    assert waiter_complete.status_code == 409
    staff_complete = client.post(
        f'/staff/operational-requests/{request_id}/complete',
        headers=headers,
        params={'location_id': scope.location_id},
    )
    assert staff_complete.status_code == 409
    assert _action(client, headers, scope, request_id, 'deliver').status_code == 409

    hidden = _action(client, headers, scope, request_id, 'hide')
    assert hidden.status_code == 200
    hidden_at = hidden.json()['current_waiter_hidden_at']
    pickup = _action(client, headers, scope, request_id, 'pick-up')
    assert pickup.status_code == 200, pickup.text
    pickup_body = pickup.json()
    assert pickup_body['status'] == 'PENDING'
    assert pickup_body['picked_up_by_membership_id'] == membership_id
    assert pickup_body['picked_up_at'] is not None
    assert pickup_body['delivered_by_membership_id'] is None
    assert pickup_body['delivered_at'] is None
    assert pickup_body['current_waiter_hidden_at'] == hidden_at

    pickup_replay = _action(client, headers, scope, request_id, 'pick-up')
    assert pickup_replay.status_code == 200
    assert pickup_replay.json()['picked_up_at'] == pickup_body['picked_up_at']
    assert pickup_replay.json()['picked_up_by_membership_id'] == membership_id

    delivered = _action(client, headers, scope, request_id, 'deliver')
    assert delivered.status_code == 200, delivered.text
    delivered_body = delivered.json()
    assert delivered_body['status'] == 'COMPLETED'
    assert delivered_body['delivered_by_membership_id'] == membership_id
    assert delivered_body['resolved_by_membership_id'] == membership_id
    assert delivered_body['delivered_at'] == delivered_body['resolved_at']
    assert delivered_body['picked_up_at'] == pickup_body['picked_up_at']
    assert delivered_body['current_waiter_hidden_at'] == hidden_at

    delivery_replay = _action(client, headers, scope, request_id, 'deliver')
    assert delivery_replay.status_code == 200
    assert delivery_replay.json()['delivered_at'] == delivered_body['delivered_at']
    assert delivery_replay.json()['delivered_by_membership_id'] == membership_id


def test_concurrent_pickup_and_delivery_preserve_first_evidence(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, headers, membership_id, work_id, _, request_id = _ready(
        client, connection, prefix,
    )
    acknowledged = _action(client, headers, scope, request_id, 'acknowledge')
    assert acknowledged.status_code == 200
    acknowledged_by = acknowledged.json()['acknowledged_by_membership_id']
    acknowledged_at = acknowledged.json()['acknowledged_at']
    with ThreadPoolExecutor(max_workers=2) as pool:
        pickups = list(pool.map(
            lambda _: _action(client, headers, scope, request_id, 'pick-up'),
            range(2),
        ))
    assert [response.status_code for response in pickups] == [200, 200]
    assert {response.json()['picked_up_by_membership_id'] for response in pickups} == {
        membership_id,
    }
    assert len({response.json()['picked_up_at'] for response in pickups}) == 1

    with ThreadPoolExecutor(max_workers=2) as pool:
        deliveries = list(pool.map(
            lambda _: _action(client, headers, scope, request_id, 'deliver'),
            range(2),
        ))
    assert [response.status_code for response in deliveries] == [200, 200]
    assert len({response.json()['delivered_at'] for response in deliveries}) == 1
    work, request = _evidence(connection, work_id, request_id)
    assert work['delivered_by_membership_id'] == membership_id
    assert request['resolved_by_membership_id'] == membership_id
    assert work['delivered_at'] == request['resolved_at']
    detail = client.get(
        f'/waiter/operational-requests/{request_id}', headers=headers,
        params={'location_id': scope.location_id},
    ).json()
    assert detail['acknowledged_by_membership_id'] == acknowledged_by
    assert detail['acknowledged_at'] == acknowledged_at


def test_not_ready_wrong_type_and_legacy_inconsistency_conflict(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, headers, membership_id, work_id, item_id, request_id = _ready(
        client, connection, prefix,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE preparation_work_items SET execution_state='IN_PROGRESS' WHERE id=%s",
            (item_id,),
        )
    assert _action(client, headers, scope, request_id, 'pick-up').status_code == 409
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE preparation_work_items SET execution_state='COMPLETED' WHERE id=%s",
            (item_id,),
        )
        cursor.execute(
            "UPDATE diner_operational_requests SET status='COMPLETED',"
            'resolved_by_membership_id=%s,resolved_at=CURRENT_TIMESTAMP WHERE id=%s',
            (membership_id, request_id),
        )
    assert _action(client, headers, scope, request_id, 'deliver').status_code == 409
    work, _ = _evidence(connection, work_id, request_id)
    assert work['delivered_at'] is None

    joined = client.post('/diner/operational-requests', headers={
        **headers, 'Idempotency-Key': 'wrong-handoff-type',
    }, json={'request_type': 'HUMAN_ASSISTANCE'})
    # Staff authentication cannot create a diner request; use an existing non-preparation row.
    if joined.status_code != 201:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT diner_session_id,service_session_id,resource_id,organization_id '
                'FROM restaurant_orders WHERE id=(SELECT restaurant_order_id '
                'FROM preparation_works WHERE id=%s)',
                (work_id,),
            )
            context = cursor.fetchone()
            cursor.execute(
                'INSERT INTO diner_operational_requests '
                '(tenant_id,organization_id,location_id,resource_id,service_session_id,'
                'diner_session_id,request_type,status,idempotency_key,request_fingerprint) '
                "VALUES (%s,%s,%s,%s,%s,%s,'HUMAN_ASSISTANCE','PENDING',%s,%s)",
                (
                    scope.tenant_id, context['organization_id'], scope.location_id,
                    context['resource_id'], context['service_session_id'],
                    context['diner_session_id'], 'wrong-handoff-type', '0' * 64,
                ),
            )
            wrong_id = int(cursor.lastrowid)
    else:
        wrong_id = int(joined.json()['id'])
    assert _action(client, headers, scope, wrong_id, 'pick-up').status_code == 409


def test_forced_delivery_failure_rolls_back_work_and_request(
    client, sql_connection, monkeypatch,
):
    connection, prefix = sql_connection
    scope, headers, _, work_id, _, request_id = _ready(client, connection, prefix)
    assert _action(client, headers, scope, request_id, 'pick-up').status_code == 200
    original = preparation_service.deliver_preparation_work

    async def fail_after_delivery(*args, **kwargs):
        await original(*args, **kwargs)
        raise RuntimeError('forced completion integration failure')

    monkeypatch.setattr(preparation_service, 'deliver_preparation_work', fail_after_delivery)
    failed = _action(client, headers, scope, request_id, 'deliver')
    assert failed.status_code == 500
    work, request = _evidence(connection, work_id, request_id)
    assert work['delivered_by_membership_id'] is None
    assert work['delivered_at'] is None
    assert request['status'] == 'PENDING'
    assert request['resolved_by_membership_id'] is None
    assert request['resolved_at'] is None

    monkeypatch.setattr(preparation_service, 'deliver_preparation_work', original)

    async def fail_commit(self):
        raise RuntimeError('forced atomic commit failure')

    monkeypatch.setattr(AsyncSession, 'commit', fail_commit)
    commit_failed = _action(client, headers, scope, request_id, 'deliver')
    assert commit_failed.status_code == 500
    work, request = _evidence(connection, work_id, request_id)
    assert work['delivered_by_membership_id'] is None
    assert work['delivered_at'] is None
    assert request['status'] == 'PENDING'
    assert request['resolved_by_membership_id'] is None
    assert request['resolved_at'] is None


def test_current_responsibility_can_transfer_between_pickup_and_delivery(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, headers, first_id, work_id, _, request_id = _ready(
        client, connection, prefix,
    )
    second_id, second_headers = _employee(client, connection, scope)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT role_id FROM membership_roles WHERE membership_id=%s',
            (second_id,),
        )
        second_role_id = int(cursor.fetchone()['role_id'])
        for code in (
            'operational_request.read', 'operational_request.manage',
            'order_draft.manage', 'restaurant_service.manage',
        ):
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
            cursor.execute(
                'INSERT IGNORE INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
                (second_role_id, permission_id),
            )
        cursor.execute(
            'INSERT INTO table_waiter_assignments '
            '(tenant_id,location_id,table_resource_id,waiter_membership_id,is_responsible) '
            'VALUES (%s,%s,%s,%s,0)',
            (scope.tenant_id, scope.location_id, scope.resource_id, second_id),
        )
        cursor.execute(
            'SELECT service_session_id FROM diner_operational_requests WHERE id=%s',
            (request_id,),
        )
        session_id = int(cursor.fetchone()['service_session_id'])

    shared = _put(
        client, scope, headers, session_id, [first_id, second_id], 1, 'mp6-shared',
    )
    assert shared.status_code == 200, shared.text
    pickup = _action(client, headers, scope, request_id, 'pick-up')
    assert pickup.status_code == 200
    assert pickup.json()['picked_up_by_membership_id'] == first_id

    transferred = _put(
        client, scope, headers, session_id, [second_id], 2, 'mp6-transfer',
    )
    assert transferred.status_code == 200, transferred.text
    assert _action(client, headers, scope, request_id, 'pick-up').status_code == 404
    delivered = _action(client, second_headers, scope, request_id, 'deliver')
    assert delivered.status_code == 200, delivered.text
    body = delivered.json()
    assert body['picked_up_by_membership_id'] == first_id
    assert body['delivered_by_membership_id'] == second_id
    assert body['resolved_by_membership_id'] == second_id
    assert _action(client, headers, scope, request_id, 'deliver').status_code == 404
    replay = _action(client, second_headers, scope, request_id, 'deliver')
    assert replay.status_code == 200
    assert replay.json()['delivered_at'] == body['delivered_at']


def test_handoff_and_responsibility_transitions_share_serialization_prefix(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, headers, first_id, work_id, _, request_id = _ready(
        client, connection, prefix,
    )
    second_id, second_headers = _employee(client, connection, scope)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT role_id FROM membership_roles WHERE membership_id=%s', (second_id,),
        )
        role_id = int(cursor.fetchone()['role_id'])
        for code in (
            'operational_request.read', 'operational_request.manage',
            'order_draft.manage', 'restaurant_service.manage',
        ):
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            cursor.execute(
                'INSERT IGNORE INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
                (role_id, int(cursor.fetchone()['id'])),
            )
        cursor.execute(
            'INSERT INTO table_waiter_assignments '
            '(tenant_id,location_id,table_resource_id,waiter_membership_id,is_responsible) '
            'VALUES (%s,%s,%s,%s,0)',
            (scope.tenant_id, scope.location_id, scope.resource_id, second_id),
        )
        cursor.execute(
            'SELECT service_session_id FROM diner_operational_requests WHERE id=%s',
            (request_id,),
        )
        session_id = int(cursor.fetchone()['service_session_id'])
    assert _put(
        client, scope, headers, session_id, [first_id, second_id], 1, 'race-shared',
    ).status_code == 200

    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pickup_future = pool.submit(
            lambda: (barrier.wait(), _action(
                client, headers, scope, request_id, 'pick-up',
            ))[1]
        )
        removal_future = pool.submit(
            lambda: (barrier.wait(), _put(
                client, scope, headers, session_id, [second_id], 2, 'race-remove-pickup',
            ))[1]
        )
        pickup = pickup_future.result(timeout=15)
        removal = removal_future.result(timeout=15)
    assert removal.status_code == 200
    assert pickup.status_code in {200, 404}
    work, _ = _evidence(connection, work_id, request_id)
    if pickup.status_code == 404:
        assert work['picked_up_at'] is None
        assert _action(client, second_headers, scope, request_id, 'pick-up').status_code == 200
    else:
        assert work['picked_up_by_membership_id'] == first_id

    assert _put(
        client, scope, headers, session_id, [first_id, second_id], 3, 'race-reshare',
    ).status_code == 200
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        delivery_future = pool.submit(
            lambda: (barrier.wait(), _action(
                client, headers, scope, request_id, 'deliver',
            ))[1]
        )
        removal_future = pool.submit(
            lambda: (barrier.wait(), _put(
                client, scope, headers, session_id, [second_id], 4, 'race-remove-delivery',
            ))[1]
        )
        delivery = delivery_future.result(timeout=15)
        removal = removal_future.result(timeout=15)
    assert removal.status_code == 200
    assert delivery.status_code in {200, 404}
    work, request = _evidence(connection, work_id, request_id)
    if delivery.status_code == 404:
        assert work['delivered_at'] is None
        assert request['status'] in {'PENDING', 'ACKNOWLEDGED'}
        assert _action(client, second_headers, scope, request_id, 'deliver').status_code == 200
    else:
        assert work['delivered_by_membership_id'] == first_id
        assert request['status'] == 'COMPLETED'
