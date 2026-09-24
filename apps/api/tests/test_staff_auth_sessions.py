from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from test_auth_foundation import PASSWORD, _seed_authority
from test_resource_foundation import (
    _grant_location,
    _location,
    _login,
    _organization,
    _resource,
    _seed_authority as _seed_location_authority,
)
from test_table_waiter_assignments import _assign, _waiter


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _token(client: TestClient, username: str, password: str = PASSWORD) -> str:
    response = client.post('/auth/login', json={
        'username': username, 'password': password,
    })
    assert response.status_code == 200, response.text
    return response.json()['access_token']


def _headers(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def _session_rows(connection, user_id: int):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT session_id,status,active_slot,closed_at '
            'FROM staff_auth_sessions WHERE user_id=%s ORDER BY id',
            (user_id,),
        )
        return cursor.fetchall()


def test_active_session_rejects_relogin_and_logout_allows_a_new_login(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)

    token_a = _token(client, authority.username)
    assert client.get('/auth/me', headers=_headers(token_a)).status_code == 200
    failed = client.post('/auth/login', json={
        'username': authority.username, 'password': 'wrong password',
    })
    assert failed.status_code == 401
    assert client.get('/auth/me', headers=_headers(token_a)).status_code == 200
    assert [row['status'] for row in _session_rows(connection, authority.user_id)] == [
        'ACTIVE'
    ]

    second_login = client.post('/auth/login', json={
        'username': authority.username, 'password': PASSWORD,
    })
    assert second_login.status_code == 409
    assert second_login.json()['error'] == {
        'code': 'staff_already_logged_in',
        'message': 'Staff already has an active session',
    }
    assert 'access_token' not in second_login.text
    assert client.get('/auth/me', headers=_headers(token_a)).status_code == 200
    rows = _session_rows(connection, authority.user_id)
    assert [row['status'] for row in rows] == ['ACTIVE']
    assert rows[0]['active_slot'] == 1
    assert rows[0]['closed_at'] is None

    logout = client.post('/auth/logout', headers=_headers(token_a))
    assert logout.status_code == 204
    assert client.get('/auth/me', headers=_headers(token_a)).status_code == 401
    token_b = _token(client, authority.username)
    assert token_b != token_a
    assert client.get('/auth/me', headers=_headers(token_b)).status_code == 200
    rows = _session_rows(connection, authority.user_id)
    assert [row['status'] for row in rows] == ['CLOSED', 'ACTIVE']
    assert [row['active_slot'] for row in rows] == [None, 1]


def test_different_staff_sessions_remain_independent(client, sql_connection) -> None:
    connection, prefix = sql_connection
    first = _seed_authority(connection, prefix)
    second = _seed_authority(connection, f'{prefix}-second')

    first_token = _token(client, first.username)
    second_token = _token(client, second.username)

    assert client.get('/auth/me', headers=_headers(first_token)).status_code == 200
    assert client.get('/auth/me', headers=_headers(second_token)).status_code == 200
    assert _session_rows(connection, first.user_id)[0]['status'] == 'ACTIVE'
    assert _session_rows(connection, second.user_id)[0]['status'] == 'ACTIVE'


def test_competing_logins_allow_exactly_one_current_session(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    barrier = Barrier(2)

    with (
        TestClient(create_app(settings=integration_settings)) as first_client,
        TestClient(create_app(settings=integration_settings)) as second_client,
    ):
        def login(candidate: TestClient):
            barrier.wait()
            return candidate.post('/auth/login', json={
                'username': authority.username, 'password': PASSWORD,
            })

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = [
                future.result()
                for future in (
                    pool.submit(login, first_client),
                    pool.submit(login, second_client),
                )
            ]

        assert sorted(response.status_code for response in responses) == [200, 409]
        successful = next(response for response in responses if response.status_code == 200)
        conflict = next(response for response in responses if response.status_code == 409)
        assert conflict.json()['error']['code'] == 'staff_already_logged_in'
        assert first_client.get(
            '/auth/me', headers=_headers(successful.json()['access_token']),
        ).status_code == 200

    rows = _session_rows(connection, authority.user_id)
    assert [row['status'] for row in rows] == ['ACTIVE']
    assert sum(row['active_slot'] == 1 for row in rows) == 1


def test_logout_and_relogin_preserve_table_waiter_assignment(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    actor = _seed_location_authority(
        connection, prefix, ('resource.read', 'resource.manage'),
    )
    organization_id = _organization(connection, actor.tenant_id, 'ORG')
    location_id = _location(connection, actor.tenant_id, organization_id, 'LOC')
    _grant_location(connection, actor, location_id)
    table_id = _resource(
        connection, actor.tenant_id, location_id, 'TABLE-AUTH', 'TABLE',
    )
    waiter_id = _waiter(
        connection, tenant_id=actor.tenant_id, location_id=location_id,
        prefix=prefix, label='preserved',
    )

    token_a = _login(client, actor)['Authorization'].partition('Bearer ')[2]
    assigned = _assign(client, _headers(token_a), location_id, table_id, waiter_id, 0)
    assert assigned.status_code == 201, assigned.text
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT tenant_id,location_id,table_resource_id,waiter_membership_id,'
            'is_responsible,created_at,updated_at FROM table_waiter_assignments '
            'WHERE table_resource_id=%s',
            (table_id,),
        )
        before = cursor.fetchone()

    assert client.post('/auth/logout', headers=_headers(token_a)).status_code == 204
    assert client.get('/auth/me', headers=_headers(token_a)).status_code == 401
    token_b = _login(client, actor)['Authorization'].partition('Bearer ')[2]
    me = client.get('/auth/me', headers=_headers(token_b))
    assert me.status_code == 200
    assert me.json()['authorized_location_ids'] == [location_id]
    assert client.get(
        f'/locations/{location_id}/tables/{table_id}/waiter-assignments',
        headers=_headers(token_b),
    ).status_code == 200
    assert client.get('/auth/me', headers=_headers(token_b)).status_code == 200

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT tenant_id,location_id,table_resource_id,waiter_membership_id,'
            'is_responsible,created_at,updated_at FROM table_waiter_assignments '
            'WHERE table_resource_id=%s',
            (table_id,),
        )
        assert cursor.fetchone() == before
