from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from test_cash_session_foundation import (
    Authority,
    _authority,
    _grant_location,
    _headers,
    _organization_location,
    _resource,
)
from test_staff_check_query import _login, _membership


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def test_location_filtered_resource_discovery_is_authorized_and_resumes_cash_session(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    owner = _authority(
        connection,
        prefix,
        (
            'resource.read',
            'resource.manage',
            'cash_session.manage',
            'cash_management.read',
        ),
    )
    _, location_id = _organization_location(connection, owner.tenant_id, 'GRANTED')
    _, other_location_id = _organization_location(
        connection, owner.tenant_id, 'UNGRANTED'
    )
    _grant_location(connection, owner, location_id)
    headers = _headers(client, owner)
    register = _resource(client, headers, location_id, 'REGISTER')
    _resource(client, headers, location_id, 'TABLE', 'TABLE')
    inactive_register = _resource(client, headers, location_id, 'INACTIVE-REGISTER')
    assert client.patch(
        f"/resources/{inactive_register['id']}",
        headers=headers,
        json={'status': 'INACTIVE'},
    ).status_code == 200
    other_register = _resource(
        client, headers, other_location_id, 'OTHER-REGISTER'
    )
    opened = client.post(
        f"/resources/{register['id']}/cash-sessions",
        headers={**headers, 'Idempotency-Key': 'resource-discovery-open'},
        json={'currency': 'MXN'},
    )
    assert opened.status_code == 201, opened.text

    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM resources')
        resource_count = cursor.fetchone()['count']
        cursor.execute('SELECT COUNT(*) AS count FROM cash_sessions')
        cash_session_count = cursor.fetchone()['count']

    params = {
        'location_id': location_id,
        'resource_type': 'CASH_REGISTER',
        'status': 'ACTIVE',
    }
    first = client.get('/resources', headers=headers, params=params)
    repeated = client.get('/resources', headers=headers, params=params)
    assert first.status_code == 200, first.text
    assert repeated.json() == first.json()
    assert [value['id'] for value in first.json()['items']] == [register['id']]
    assert all(value['location_id'] == location_id for value in first.json()['items'])
    assert inactive_register['id'] not in {
        value['id'] for value in first.json()['items']
    }
    assert other_register['id'] not in {value['id'] for value in first.json()['items']}

    active = client.get(
        '/cash-sessions/active',
        headers=headers,
        params={'location_id': location_id, 'resource_id': register['id']},
    )
    assert active.status_code == 200, active.text
    assert active.json()['id'] == opened.json()['id']
    assert active.json()['resource_id'] == register['id']

    permission_email, _ = _membership(
        connection,
        tenant_id=owner.tenant_id,
        slug=f'{prefix}-permission-no-grant',
        permissions=('resource.read',),
    )
    no_permission_email, no_permission_membership_id = _membership(
        connection,
        tenant_id=owner.tenant_id,
        slug=f'{prefix}-grant-no-permission',
        permissions=(),
    )
    _grant_location(
        connection,
        Authority(
            owner.tenant_id,
            no_permission_membership_id,
            owner.role_id,
            no_permission_email,
        ),
        location_id,
    )
    foreign = _authority(
        connection, f'{prefix}-foreign', ('resource.read',)
    )
    _, foreign_location_id = _organization_location(
        connection, foreign.tenant_id, 'FOREIGN'
    )
    _grant_location(connection, foreign, foreign_location_id)

    denied_cases = (
        (_login(client, permission_email), 404),
        (_login(client, no_permission_email), 403),
        (_headers(client, foreign), 404),
    )
    for denied_headers, expected_status in denied_cases:
        denied = client.get('/resources', headers=denied_headers, params=params)
        assert denied.status_code == expected_status, denied.text
        for protected_value in (
            str(register['id']),
            register['code'],
            register['name'],
        ):
            assert protected_value not in denied.text

    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM resources')
        assert cursor.fetchone()['count'] == resource_count
        cursor.execute('SELECT COUNT(*) AS count FROM cash_sessions')
        assert cursor.fetchone()['count'] == cash_session_count
