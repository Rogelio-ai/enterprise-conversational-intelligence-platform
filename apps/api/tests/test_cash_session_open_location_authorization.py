from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_cash_session_foundation import (
    _authority,
    _grant_location as _grant_authority_location,
    _headers,
    _organization_location,
    _resource,
)
from test_staff_check_query import (
    _grant_location as _grant_membership_location,
    _login,
    _membership,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _cash_counts(connection, tenant_id: int) -> tuple[int, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM cash_sessions WHERE tenant_id=%s',
            (tenant_id,),
        )
        sessions = int(cursor.fetchone()['count'])
        cursor.execute(
            'SELECT COUNT(*) AS count FROM cash_movements WHERE tenant_id=%s',
            (tenant_id,),
        )
        movements = int(cursor.fetchone()['count'])
    return sessions, movements


def test_cash_session_open_authorizes_location_before_creation_and_replay(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    owner = _authority(
        connection,
        prefix,
        ('resource.manage', 'cash_session.manage', 'cash_management.read'),
    )
    _, location_id = _organization_location(connection, owner.tenant_id, 'OPEN')
    _, other_location_id = _organization_location(
        connection, owner.tenant_id, 'MISMATCH'
    )
    _grant_authority_location(connection, owner, location_id)
    _grant_authority_location(connection, owner, other_location_id)
    owner_headers = _headers(client, owner)
    register = _resource(client, owner_headers, location_id, 'REGISTER')
    table = _resource(client, owner_headers, location_id, 'TABLE', 'TABLE')

    permission_email, _ = _membership(
        connection,
        tenant_id=owner.tenant_id,
        slug=f'{prefix}-open-permission-no-grant',
        permissions=('cash_session.manage',),
    )
    no_permission_email, no_permission_membership_id = _membership(
        connection,
        tenant_id=owner.tenant_id,
        slug=f'{prefix}-open-grant-no-permission',
        permissions=(),
    )
    _grant_membership_location(
        connection, owner.tenant_id, no_permission_membership_id, location_id
    )

    foreign = _authority(
        connection,
        f'{prefix}-foreign',
        ('resource.manage', 'cash_session.manage'),
    )
    _, foreign_location_id = _organization_location(
        connection, foreign.tenant_id, 'FOREIGN'
    )
    _grant_authority_location(connection, foreign, foreign_location_id)
    foreign_register = _resource(
        client,
        _headers(client, foreign),
        foreign_location_id,
        'FOREIGN-REGISTER',
    )

    url = f"/resources/{register['id']}/cash-sessions"
    payload = {'currency': 'MXN'}
    assert _cash_counts(connection, owner.tenant_id) == (0, 0)

    missing_location = client.post(
        url,
        headers={**owner_headers, 'Idempotency-Key': 'missing-location'},
        json=payload,
    )
    assert missing_location.status_code == 422, missing_location.text

    denied_cases = (
        (
            _login(client, permission_email),
            register['id'],
            location_id,
            404,
            'permission-no-grant',
        ),
        (
            _login(client, no_permission_email),
            register['id'],
            location_id,
            403,
            'grant-no-permission',
        ),
        (
            owner_headers,
            register['id'],
            other_location_id,
            404,
            'location-mismatch',
        ),
        (
            owner_headers,
            foreign_register['id'],
            location_id,
            404,
            'foreign-register',
        ),
    )
    for headers, resource_id, requested_location_id, status, key in denied_cases:
        denied = client.post(
            f'/resources/{resource_id}/cash-sessions',
            headers={**headers, 'Idempotency-Key': key},
            params={'location_id': requested_location_id},
            json=payload,
        )
        assert denied.status_code == status, denied.text
        assert 'expected_cash' not in denied.text
    assert _cash_counts(connection, owner.tenant_id) == (0, 0)

    invalid_type = client.post(
        f"/resources/{table['id']}/cash-sessions",
        headers={**owner_headers, 'Idempotency-Key': 'non-register'},
        params={'location_id': location_id},
        json=payload,
    )
    assert invalid_type.status_code == 409, invalid_type.text
    assert invalid_type.json()['error']['code'] == 'INVALID_CASH_REGISTER'
    assert _cash_counts(connection, owner.tenant_id) == (0, 0)

    open_headers = {**owner_headers, 'Idempotency-Key': 'authorized-open'}
    created = client.post(
        url,
        headers=open_headers,
        params={'location_id': location_id},
        json=payload,
    )
    assert created.status_code == 201, created.text
    assert created.json()['status'] == 'OPEN'
    assert created.json()['location_id'] == location_id
    assert created.json()['resource_id'] == register['id']

    replay = client.post(
        url,
        headers=open_headers,
        params={'location_id': location_id},
        json={'currency': 'mxn'},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()['id'] == created.json()['id']

    unauthorized_replay = client.post(
        url,
        headers=open_headers,
        params={'location_id': other_location_id},
        json=payload,
    )
    assert unauthorized_replay.status_code == 404, unauthorized_replay.text
    assert str(created.json()['id']) not in unauthorized_replay.text
    assert 'expected_cash' not in unauthorized_replay.text

    no_grant_replay = client.post(
        url,
        headers={
            **_login(client, permission_email),
            'Idempotency-Key': 'authorized-open',
        },
        params={'location_id': location_id},
        json=payload,
    )
    assert no_grant_replay.status_code == 404, no_grant_replay.text
    assert 'expected_cash' not in no_grant_replay.text

    duplicate = client.post(
        url,
        headers={**owner_headers, 'Idempotency-Key': 'duplicate-open'},
        params={'location_id': location_id},
        json=payload,
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()['error']['code'] == 'ACTIVE_CASH_SESSION_EXISTS'

    active = client.get(
        '/cash-sessions/active',
        headers=owner_headers,
        params={'location_id': location_id, 'resource_id': register['id']},
    )
    assert active.status_code == 200, active.text
    assert active.json()['id'] == created.json()['id']
    direct = client.get(
        f"/cash-sessions/{created.json()['id']}", headers=owner_headers
    )
    assert direct.status_code == 200, direct.text
    assert direct.json()['id'] == created.json()['id']
    assert _cash_counts(connection, owner.tenant_id) == (1, 0)
