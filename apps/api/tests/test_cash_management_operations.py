from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from test_cash_session_foundation import (
    _authority,
    _headers,
    _organization_location,
    _permission,
    _resource,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _setup(connection, prefix: str, client: TestClient):
    authority = _authority(
        connection,
        prefix,
        (
            'resource.manage',
            'cash_session.manage',
            'cash_management.read',
            'cash_movement.manage',
        ),
    )
    _, location_id = _organization_location(connection, authority.tenant_id, 'OPS')
    headers = _headers(client, authority)
    register = _resource(client, headers, location_id, 'REGISTER')
    opened = client.post(
        f"/resources/{register['id']}/cash-sessions",
        headers={**headers, 'Idempotency-Key': 'open-1'},
        json={'currency': 'MXN'},
    )
    assert opened.status_code == 201, opened.text
    return authority, headers, register, opened.json()


def _movement(
    client: TestClient,
    headers: dict[str, str],
    session_id: int,
    key: str,
    movement_type: str,
    amount: str,
    reason: str | None = None,
    currency: str = 'MXN',
):
    return client.post(
        f'/cash-sessions/{session_id}/movements',
        headers={**headers, 'Idempotency-Key': key},
        json={
            'movement_type': movement_type,
            'amount': amount,
            'currency': currency,
            'reason': reason,
            'reference': f'ref-{key}',
        },
    )


def _count(
    client: TestClient,
    headers: dict[str, str],
    session_id: int,
    key: str,
    amount: str,
    currency: str = 'MXN',
):
    return client.post(
        f'/cash-sessions/{session_id}/counts',
        headers={**headers, 'Idempotency-Key': key},
        json={'counted_amount': amount, 'currency': currency},
    )


def _close(
    client: TestClient,
    headers: dict[str, str],
    session_id: int,
    key: str,
    count_id: int,
    reason: str | None = None,
):
    return client.post(
        f'/cash-sessions/{session_id}/close',
        headers={**headers, 'Idempotency-Key': key},
        json={'cash_count_id': count_id, 'variance_reason': reason},
    )


def _code(response) -> str:
    return response.json()['error']['code']


def test_manual_movements_validate_authorize_accumulate_and_are_idempotent(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    authority, headers, _, session = _setup(connection, prefix, client)
    session_id = session['id']

    _execute_without_permission = _authority(
        connection, f'{prefix}-limited', ('cash_session.manage',)
    )
    limited_headers = _headers(client, _execute_without_permission)
    assert _movement(
        client, limited_headers, session_id, 'forbidden', 'CASH_IN', '1', 'funds'
    ).status_code == 403

    accepted = (
        ('float', 'OPENING_FLOAT', '100.0000', None),
        ('in', 'CASH_IN', '20.1250', 'cash replenishment'),
        ('out', 'CASH_OUT', '-10.0250', 'petty cash'),
        ('withdraw', 'WITHDRAWAL', '-30.0000', 'safe drop'),
        ('adjust-plus', 'ADJUSTMENT', '0.0001', 'correction'),
        ('adjust-minus', 'ADJUSTMENT', '-0.0001', 'correction'),
    )
    created = []
    for key, kind, amount, reason in accepted:
        response = _movement(
            client, headers, session_id, key, kind, amount, reason
        )
        assert response.status_code == 201, response.text
        created.append(response.json())
    assert created[0]['actor_id'] == authority.membership_id
    assert created[0]['authorized_by_actor_id'] == authority.membership_id

    replay = _movement(
        client, headers, session_id, 'in', 'cash_in', '20.125',
        'cash replenishment',
    )
    assert replay.status_code == 200
    assert replay.json()['id'] == created[1]['id']
    conflict = _movement(
        client, headers, session_id, 'in', 'CASH_IN', '21',
        'cash replenishment',
    )
    assert conflict.status_code == 409
    assert _code(conflict) == 'CASH_MOVEMENT_IDEMPOTENCY_CONFLICT'

    invalid = (
        ('duplicate', 'OPENING_FLOAT', '1', None, 'MXN', 409),
        ('zero', 'ADJUSTMENT', '0', 'correction', 'MXN', 422),
        ('wrong-sign', 'CASH_OUT', '1', 'expense', 'MXN', 422),
        ('wrong-currency', 'CASH_IN', '1', 'funds', 'USD', 422),
        ('tender', 'CUSTOMER_TENDER', '1', 'customer', 'MXN', 422),
        ('change', 'CUSTOMER_CHANGE', '-1', 'customer', 'MXN', 422),
        ('missing-reason', 'CASH_IN', '1', None, 'MXN', 422),
    )
    for key, kind, amount, reason, currency, expected_status in invalid:
        response = _movement(
            client, headers, session_id, key, kind, amount, reason, currency
        )
        assert response.status_code == expected_status, response.text

    read = client.get(f'/cash-sessions/{session_id}', headers=headers)
    assert read.status_code == 200
    assert read.json()['movement_version'] == len(accepted)
    assert read.json()['expected_cash'] == '80.1000'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM cash_movements WHERE cash_session_id=%s',
            (session_id,),
        )
        assert cursor.fetchone()['count'] == len(accepted)


def test_counts_are_immutable_recounts_and_stale_fence_close(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    _, headers, _, session = _setup(connection, prefix, client)
    session_id = session['id']
    assert _movement(
        client, headers, session_id, 'float', 'OPENING_FLOAT', '50'
    ).status_code == 201

    first = _count(client, headers, session_id, 'count-1', '50.0000')
    replay = _count(client, headers, session_id, 'count-1', '50')
    second = _count(client, headers, session_id, 'count-2', '49.5000')
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()['id'] == first.json()['id']
    assert second.status_code == 201
    assert first.json()['captured_movement_version'] == 1
    assert second.json()['captured_movement_version'] == 1
    assert client.get(
        f'/cash-sessions/{session_id}', headers=headers
    ).json()['movement_version'] == 1
    changed = _count(client, headers, session_id, 'count-1', '49')
    assert changed.status_code == 409
    assert _code(changed) == 'CASH_COUNT_IDEMPOTENCY_CONFLICT'
    assert _count(client, headers, session_id, 'negative', '-1').status_code == 422
    assert _count(
        client, headers, session_id, 'currency', '50', 'USD'
    ).status_code == 422

    assert _movement(
        client, headers, session_id, 'later', 'CASH_IN', '10', 'replenishment'
    ).status_code == 201
    stale = _close(
        client, headers, session_id, 'stale-close', first.json()['id']
    )
    assert stale.status_code == 409
    assert _code(stale) == 'STALE_CASH_COUNT'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM cash_counts WHERE cash_session_id=%s',
            (session_id,),
        )
        assert cursor.fetchone()['count'] == 2


def test_close_freezes_variance_blocks_writes_and_allows_new_session(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    _, headers, register, session = _setup(connection, prefix, client)
    session_id = session['id']
    assert _movement(
        client, headers, session_id, 'float', 'OPENING_FLOAT', '100'
    ).status_code == 201
    count = _count(client, headers, session_id, 'count', '102.5000')
    assert count.status_code == 201
    missing_reason = _close(
        client, headers, session_id, 'close-missing', count.json()['id']
    )
    assert missing_reason.status_code == 422
    assert _code(missing_reason) == 'CASH_SESSION_VARIANCE_REASON_REQUIRED'

    assert client.patch(
        f"/resources/{register['id']}", headers=headers,
        json={'status': 'INACTIVE'},
    ).status_code == 200
    closed = _close(
        client, headers, session_id, 'close', count.json()['id'], 'drawer overage'
    )
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body['status'] == 'CLOSED'
    assert body['selected_cash_count_id'] == count.json()['id']
    assert body['final_movement_version'] == 1
    assert body['frozen_expected_cash'] == '100.0000'
    assert body['frozen_variance'] == '2.5000'
    assert body['variance_reason'] == 'drawer overage'
    assert body['closed_at'] is not None
    assert body['closed_by_actor_type'] == 'EMPLOYEE'

    replay = _close(
        client, headers, session_id, 'close', count.json()['id'], 'drawer overage'
    )
    assert replay.status_code == 200
    conflicting = _close(
        client, headers, session_id, 'other-close', count.json()['id'],
        'different reason',
    )
    assert conflicting.status_code == 409
    assert _code(conflicting) == 'CASH_SESSION_CLOSE_CONFLICT'
    assert _movement(
        client, headers, session_id, 'after-close', 'CASH_IN', '1', 'late'
    ).status_code == 409
    assert _count(
        client, headers, session_id, 'after-close', '102.5'
    ).status_code == 409
    cannot_open = client.post(
        f"/resources/{register['id']}/cash-sessions",
        headers={**headers, 'Idempotency-Key': 'inactive-open'},
        json={'currency': 'MXN'},
    )
    assert cannot_open.status_code == 409

    assert client.patch(
        f"/resources/{register['id']}", headers=headers,
        json={'status': 'ACTIVE'},
    ).status_code == 200
    reopened = client.post(
        f"/resources/{register['id']}/cash-sessions",
        headers={**headers, 'Idempotency-Key': 'open-2'},
        json={'currency': 'MXN'},
    )
    assert reopened.status_code == 201
    assert reopened.json()['id'] != session_id


def test_balanced_shortage_scope_and_cross_session_count_are_controlled(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    _, headers, register, first = _setup(connection, prefix, client)
    assert _movement(
        client, headers, first['id'], 'first-float', 'OPENING_FLOAT', '10'
    ).status_code == 201
    balanced_count = _count(client, headers, first['id'], 'balanced-count', '10')
    balanced = _close(
        client, headers, first['id'], 'balanced-close',
        balanced_count.json()['id'], 'ignored for balanced close',
    )
    assert balanced.status_code == 200
    assert balanced.json()['frozen_variance'] == '0.0000'
    assert balanced.json()['variance_reason'] is None

    second = client.post(
        f"/resources/{register['id']}/cash-sessions",
        headers={**headers, 'Idempotency-Key': 'open-second'},
        json={'currency': 'MXN'},
    ).json()
    wrong_count = _close(
        client, headers, second['id'], 'cross-count', balanced_count.json()['id']
    )
    assert wrong_count.status_code == 409
    assert _code(wrong_count) == 'CASH_COUNT_SESSION_CONFLICT'
    assert _movement(
        client, headers, second['id'], 'second-float', 'OPENING_FLOAT', '10'
    ).status_code == 201
    shortage_count = _count(client, headers, second['id'], 'short-count', '8.75')
    shortage = _close(
        client, headers, second['id'], 'short-close',
        shortage_count.json()['id'], 'drawer shortage',
    )
    assert shortage.status_code == 200
    assert shortage.json()['frozen_variance'] == '-1.2500'

    other = _authority(
        connection,
        f'{prefix}-other',
        ('cash_session.manage', 'cash_movement.manage', 'cash_management.read'),
    )
    other_headers = _headers(client, other)
    assert _movement(
        client, other_headers, second['id'], 'foreign', 'CASH_IN', '1', 'foreign'
    ).status_code == 404
    assert _count(
        client, other_headers, second['id'], 'foreign-count', '1'
    ).status_code == 404
