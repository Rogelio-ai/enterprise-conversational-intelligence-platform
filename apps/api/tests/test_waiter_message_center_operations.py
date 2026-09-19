from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from test_resource_foundation import _location
from test_service_responsibility_api import _put
from test_waiter_operational_request_routing import (
    _action,
    _create_request,
    _list,
    _prepare,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _shared_request(client, connection, prefix):
    scope, actor_headers, session_id, diner_headers, waiters = _prepare(
        client, connection, prefix,
    )
    shared = _put(
        client,
        scope,
        actor_headers,
        session_id,
        list(scope.waiter_ids[:2]),
        1,
        'mp4-shared',
    )
    assert shared.status_code == 200, shared.text
    request_id = _create_request(client, diner_headers, 'mp4-request')
    return scope, actor_headers, session_id, waiters, request_id


def _view(client, headers, location_id: int, view: str | None = None):
    suffix = '' if view is None else f'&view={view}'
    return client.get(
        f'/waiter/operational-requests?location_id={location_id}{suffix}',
        headers=headers,
    )


def test_enterado_is_explicit_idempotent_and_independent_per_waiter(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, _, _, waiters, request_id = _shared_request(client, connection, prefix)
    first, second, _ = waiters

    for headers in (first, second):
        listed = _list(client, headers, scope.location_id)
        assert listed.status_code == 200
        item = listed.json()['items'][0]
        assert item['current_waiter_entered_at'] is None
        assert item['current_waiter_hidden_at'] is None
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM operational_request_waiter_states '
            'WHERE operational_request_id=%s',
            (request_id,),
        )
        assert cursor.fetchone()['count'] == 0

    first_entered = _action(client, first, scope.location_id, request_id, 'entered')
    assert first_entered.status_code == 200, first_entered.text
    first_timestamp = first_entered.json()['current_waiter_entered_at']
    assert first_timestamp is not None
    assert first_entered.json()['current_waiter_hidden_at'] is None
    assert first_entered.json()['status'] == 'PENDING'
    replay = _action(client, first, scope.location_id, request_id, 'entered')
    assert replay.status_code == 200
    assert replay.json()['current_waiter_entered_at'] == first_timestamp

    second_entered = _action(client, second, scope.location_id, request_id, 'entered')
    assert second_entered.status_code == 200
    assert second_entered.json()['current_waiter_entered_at'] is not None
    assert second_entered.json()['current_waiter_hidden_at'] is None
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT waiter_membership_id,entered_at,hidden_at '
            'FROM operational_request_waiter_states WHERE operational_request_id=%s '
            'ORDER BY waiter_membership_id',
            (request_id,),
        )
        rows = cursor.fetchall()
    assert [row['waiter_membership_id'] for row in rows] == list(scope.waiter_ids[:2])
    assert all(row['entered_at'] is not None and row['hidden_at'] is None for row in rows)


def test_concurrent_same_waiter_enterado_creates_one_canonical_row(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, _, _, waiters, request_id = _shared_request(client, connection, prefix)
    barrier = Barrier(2)

    def enter():
        barrier.wait()
        return _action(client, waiters[0], scope.location_id, request_id, 'entered')

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [future.result() for future in (pool.submit(enter), pool.submit(enter))]
    assert [response.status_code for response in responses] == [200, 200]
    assert len({response.json()['current_waiter_entered_at'] for response in responses}) == 1
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM operational_request_waiter_states '
            'WHERE operational_request_id=%s AND waiter_membership_id=%s',
            (request_id, scope.waiter_ids[0]),
        )
        assert cursor.fetchone()['count'] == 1


def test_hide_and_show_are_personal_idempotent_and_drive_active_hidden_views(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, _, _, waiters, request_id = _shared_request(client, connection, prefix)
    first, second, _ = waiters
    entered = _action(client, first, scope.location_id, request_id, 'entered').json()[
        'current_waiter_entered_at'
    ]
    hidden = _action(client, first, scope.location_id, request_id, 'hide')
    assert hidden.status_code == 200, hidden.text
    hidden_at = hidden.json()['current_waiter_hidden_at']
    assert hidden_at is not None
    assert hidden.json()['current_waiter_entered_at'] == entered
    replay = _action(client, first, scope.location_id, request_id, 'hide')
    assert replay.status_code == 200
    assert replay.json()['current_waiter_hidden_at'] == hidden_at
    assert replay.json()['current_waiter_entered_at'] == entered

    assert _view(client, first, scope.location_id).json()['items'] == []
    assert _view(client, first, scope.location_id, 'active').json()['items'] == []
    first_hidden = _view(client, first, scope.location_id, 'hidden').json()['items']
    assert [item['id'] for item in first_hidden] == [request_id]
    assert first_hidden[0]['current_waiter_hidden_at'] == hidden_at
    assert [
        item['id'] for item in _view(client, second, scope.location_id).json()['items']
    ] == [request_id]
    assert _view(client, second, scope.location_id, 'hidden').json()['items'] == []
    assert _view(client, first, scope.location_id, 'all').status_code == 422

    shown = _action(client, first, scope.location_id, request_id, 'show')
    assert shown.status_code == 200, shown.text
    assert shown.json()['current_waiter_hidden_at'] is None
    assert shown.json()['current_waiter_entered_at'] == entered
    shown_replay = _action(client, first, scope.location_id, request_id, 'show')
    assert shown_replay.status_code == 200
    assert shown_replay.json()['current_waiter_hidden_at'] is None
    assert shown_replay.json()['current_waiter_entered_at'] == entered
    assert [
        item['id'] for item in _view(client, first, scope.location_id).json()['items']
    ] == [request_id]


def test_hide_before_enterado_and_show_without_state_do_not_fabricate_awareness(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, _, _, waiters, request_id = _shared_request(client, connection, prefix)
    first = waiters[0]
    shown = _action(client, first, scope.location_id, request_id, 'show')
    assert shown.status_code == 200
    assert shown.json()['current_waiter_entered_at'] is None
    assert shown.json()['current_waiter_hidden_at'] is None
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM operational_request_waiter_states '
            'WHERE operational_request_id=%s AND waiter_membership_id=%s',
            (request_id, scope.waiter_ids[0]),
        )
        assert cursor.fetchone()['count'] == 0

    hidden = _action(client, first, scope.location_id, request_id, 'hide')
    assert hidden.status_code == 200
    assert hidden.json()['current_waiter_entered_at'] is None
    assert hidden.json()['current_waiter_hidden_at'] is not None
    restored = _action(client, first, scope.location_id, request_id, 'show')
    assert restored.status_code == 200
    assert restored.json()['current_waiter_entered_at'] is None
    assert restored.json()['current_waiter_hidden_at'] is None


def test_terminal_show_conflicts_and_hidden_state_never_reactivates_history(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, _, _, waiters, request_id = _shared_request(client, connection, prefix)
    first = waiters[0]
    assert _action(client, first, scope.location_id, request_id, 'hide').status_code == 200
    assert _action(
        client, first, scope.location_id, request_id, 'acknowledge',
    ).status_code == 200
    completed = _action(client, first, scope.location_id, request_id, 'complete')
    assert completed.status_code == 200
    conflict = _action(client, first, scope.location_id, request_id, 'show')
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'OPERATIONAL_REQUEST_STATE_CONFLICT'
    assert _view(client, first, scope.location_id, 'hidden').json()['items'] == []
    assert _view(client, first, scope.location_id).json()['items'] == []
    detail = client.get(
        f'/waiter/operational-requests/{request_id}?location_id={scope.location_id}',
        headers=first,
    )
    assert detail.status_code == 200
    assert detail.json()['status'] == 'COMPLETED'
    assert detail.json()['current_waiter_hidden_at'] is not None


def test_atendido_records_first_actor_and_preserves_enterado_and_completion(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, _, _, waiters, request_id = _shared_request(client, connection, prefix)
    first, second, _ = waiters
    entered_at = _action(
        client, first, scope.location_id, request_id, 'entered',
    ).json()['current_waiter_entered_at']
    acknowledged = _action(client, first, scope.location_id, request_id, 'acknowledge')
    assert acknowledged.status_code == 200, acknowledged.text
    evidence = acknowledged.json()
    assert evidence['status'] == 'ACKNOWLEDGED'
    assert evidence['acknowledged_by_membership_id'] == scope.waiter_ids[0]
    assert evidence['acknowledged_at'] is not None
    assert evidence['current_waiter_entered_at'] == entered_at

    replay = _action(client, second, scope.location_id, request_id, 'acknowledge')
    assert replay.status_code == 200
    assert replay.json()['acknowledged_by_membership_id'] == scope.waiter_ids[0]
    assert replay.json()['acknowledged_at'] == evidence['acknowledged_at']
    assert replay.json()['current_waiter_entered_at'] is None
    completed = _action(client, second, scope.location_id, request_id, 'complete')
    assert completed.status_code == 200
    assert completed.json()['status'] == 'COMPLETED'
    assert completed.json()['acknowledged_by_membership_id'] == scope.waiter_ids[0]
    assert completed.json()['acknowledged_at'] == evidence['acknowledged_at']
    assert completed.json()['resolved_by_membership_id'] == scope.waiter_ids[1]


def test_concurrent_atendido_has_one_effective_actor_and_timestamp(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, _, _, waiters, request_id = _shared_request(client, connection, prefix)
    barrier = Barrier(2)

    def acknowledge(headers):
        barrier.wait()
        return _action(client, headers, scope.location_id, request_id, 'acknowledge')

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(acknowledge, headers) for headers in waiters[:2]]
        responses = [future.result() for future in futures]
    assert [response.status_code for response in responses] == [200, 200]
    assert {response.json()['status'] for response in responses} == {'ACKNOWLEDGED'}
    assert len({response.json()['acknowledged_at'] for response in responses}) == 1
    actors = {response.json()['acknowledged_by_membership_id'] for response in responses}
    assert len(actors) == 1
    assert actors <= set(scope.waiter_ids[:2])


def test_legacy_acknowledged_replay_preserves_unknown_actor_and_time(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, _, _, waiters, request_id = _shared_request(client, connection, prefix)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE diner_operational_requests SET status='ACKNOWLEDGED' WHERE id=%s",
            (request_id,),
        )
    replay = _action(client, waiters[1], scope.location_id, request_id, 'acknowledge')
    assert replay.status_code == 200
    assert replay.json()['status'] == 'ACKNOWLEDGED'
    assert replay.json()['acknowledged_by_membership_id'] is None
    assert replay.json()['acknowledged_at'] is None


def test_authority_permission_and_historical_state_never_restore_routing(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, actor_headers, session_id, waiters, request_id = _shared_request(
        client, connection, prefix,
    )
    first, second, third = waiters
    assert _action(client, first, scope.location_id, request_id, 'entered').status_code == 200
    for action in ('entered', 'hide', 'show', 'acknowledge'):
        assert _action(client, third, scope.location_id, request_id, action).status_code == 404

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT MR.role_id,P.id AS permission_id FROM membership_roles MR '
            'JOIN role_permissions RP ON RP.role_id=MR.role_id '
            'JOIN permissions P ON P.id=RP.permission_id '
            "WHERE MR.membership_id=%s AND P.code='operational_request.manage'",
            (scope.waiter_ids[1],),
        )
        authority = cursor.fetchone()
        cursor.execute(
            'DELETE FROM role_permissions WHERE role_id=%s AND permission_id=%s',
            (authority['role_id'], authority['permission_id']),
        )
    assert _action(client, second, scope.location_id, request_id, 'entered').status_code == 403

    ungranted_location = _location(
        connection, scope.actor.tenant_id, scope.organization_id, 'MP4-UNGRANTED',
    )
    assert _action(client, first, ungranted_location, request_id, 'entered').status_code == 404

    changed = _put(
        client,
        scope,
        actor_headers,
        session_id,
        [scope.waiter_ids[1]],
        2,
        'mp4-remove-first',
    )
    assert changed.status_code == 200, changed.text
    assert _action(client, first, scope.location_id, request_id, 'entered').status_code == 404
    assert _view(client, first, scope.location_id, 'hidden').json()['items'] == []
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT entered_at FROM operational_request_waiter_states '
            'WHERE operational_request_id=%s AND waiter_membership_id=%s',
            (request_id, scope.waiter_ids[0]),
        )
        assert cursor.fetchone()['entered_at'] is not None


def test_enterado_and_responsibility_transition_serialize_to_one_winner(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope, actor_headers, session_id, waiters, request_id = _shared_request(
        client, connection, prefix,
    )
    barrier = Barrier(2)

    def enter():
        barrier.wait()
        return _action(client, waiters[0], scope.location_id, request_id, 'entered')

    def remove():
        barrier.wait()
        return _put(
            client,
            scope,
            actor_headers,
            session_id,
            [scope.waiter_ids[1]],
            2,
            'mp4-enter-remove-race',
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        action_future = pool.submit(enter)
        transition_future = pool.submit(remove)
        action_response = action_future.result()
        transition_response = transition_future.result()
    assert transition_response.status_code == 200, transition_response.text
    assert action_response.status_code in {200, 404}
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM operational_request_waiter_states '
            'WHERE operational_request_id=%s AND waiter_membership_id=%s '
            'AND entered_at IS NOT NULL',
            (request_id, scope.waiter_ids[0]),
        )
        evidence_count = cursor.fetchone()['count']
    assert evidence_count == (1 if action_response.status_code == 200 else 0)
    assert _view(client, waiters[0], scope.location_id).json()['items'] == []
