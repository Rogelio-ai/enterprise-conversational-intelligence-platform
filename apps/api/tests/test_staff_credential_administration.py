from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap_pilot_minimum import OPERATIONAL_PROFILE_PERMISSIONS
from app.core.security import hash_password, verify_password
from app.identity.credential_administration import PERMISSION
from app.main import create_app
from test_auth_foundation import PASSWORD, _execute, _seed_authority


NEW_PASSWORD = 'Changed Password 2026!'


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _staff(
    connection, authority, prefix: str, label: str, *, status: str = 'ACTIVE',
) -> tuple[int, int, str]:
    username = f'{prefix}-{label}'.casefold()
    user_id = _execute(
        connection,
        'INSERT INTO users (username,email,password_hash,display_name,status) '
        'VALUES (%s,%s,%s,%s,%s)',
        (
            username, f'{username}@example.test', hash_password(PASSWORD),
            f'Staff {label}', status,
        ),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,%s)',
        (authority.tenant_id, user_id, 'ACTIVE'),
    )
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,%s)',
        (authority.tenant_id, f'{prefix}-{label}-ROLE', 'Credential test Staff', 'ACTIVE'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',
        (authority.tenant_id, membership_id, role_id),
    )
    return user_id, membership_id, username


def _login(client: TestClient, username: str, password: str = PASSWORD):
    return client.post('/auth/login', json={
        'username': username, 'password': password,
    })


def _headers(response) -> dict[str, str]:
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _active_sessions(connection, user_id: int) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS amount FROM staff_auth_sessions '
            "WHERE user_id=%s AND status='ACTIVE' AND active_slot=1",
            (user_id,),
        )
        return int(cursor.fetchone()['amount'])


def _password_hash(connection, user_id: int) -> str:
    with connection.cursor() as cursor:
        cursor.execute('SELECT password_hash FROM users WHERE id=%s', (user_id,))
        return str(cursor.fetchone()['password_hash'])


def test_authorized_change_revokes_target_only_and_requires_new_password(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    admin = _seed_authority(connection, prefix, permission=PERMISSION)
    target_user_id, target_membership_id, target_username = _staff(
        connection, admin, prefix, 'target',
    )
    other_user_id, _, other_username = _staff(
        connection, admin, prefix, 'other',
    )
    admin_login = _login(client, admin.username)
    target_login = _login(client, target_username)
    other_login = _login(client, other_username)

    changed = client.put(
        f'/identity/staff/{target_membership_id}/password',
        headers=_headers(admin_login), json={'new_password': NEW_PASSWORD},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json() == {
        'target_membership_id': target_membership_id,
        'status': 'CHANGED',
        'sessions_revoked': 1,
    }
    assert 'password' not in changed.text.casefold()
    assert client.get('/auth/me', headers=_headers(target_login)).status_code == 401
    assert client.get('/auth/me', headers=_headers(other_login)).status_code == 200
    assert client.get('/auth/me', headers=_headers(admin_login)).status_code == 200
    assert _active_sessions(connection, target_user_id) == 0
    assert _active_sessions(connection, other_user_id) == 1
    assert _login(client, target_username).status_code == 401

    new_login = _login(client, target_username, NEW_PASSWORD)
    assert new_login.status_code == 200, new_login.text
    assert client.post('/auth/logout', headers=_headers(new_login)).status_code == 204
    assert client.post('/auth/logout', headers=_headers(other_login)).status_code == 204


def test_tenant_isolation_role_authorization_and_inactive_target(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    admin = _seed_authority(connection, prefix, permission=PERMISSION)
    target_user_id, target_membership_id, _ = _staff(
        connection, admin, prefix, 'target',
    )
    host_user_id, host_membership_id, host_username = _staff(
        connection, admin, prefix, 'host',
    )
    waiter_user_id, waiter_membership_id, waiter_username = _staff(
        connection, admin, prefix, 'waiter',
    )
    other = _seed_authority(connection, f'{prefix}-other', permission=None)
    admin_login = _login(client, admin.username)
    host_login = _login(client, host_username)
    waiter_login = _login(client, waiter_username)
    original_hash = _password_hash(connection, target_user_id)

    cross_tenant = client.put(
        f'/identity/staff/{other.membership_id}/password',
        headers=_headers(admin_login), json={'new_password': NEW_PASSWORD},
    )
    assert cross_tenant.status_code == 404
    assert _password_hash(connection, other.user_id) != hash_password(NEW_PASSWORD)

    for login, membership_id in (
        (host_login, target_membership_id),
        (waiter_login, target_membership_id),
    ):
        denied = client.put(
            f'/identity/staff/{membership_id}/password',
            headers=_headers(login), json={'new_password': NEW_PASSWORD},
        )
        assert denied.status_code == 403
    assert _password_hash(connection, target_user_id) == original_hash
    assert _active_sessions(connection, host_user_id) == 1
    assert _active_sessions(connection, waiter_user_id) == 1

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET status='DISABLED' WHERE id=%s", (target_user_id,),
        )
    invalid = client.put(
        f'/identity/staff/{target_membership_id}/password',
        headers=_headers(admin_login), json={'new_password': NEW_PASSWORD},
    )
    assert invalid.status_code == 409
    assert _password_hash(connection, target_user_id) == original_hash

    assert PERMISSION not in {
        code for codes in OPERATIONAL_PROFILE_PERMISSIONS.values() for code in codes
    }
    del host_membership_id, waiter_membership_id


def test_password_policy_and_commit_failure_preserve_credential_and_session(
    client, sql_connection, monkeypatch,
) -> None:
    connection, prefix = sql_connection
    admin = _seed_authority(connection, prefix, permission=PERMISSION)
    target_user_id, target_membership_id, target_username = _staff(
        connection, admin, prefix, 'target',
    )
    admin_login = _login(client, admin.username)
    target_login = _login(client, target_username)
    original_hash = _password_hash(connection, target_user_id)

    policy = client.put(
        f'/identity/staff/{target_membership_id}/password',
        headers=_headers(admin_login), json={'new_password': 'short'},
    )
    assert policy.status_code == 422
    assert _password_hash(connection, target_user_id) == original_hash
    assert client.get('/auth/me', headers=_headers(target_login)).status_code == 200
    assert _active_sessions(connection, target_user_id) == 1

    async def fail_commit(_session):
        raise RuntimeError('simulated commit failure')

    monkeypatch.setattr(AsyncSession, 'commit', fail_commit)
    failed = client.put(
        f'/identity/staff/{target_membership_id}/password',
        headers=_headers(admin_login), json={'new_password': NEW_PASSWORD},
    )
    assert failed.status_code == 500
    assert _password_hash(connection, target_user_id) == original_hash
    assert client.get('/auth/me', headers=_headers(target_login)).status_code == 200
    assert _active_sessions(connection, target_user_id) == 1


def test_concurrent_old_password_login_cannot_survive_password_change(
    integration_settings, sql_connection,
) -> None:
    connection, prefix = sql_connection
    admin = _seed_authority(connection, prefix, permission=PERMISSION)
    target_user_id, target_membership_id, target_username = _staff(
        connection, admin, prefix, 'target',
    )
    barrier = Barrier(2)
    with (
        TestClient(create_app(settings=integration_settings)) as admin_client,
        TestClient(create_app(settings=integration_settings)) as login_client,
    ):
        admin_login = _login(admin_client, admin.username)

        def reset_password():
            barrier.wait()
            return admin_client.put(
                f'/identity/staff/{target_membership_id}/password',
                headers=_headers(admin_login), json={'new_password': NEW_PASSWORD},
            )

        def old_login():
            barrier.wait()
            return _login(login_client, target_username)

        with ThreadPoolExecutor(max_workers=2) as pool:
            reset_response, login_response = (
                future.result() for future in (
                    pool.submit(reset_password), pool.submit(old_login),
                )
            )
        assert reset_response.status_code == 200, reset_response.text
        assert login_response.status_code in {200, 401}
        if login_response.status_code == 200:
            assert login_client.get(
                '/auth/me', headers=_headers(login_response),
            ).status_code == 401
        assert _active_sessions(connection, target_user_id) == 0
        assert _login(login_client, target_username).status_code == 401
        new_login = _login(login_client, target_username, NEW_PASSWORD)
        assert new_login.status_code == 200
