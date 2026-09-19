from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from test_preparation_execution_foundation import _native_item, _transition
from test_pos_order_submission_recovery import _headers, _scope
from test_service_responsibility_api import _put
from test_staff_operational_requests import _enable_staff
from test_waiter_operational_request_routing import (
    _action,
    _create_request,
    _prepare,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _respond(
    client: TestClient,
    headers: dict[str, str],
    location_id: int,
    request_id: int,
    key: str,
    content: str,
):
    return client.post(
        f'/waiter/operational-requests/{request_id}/respond',
        params={'location_id': location_id},
        headers={**headers, 'Idempotency-Key': key},
        json={
            'content_text': content,
            'modality': 'TEXT',
            'language': 'es-MX',
            'language_source': 'DECLARED',
        },
    )


def _request_evidence(connection, request_id: int):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT status,acknowledged_by_membership_id,acknowledged_at,'
            'resolved_by_membership_id,resolved_at FROM diner_operational_requests '
            'WHERE id=%s',
            (request_id,),
        )
        return cursor.fetchone()


def test_responder_lifecycle_idempotency_and_diner_availability(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, _, _, diner_headers, waiters = _prepare(client, connection, prefix)
    waiter = waiters[0]
    request_id = _create_request(client, diner_headers, 'mp7-lifecycle')

    pending_before = _request_evidence(connection, request_id)
    first = _respond(
        client, waiter, scope.location_id, request_id, 'reply-one', '  Ya voy.  ',
    )
    assert first.status_code == 200, first.text
    message = first.json()
    assert message['operational_request_id'] == request_id
    assert message['author_type'] == 'HUMAN_STAFF'
    assert message['content_text'] == 'Ya voy.'
    assert _request_evidence(connection, request_id) == pending_before

    replay = _respond(
        client, waiter, scope.location_id, request_id, 'reply-one', 'Ya voy.',
    )
    assert replay.status_code == 200, replay.text
    assert replay.json() == message
    conflict = _respond(
        client, waiter, scope.location_id, request_id, 'reply-one', 'Otro contenido',
    )
    assert conflict.status_code == 409

    second = _respond(
        client, waiter, scope.location_id, request_id, 'reply-two', '¿Algo más?',
    )
    assert second.status_code == 200, second.text
    assert second.json()['message_id'] != message['message_id']
    assert second.json()['participant_id'] == message['participant_id']

    acknowledged = _action(
        client, waiter, scope.location_id, request_id, 'acknowledge',
    )
    assert acknowledged.status_code == 200, acknowledged.text
    acknowledged_before = _request_evidence(connection, request_id)
    assert _respond(
        client, waiter, scope.location_id, request_id, 'reply-ack', 'Enterado.',
    ).status_code == 200
    assert _request_evidence(connection, request_id) == acknowledged_before

    completed = _action(client, waiter, scope.location_id, request_id, 'complete')
    assert completed.status_code == 200, completed.text
    completed_before = _request_evidence(connection, request_id)
    final = _respond(
        client, waiter, scope.location_id, request_id, 'reply-complete', 'Listo.',
    )
    assert final.status_code == 200, final.text
    assert _request_evidence(connection, request_id) == completed_before

    transcript = client.get('/diner/conversation/messages', headers=diner_headers)
    assert transcript.status_code == 200, transcript.text
    items = transcript.json()['items']
    projected = next(item for item in items if item['message_id'] == message['message_id'])
    assert projected == {
        'message_id': message['message_id'],
        'author_type': 'HUMAN_STAFF',
        'sequence_number': message['sequence_number'],
        'modality': message['modality'],
        'content_text': message['content_text'],
        'language': message['language'],
        'language_source': message['language_source'],
        'created_at': message['created_at'],
    }
    assert [item['sequence_number'] for item in items] == sorted(
        item['sequence_number'] for item in items
    )
    assert all('response_idempotency_key' not in item for item in items)

    _, _, _, foreign_diner_headers, _ = _prepare(
        client, connection, f'{prefix}-foreign',
    )
    foreign_transcript = client.get(
        '/diner/conversation/messages', headers=foreign_diner_headers,
    )
    assert foreign_transcript.status_code == 200, foreign_transcript.text
    assert message['message_id'] not in {
        item['message_id'] for item in foreign_transcript.json()['items']
    }
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM operational_request_waiter_states '
            'WHERE operational_request_id=%s',
            (request_id,),
        )
        assert cursor.fetchone()['count'] == 0


def test_concurrent_first_response_and_current_responsibility(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, actor_headers, session_id, diner_headers, waiters = _prepare(
        client, connection, prefix,
    )
    first, second, _ = waiters
    assert _put(
        client, scope, actor_headers, session_id, list(scope.waiter_ids[:2]),
        1, 'mp7-shared',
    ).status_code == 200
    request_id = _create_request(client, diner_headers, 'mp7-concurrent')

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(
            lambda _: _respond(
                client, first, scope.location_id, request_id,
                'same-concurrent-key', 'Respuesta concurrente',
            ),
            range(2),
        ))
    assert [response.status_code for response in responses] == [200, 200]
    assert len({response.json()['message_id'] for response in responses}) == 1
    assert len({response.json()['participant_id'] for response in responses}) == 1

    independent = _respond(
        client, second, scope.location_id, request_id, 'second-waiter', 'También voy.',
    )
    assert independent.status_code == 200, independent.text
    assert independent.json()['participant_id'] != responses[0].json()['participant_id']

    assert _put(
        client, scope, actor_headers, session_id, [scope.waiter_ids[1]],
        2, 'mp7-remove-first',
    ).status_code == 200
    denied_replay = _respond(
        client, first, scope.location_id, request_id,
        'same-concurrent-key', 'Respuesta concurrente',
    )
    assert denied_replay.status_code == 404
    assert _respond(
        client, second, scope.location_id, request_id, 'second-current', 'Sigo aquí.',
    ).status_code == 200

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS count FROM conversation_participants "
            "WHERE conversation_id=%s AND participant_type='HUMAN_STAFF'",
            (responses[0].json()['conversation_id'],),
        )
        assert cursor.fetchone()['count'] == 2
        cursor.execute(
            'SELECT COUNT(*) AS count FROM conversation_messages '
            'WHERE operational_request_id=%s AND response_idempotency_key=%s',
            (request_id, 'same-concurrent-key'),
        )
        assert cursor.fetchone()['count'] == 1


def test_cancelled_and_closed_service_reject_without_new_message(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, actor_headers, session_id, diner_headers, waiters = _prepare(
        client, connection, prefix,
    )
    waiter = waiters[0]
    cancelled_id = _create_request(client, diner_headers, 'mp7-cancelled')
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE diner_operational_requests SET status='CANCELLED',"
            'resolved_by_membership_id=%s,resolved_at=CURRENT_TIMESTAMP WHERE id=%s',
            (scope.waiter_ids[0], cancelled_id),
        )
    rejected = _respond(
        client, waiter, scope.location_id, cancelled_id, 'cancelled-response', 'No.',
    )
    assert rejected.status_code == 409

    historical_id = _create_request(client, diner_headers, 'mp7-before-close')
    committed = _respond(
        client, waiter, scope.location_id, historical_id, 'before-close', 'Persistida.',
    )
    assert committed.status_code == 200, committed.text
    closed = client.post(
        f'/restaurant-service-sessions/{session_id}/close', headers=actor_headers,
    )
    assert closed.status_code == 200, closed.text
    after_close = _respond(
        client, waiter, scope.location_id, historical_id, 'after-close', 'Tarde.',
    )
    assert after_close.status_code == 409
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT response_idempotency_key FROM conversation_messages '
            'WHERE operational_request_id IN (%s,%s) ORDER BY id',
            (cancelled_id, historical_id),
        )
        assert cursor.fetchall() == [{'response_idempotency_key': 'before-close'}]


def test_responder_serializes_with_responsibility_removal_and_service_close(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, actor_headers, session_id, diner_headers, waiters = _prepare(
        client, connection, prefix,
    )
    first, second, _ = waiters
    assert _put(
        client, scope, actor_headers, session_id, list(scope.waiter_ids[:2]),
        1, 'mp7-race-shared',
    ).status_code == 200
    request_id = _create_request(client, diner_headers, 'mp7-race-request')
    responsibility_barrier = Barrier(2)

    def respond_during_removal():
        responsibility_barrier.wait()
        return _respond(
            client, first, scope.location_id, request_id,
            'responsibility-race', 'Puede quedar como historia.',
        )

    def remove_responsibility():
        responsibility_barrier.wait()
        return _put(
            client, scope, actor_headers, session_id, [scope.waiter_ids[1]],
            2, 'mp7-race-remove',
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        response_future = pool.submit(respond_during_removal)
        removal_future = pool.submit(remove_responsibility)
        response = response_future.result(timeout=15)
        removal = removal_future.result(timeout=15)
    assert removal.status_code == 200, removal.text
    assert response.status_code in {200, 404}
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM conversation_messages '
            'WHERE operational_request_id=%s AND response_idempotency_key=%s',
            (request_id, 'responsibility-race'),
        )
        assert cursor.fetchone()['count'] == (1 if response.status_code == 200 else 0)

    close_request_id = _create_request(client, diner_headers, 'mp7-close-race')
    close_barrier = Barrier(2)

    def respond_during_close():
        close_barrier.wait()
        return _respond(
            client, second, scope.location_id, close_request_id,
            'close-race', 'Antes o después del cierre.',
        )

    def close_service():
        close_barrier.wait()
        return client.post(
            f'/restaurant-service-sessions/{session_id}/close', headers=actor_headers,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        response_future = pool.submit(respond_during_close)
        close_future = pool.submit(close_service)
        response = response_future.result(timeout=15)
        closed = close_future.result(timeout=15)
    assert closed.status_code == 200, closed.text
    assert response.status_code in {200, 409}
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM conversation_messages '
            'WHERE operational_request_id=%s AND response_idempotency_key=%s',
            (close_request_id, 'close-race'),
        )
        assert cursor.fetchone()['count'] == (1 if response.status_code == 200 else 0)


def test_preparation_ready_has_no_fabricated_diner_destination(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers, _, _, work_id, item_id = _native_item(client, connection, scope)
    assert _transition(
        client, headers, item_id, 'mp7-ready-start', 'NEW', 0, 'IN_PROGRESS',
    ).status_code == 201
    assert _transition(
        client, headers, item_id, 'mp7-ready-complete',
        'IN_PROGRESS', 1, 'COMPLETED',
    ).status_code == 201
    _enable_staff(
        connection,
        scope,
        permissions=('operational_request.read', 'operational_request.manage'),
    )
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM diner_operational_requests WHERE preparation_work_id=%s',
            (work_id,),
        )
        request_id = int(cursor.fetchone()['id'])
    response = _respond(
        client, headers, scope.location_id, request_id, 'no-diner', '¿Quién recibe?',
    )
    assert response.status_code == 409, response.text
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM conversation_messages '
            'WHERE operational_request_id=%s',
            (request_id,),
        )
        assert cursor.fetchone()['count'] == 0
