from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pymysql
import pytest
from fastapi.testclient import TestClient

from app.bootstrap_admin import BootstrapInput, bootstrap_admin
from app.core.security import hash_password
from app.main import create_app


PASSWORD = 'Test Password 123!'


@dataclass(frozen=True)
class SeededAuthority:
    tenant_id: int
    user_id: int
    membership_id: int
    role_id: int
    email: str


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _seed_authority(
    connection,
    prefix: str,
    *,
    permission: str | None = 'tenant.read',
    user_status: str = 'ACTIVE',
    tenant_status: str = 'ACTIVE',
    membership_status: str = 'ACTIVE',
) -> SeededAuthority:
    tenant_id = _execute(
        connection,
        'INSERT INTO tenants (name, slug, status) VALUES (%s, %s, %s)',
        ('Test Tenant', prefix, tenant_status),
    )
    email = f'{prefix}@example.test'
    user_id = _execute(
        connection,
        'INSERT INTO users (email, password_hash, display_name, status) VALUES (%s, %s, %s, %s)',
        (email, hash_password(PASSWORD), 'Test User', user_status),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id, user_id, status) VALUES (%s, %s, %s)',
        (tenant_id, user_id, membership_status),
    )
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id, name, description, status) VALUES (%s, %s, %s, %s)',
        (tenant_id, 'TEST_ROLE', 'Test role', 'ACTIVE'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id, membership_id, role_id) VALUES (%s, %s, %s)',
        (tenant_id, membership_id, role_id),
    )
    if permission:
        _assign_permission(connection, role_id, permission)
    return SeededAuthority(tenant_id, user_id, membership_id, role_id, email)


def _assign_permission(connection, role_id: int, code: str) -> None:
    _execute(
        connection,
        'INSERT IGNORE INTO permissions (code, description) VALUES (%s, %s)',
        (code, f'Permission {code}'),
    )
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM permissions WHERE code = %s', (code,))
        permission_id = int(cursor.fetchone()['id'])
    _execute(
        connection,
        'INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
        (role_id, permission_id),
    )


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as test_client:
        yield test_client


def _login(client: TestClient, authority: SeededAuthority, **extra) -> str:
    response = client.post(
        '/auth/login',
        json={'email': authority.email, 'password': PASSWORD, **extra},
    )
    assert response.status_code == 200, response.text
    return response.json()['access_token']


def test_unique_tenant_slug_user_email_and_membership(sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    with pytest.raises(pymysql.err.IntegrityError):
        _execute(connection, 'INSERT INTO tenants (name, slug, status) VALUES (%s, %s, %s)', ('Duplicate', prefix, 'ACTIVE'))
    with pytest.raises(pymysql.err.IntegrityError):
        _execute(
            connection,
            'INSERT INTO users (email, password_hash, display_name, status) VALUES (%s, %s, %s, %s)',
            (authority.email, hash_password(PASSWORD), 'Duplicate', 'ACTIVE'),
        )
    with pytest.raises(pymysql.err.IntegrityError):
        _execute(
            connection,
            'INSERT INTO tenant_memberships (tenant_id, user_id, status) VALUES (%s, %s, %s)',
            (authority.tenant_id, authority.user_id, 'ACTIVE'),
        )


def test_cross_tenant_role_assignment_is_rejected_by_database(sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    other_tenant_id = _execute(
        connection,
        'INSERT INTO tenants (name, slug, status) VALUES (%s, %s, %s)',
        ('Other Tenant', f'{prefix}-other', 'ACTIVE'),
    )
    other_role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id, name, description, status) VALUES (%s, %s, %s, %s)',
        (other_tenant_id, 'OTHER_ROLE', 'Other role', 'ACTIVE'),
    )
    with pytest.raises(pymysql.err.IntegrityError):
        _execute(
            connection,
            'INSERT INTO membership_roles (tenant_id, membership_id, role_id) VALUES (%s, %s, %s)',
            (authority.tenant_id, authority.membership_id, other_role_id),
        )


def test_successful_login_and_authenticated_me(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    token = _login(client, authority)

    response = client.get('/auth/me', headers={'Authorization': f'Bearer {token}'})

    assert response.status_code == 200
    assert response.json() == {
        'user_id': authority.user_id,
        'email': authority.email,
        'display_name': 'Test User',
        'tenant_id': authority.tenant_id,
        'membership_id': authority.membership_id,
        'roles': ['TEST_ROLE'],
        'permissions': ['tenant.read'],
    }


@pytest.mark.parametrize(
    ('email_kind', 'password'),
    [('known', 'incorrect password'), ('unknown', PASSWORD)],
)
def test_invalid_credentials_are_generic(client, sql_connection, email_kind, password) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    email = authority.email if email_kind == 'known' else f'{prefix}-unknown@example.test'

    response = client.post('/auth/login', json={'email': email, 'password': password})

    assert response.status_code == 401
    assert 'Invalid authentication credentials' in response.text
    assert authority.email not in response.text


def test_disabled_user_cannot_login(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix, user_status='DISABLED')

    response = client.post('/auth/login', json={'email': authority.email, 'password': PASSWORD})

    assert response.status_code == 401


def test_auth_me_requires_valid_token(client) -> None:
    assert client.get('/auth/me').status_code == 401
    assert client.get('/auth/me', headers={'Authorization': 'Bearer invalid'}).status_code == 401


def test_single_tenant_is_inferred_and_multiple_tenants_require_selection(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    first = client.post('/auth/login', json={'email': authority.email, 'password': PASSWORD})
    assert first.status_code == 200
    assert first.json()['tenant']['id'] == authority.tenant_id

    other_tenant_id = _execute(
        connection,
        'INSERT INTO tenants (name, slug, status) VALUES (%s, %s, %s)',
        ('Other Tenant', f'{prefix}-other', 'ACTIVE'),
    )
    _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id, user_id, status) VALUES (%s, %s, %s)',
        (other_tenant_id, authority.user_id, 'ACTIVE'),
    )
    ambiguous = client.post('/auth/login', json={'email': authority.email, 'password': PASSWORD})
    selected = client.post(
        '/auth/login',
        json={'email': authority.email, 'password': PASSWORD, 'tenant_id': authority.tenant_id},
    )

    assert ambiguous.status_code == 400
    assert selected.status_code == 200
    assert selected.json()['tenant']['id'] == authority.tenant_id


def test_unauthorized_tenant_selection_and_cross_tenant_token_are_denied(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    other_tenant_id = _execute(
        connection,
        'INSERT INTO tenants (name, slug, status) VALUES (%s, %s, %s)',
        ('Tenant B', f'{prefix}-b', 'ACTIVE'),
    )
    token = _login(client, authority)

    response = client.get(
        '/tenants/current',
        headers={'Authorization': f'Bearer {token}', 'X-Tenant-ID': str(other_tenant_id)},
    )

    assert response.status_code == 403


def test_current_tenant_permission_denied_then_allowed(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix, permission=None)
    token = _login(client, authority)
    headers = {'Authorization': f'Bearer {token}'}

    assert client.get('/tenants/current', headers=headers).status_code == 403
    _assign_permission(connection, authority.role_id, 'tenant.read')
    response = client.get('/tenants/current', headers=headers)

    assert response.status_code == 200
    assert response.json()['id'] == authority.tenant_id


def test_inactive_membership_blocks_an_existing_token(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    token = _login(client, authority)
    _execute(
        connection,
        'UPDATE tenant_memberships SET status = %s WHERE id = %s',
        ('INACTIVE', authority.membership_id),
    )

    assert client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code == 403


def test_inactive_tenant_blocks_an_existing_token(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    token = _login(client, authority)
    _execute(
        connection,
        'UPDATE tenants SET status = %s WHERE id = %s',
        ('SUSPENDED', authority.tenant_id),
    )

    assert client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code == 403


def test_disabled_user_blocks_an_existing_token(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    token = _login(client, authority)
    _execute(connection, 'UPDATE users SET status = %s WHERE id = %s', ('DISABLED', authority.user_id))

    assert client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code == 401


def test_bootstrap_is_idempotent(integration_settings, sql_connection) -> None:
    connection, prefix = sql_connection
    values = BootstrapInput(
        tenant_name='Bootstrap Tenant',
        tenant_slug=f'{prefix}-bootstrap',
        admin_email=f'{prefix}-bootstrap@example.test',
        admin_password=PASSWORD,
        admin_display_name='Bootstrap Admin',
    )

    first = asyncio.run(bootstrap_admin(settings=integration_settings, values=values))
    second = asyncio.run(bootstrap_admin(settings=integration_settings, values=values))

    assert first.created
    assert second.created == ()
    assert first.tenant_id == second.tenant_id
    assert first.user_id == second.user_id
    assert first.membership_id == second.membership_id
    assert first.role_id == second.role_id
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT P.code
            FROM role_permissions AS RP
            JOIN permissions AS P ON P.id = RP.permission_id
            WHERE RP.role_id = %s
              AND P.code IN (
                  'organization.read', 'organization.manage',
                  'location.read', 'location.manage',
                  'resource.read', 'resource.manage',
                  'customer.read', 'customer.manage',
                  'product.read', 'product.manage',
                  'menu.read', 'menu.manage',
                  'pricing.read', 'pricing.manage',
                  'promotion.read', 'promotion.manage',
                  'conversation.read', 'conversation.manage',
                  'order_draft.read', 'order_draft.manage'
              )
            ORDER BY P.code
            ''',
            (first.role_id,),
        )
        assert [row['code'] for row in cursor.fetchall()] == [
            'conversation.manage',
            'conversation.read',
            'customer.manage',
            'customer.read',
            'location.manage',
            'location.read',
            'menu.manage',
            'menu.read',
            'order_draft.manage',
            'order_draft.read',
            'organization.manage',
            'organization.read',
            'pricing.manage',
            'pricing.read',
            'product.manage',
            'product.read',
            'promotion.manage',
            'promotion.read',
            'resource.manage',
            'resource.read',
        ]
