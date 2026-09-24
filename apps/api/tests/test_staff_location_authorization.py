from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import pymysql
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.deps import AuthenticatedContext, require_staff_location_access
from app.core.security import hash_password
from app.main import create_app


PASSWORD = 'Test Password 123!'


@dataclass(frozen=True)
class Authority:
    tenant_id: int
    membership_id: int
    role_id: int
    email: str


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _tenant(connection, slug: str) -> int:
    return _execute(
        connection,
        "INSERT INTO tenants (name, slug, status) VALUES (%s, %s, 'ACTIVE')",
        (f'Tenant {slug}', slug),
    )


def _authority(
    connection,
    tenant_id: int,
    prefix: str,
    *,
    permissions: tuple[str, ...] = ('location.read', 'location.manage'),
) -> Authority:
    email = f'{prefix}@example.test'
    user_id = _execute(
        connection,
        "INSERT INTO users (username, email, password_hash, display_name, status) VALUES (%s,%s,%s,%s,'ACTIVE')",
        (prefix.casefold(), email, hash_password(PASSWORD), f'User {prefix}'),
    )
    membership_id = _execute(
        connection,
        "INSERT INTO tenant_memberships (tenant_id, user_id, status) VALUES (%s,%s,'ACTIVE')",
        (tenant_id, user_id),
    )
    role_id = _execute(
        connection,
        "INSERT INTO roles (tenant_id, name, description, status) VALUES (%s,%s,%s,'ACTIVE')",
        (tenant_id, f'ROLE_{prefix}', 'Location authorization test role'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id, membership_id, role_id) VALUES (%s,%s,%s)',
        (tenant_id, membership_id, role_id),
    )
    for code in permissions:
        _execute(
            connection,
            'INSERT IGNORE INTO permissions (code, description) VALUES (%s,%s)',
            (code, f'Permission {code}'),
        )
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
        _execute(
            connection,
            'INSERT INTO role_permissions (role_id, permission_id) VALUES (%s,%s)',
            (role_id, permission_id),
        )
    return Authority(tenant_id, membership_id, role_id, email)


def _organization(connection, tenant_id: int, code: str) -> int:
    return _execute(
        connection,
        "INSERT INTO organizations (tenant_id, code, name, status) VALUES (%s,%s,%s,'ACTIVE')",
        (tenant_id, code, f'Organization {code}'),
    )


def _location(connection, tenant_id: int, organization_id: int, code: str) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO locations (tenant_id, organization_id, code, name, timezone, status)
        VALUES (%s,%s,%s,%s,'America/Mexico_City','ACTIVE')
        ''',
        (tenant_id, organization_id, code, f'Location {code}'),
    )


def _grant(
    connection, authority: Authority, location_id: int, role_id: int | None = None,
) -> int:
    _execute(
        connection,
        'INSERT IGNORE INTO membership_location_grants '
        '(tenant_id, membership_id, location_id) VALUES (%s,%s,%s)',
        (authority.tenant_id, authority.membership_id, location_id),
    )
    return _execute(
        connection,
        'INSERT INTO membership_location_roles '
        '(tenant_id, membership_id, location_id, role_id) VALUES (%s,%s,%s,%s)',
        (
            authority.tenant_id, authority.membership_id, location_id,
            authority.role_id if role_id is None else role_id,
        ),
    )


def _role(connection, tenant_id: int, name: str, permission: str) -> int:
    role_id = _execute(
        connection,
        "INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,'ACTIVE')",
        (tenant_id, name, f'{name} scoped role'),
    )
    _execute(
        connection,
        'INSERT IGNORE INTO permissions (code,description) VALUES (%s,%s)',
        (permission, permission),
    )
    _execute(
        connection,
        'INSERT INTO role_permissions (role_id,permission_id) '
        'SELECT %s,id FROM permissions WHERE code=%s',
        (role_id, permission),
    )
    return role_id


def _login(client: TestClient, authority: Authority) -> dict[str, str]:
    response = client.post(
        '/auth/login',
        json={'username': authority.email.partition('@')[0], 'password': PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as test_client:
        yield test_client


def test_grants_support_one_or_many_locations_and_reject_duplicates_and_cross_tenant(
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_a = _tenant(connection, prefix)
    tenant_b = _tenant(connection, f'{prefix}-other')
    authority = _authority(connection, tenant_a, prefix)
    organization_a = _organization(connection, tenant_a, 'A')
    organization_b = _organization(connection, tenant_b, 'B')
    first = _location(connection, tenant_a, organization_a, 'ONE')
    second = _location(connection, tenant_a, organization_a, 'TWO')
    foreign = _location(connection, tenant_b, organization_b, 'FOREIGN')

    _grant(connection, authority, first)
    _grant(connection, authority, second)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT location_id FROM membership_location_grants '
            'WHERE membership_id=%s ORDER BY location_id',
            (authority.membership_id,),
        )
        assert [row['location_id'] for row in cursor.fetchall()] == [first, second]

    with pytest.raises(pymysql.err.IntegrityError):
        _grant(connection, authority, first)
    with pytest.raises(pymysql.err.IntegrityError):
        _grant(connection, authority, foreign)


def test_identity_location_list_and_detail_are_authoritatively_grant_scoped(
    client: TestClient,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_a = _tenant(connection, prefix)
    tenant_b = _tenant(connection, f'{prefix}-other')
    authority = _authority(connection, tenant_a, prefix)
    organization_a = _organization(connection, tenant_a, 'A')
    organization_b = _organization(connection, tenant_b, 'B')
    granted_one = _location(connection, tenant_a, organization_a, 'ONE')
    ungranted = _location(connection, tenant_a, organization_a, 'NONE')
    granted_two = _location(connection, tenant_a, organization_a, 'TWO')
    foreign = _location(connection, tenant_b, organization_b, 'FOREIGN')
    _grant(connection, authority, granted_two)
    _grant(connection, authority, granted_one)
    headers = _login(client, authority)

    me = client.get('/auth/me', headers=headers)
    listing = client.get('/locations', headers=headers)

    assert me.status_code == 200
    assert me.json()['authorized_location_ids'] == [granted_one, granted_two]
    assert [row['id'] for row in listing.json()['items']] == [granted_one, granted_two]
    assert client.get(f'/locations/{granted_one}', headers=headers).status_code == 200
    assert client.patch(
        f'/locations/{granted_one}', headers=headers, json={'name': 'Authorized update'}
    ).status_code == 200
    assert client.get(f'/locations/{ungranted}', headers=headers).status_code == 404
    assert client.patch(
        f'/locations/{ungranted}', headers=headers, json={'name': 'No access'}
    ).status_code == 404
    assert client.get(f'/locations/{foreign}', headers=headers).status_code == 404
    assert client.get(
        f'/locations/{ungranted}',
        headers={**headers, 'X-Location-ID': str(ungranted)},
    ).status_code == 404
    assert client.get(
        f'/locations/{foreign}',
        headers={**headers, 'X-Tenant-ID': str(tenant_b)},
    ).status_code == 403


def test_location_access_requires_both_permission_and_grant(
    client: TestClient,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_id = _tenant(connection, prefix)
    organization_id = _organization(connection, tenant_id, 'ORG')
    location_id = _location(connection, tenant_id, organization_id, 'LOC')
    permitted = _authority(connection, tenant_id, prefix, permissions=('location.read',))
    granted = _authority(connection, tenant_id, f'{prefix}-grant', permissions=())
    _grant(connection, granted, location_id)

    permitted_headers = _login(client, permitted)
    granted_headers = _login(client, granted)

    assert client.get(f'/locations/{location_id}', headers=permitted_headers).status_code == 404
    assert client.get(f'/locations/{location_id}', headers=granted_headers).status_code == 403


def test_location_creation_explicitly_grants_the_creator(
    client: TestClient,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_id = _tenant(connection, prefix)
    authority = _authority(connection, tenant_id, prefix)
    organization_id = _organization(connection, tenant_id, 'ORG')
    headers = _login(client, authority)

    response = client.post(
        '/locations',
        headers=headers,
        json={
            'organization_id': organization_id,
            'code': 'CREATED',
            'name': 'Created location',
            'timezone': 'America/Mexico_City',
        },
    )

    assert response.status_code == 201, response.text
    location_id = response.json()['id']
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT tenant_id FROM membership_location_grants '
            'WHERE membership_id=%s AND location_id=%s',
            (authority.membership_id, location_id),
        )
        assert cursor.fetchone()['tenant_id'] == tenant_id
    assert client.get(f'/locations/{location_id}', headers=headers).status_code == 200


def test_shared_location_dependency_is_reusable_by_future_staff_routes(
    integration_settings,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_id = _tenant(connection, prefix)
    authority = _authority(connection, tenant_id, prefix, permissions=())
    organization_id = _organization(connection, tenant_id, 'ORG')
    granted = _location(connection, tenant_id, organization_id, 'YES')
    denied = _location(connection, tenant_id, organization_id, 'NO')
    _grant(connection, authority, granted)
    app = create_app(settings=integration_settings)

    @app.get('/_proof/staff-locations/{location_id}')
    async def proof_route(
        context: Annotated[AuthenticatedContext, Depends(require_staff_location_access)],
    ) -> dict[str, int]:
        return {'membership_id': context.membership_id}

    with TestClient(app) as test_client:
        headers = _login(test_client, authority)
        allowed = test_client.get(f'/_proof/staff-locations/{granted}', headers=headers)
        denied_response = test_client.get(f'/_proof/staff-locations/{denied}', headers=headers)

    assert allowed.status_code == 200
    assert allowed.json() == {'membership_id': authority.membership_id}
    assert denied_response.status_code == 404


def test_roles_and_permissions_are_composed_only_within_the_assigned_location(
    client: TestClient,
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_id = _tenant(connection, prefix)
    organization_id = _organization(connection, tenant_id, 'ORG')
    location_a = _location(connection, tenant_id, organization_id, 'A')
    location_b = _location(connection, tenant_id, organization_id, 'B')
    staff = _authority(connection, tenant_id, prefix, permissions=())
    waiter_role = _role(connection, tenant_id, f'{prefix}-WAITER', 'restaurant_service.read')
    cashier_role = _role(connection, tenant_id, f'{prefix}-CASHIER', 'resource.read')
    _grant(connection, staff, location_a, waiter_role)
    _grant(connection, staff, location_b, cashier_role)
    headers = _login(client, staff)

    waiter_a = client.get(
        f'/locations/{location_a}/restaurant-service-sessions/999999/responsibility',
        headers=headers,
    )
    waiter_b = client.get(
        f'/locations/{location_b}/restaurant-service-sessions/999999/responsibility',
        headers=headers,
    )
    cashier_a = client.get(
        f'/locations/{location_a}/tables/eligible-waiters', headers=headers,
    )
    cashier_b = client.get(
        f'/locations/{location_b}/tables/eligible-waiters', headers=headers,
    )
    me = client.get('/auth/me', headers=headers)

    assert waiter_a.status_code == 404
    assert waiter_b.status_code == 403
    assert cashier_a.status_code == 403
    assert cashier_b.status_code == 200
    assert me.status_code == 200
    assert me.json()['location_authorities'] == [
        {
            'location_id': location_a,
            'roles': [f'{prefix}-WAITER'],
            'permissions': ['restaurant_service.read'],
        },
        {
            'location_id': location_b,
            'roles': [f'{prefix}-CASHIER'],
            'permissions': ['resource.read'],
        },
    ]

    second_waiter_role = _role(
        connection, tenant_id, f'{prefix}-WAITER-READ', 'location.read',
    )
    _grant(connection, staff, location_a, second_waiter_role)
    refreshed_headers = _login(client, staff)
    assert client.get(f'/locations/{location_a}', headers=refreshed_headers).status_code == 200
    assert client.get(f'/locations/{location_b}', headers=refreshed_headers).status_code == 403
    listing = client.get('/locations', headers=refreshed_headers)
    assert listing.status_code == 200
    assert [item['id'] for item in listing.json()['items']] == [location_a]


def test_location_role_assignment_rejects_cross_tenant_and_duplicate_scope(
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    tenant_a = _tenant(connection, prefix)
    tenant_b = _tenant(connection, f'{prefix}-foreign')
    organization_a = _organization(connection, tenant_a, 'A')
    organization_b = _organization(connection, tenant_b, 'B')
    location_a = _location(connection, tenant_a, organization_a, 'A')
    location_b = _location(connection, tenant_b, organization_b, 'B')
    staff = _authority(connection, tenant_a, prefix, permissions=())
    role_a = _role(connection, tenant_a, f'{prefix}-A', 'location.read')
    role_b = _role(connection, tenant_b, f'{prefix}-B', 'resource.read')
    _grant(connection, staff, location_a, role_a)

    with pytest.raises(pymysql.err.IntegrityError):
        _grant(connection, staff, location_a, role_a)
    with pytest.raises(pymysql.err.IntegrityError):
        _grant(connection, staff, location_b, role_a)
    with pytest.raises(pymysql.err.IntegrityError):
        _grant(connection, staff, location_a, role_b)
    with pytest.raises(pymysql.err.IntegrityError):
        _execute(
            connection,
            'INSERT INTO membership_location_roles '
            '(tenant_id,membership_id,location_id,role_id) VALUES (%s,%s,%s,%s)',
            (tenant_b, staff.membership_id, location_a, role_b),
        )
