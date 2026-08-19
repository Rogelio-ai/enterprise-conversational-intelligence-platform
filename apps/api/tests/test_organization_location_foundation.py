from __future__ import annotations

from dataclasses import dataclass

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.routes.locations import _is_duplicate_code_error as is_location_code_conflict
from app.api.routes.locations import validate_timezone
from app.api.routes.organizations import _is_duplicate_code_error as is_organization_code_conflict
from app.core.security import hash_password
from app.main import create_app


PASSWORD = 'Test Password 123!'
WS_02_PERMISSIONS = (
    'organization.read',
    'organization.manage',
    'location.read',
    'location.manage',
)


@dataclass(frozen=True)
class Authority:
    tenant_id: int
    role_id: int
    email: str


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


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


def _seed_authority(connection, slug: str, permissions=WS_02_PERMISSIONS) -> Authority:
    tenant_id = _execute(
        connection,
        'INSERT INTO tenants (name, slug, status) VALUES (%s, %s, %s)',
        ('Test Tenant', slug, 'ACTIVE'),
    )
    email = f'{slug}@example.test'
    user_id = _execute(
        connection,
        'INSERT INTO users (email, password_hash, display_name, status) VALUES (%s, %s, %s, %s)',
        (email, hash_password(PASSWORD), 'Test User', 'ACTIVE'),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id, user_id, status) VALUES (%s, %s, %s)',
        (tenant_id, user_id, 'ACTIVE'),
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
    for permission in permissions:
        _assign_permission(connection, role_id, permission)
    return Authority(tenant_id=tenant_id, role_id=role_id, email=email)


def _login(client: TestClient, authority: Authority) -> dict[str, str]:
    response = client.post(
        '/auth/login',
        json={'email': authority.email, 'password': PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _organization(connection, tenant_id: int, code: str, status: str = 'ACTIVE') -> int:
    return _execute(
        connection,
        'INSERT INTO organizations (tenant_id, code, name, status) VALUES (%s, %s, %s, %s)',
        (tenant_id, code, f'Organization {code}', status),
    )


def _location(connection, tenant_id: int, organization_id: int, code: str) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO locations (tenant_id, organization_id, code, name, timezone, status)
        VALUES (%s, %s, %s, %s, 'America/Mexico_City', 'ACTIVE')
        ''',
        (tenant_id, organization_id, code, f'Location {code}'),
    )


def _integrity_error(message: str, code: int = 1062) -> IntegrityError:
    return IntegrityError(None, None, pymysql.err.IntegrityError(code, message))


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as test_client:
        yield test_client


def test_organization_api_auth_permission_cardinality_and_no_delete(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix, permissions=())
    headers = _login(client, authority)

    assert client.get('/organizations').status_code == 401
    assert client.post('/organizations', headers=headers, json={'code': 'ONE', 'name': 'One'}).status_code == 403
    assert client.delete('/organizations/1', headers=headers).status_code == 405

    _assign_permission(connection, authority.role_id, 'organization.read')
    _assign_permission(connection, authority.role_id, 'organization.manage')
    first = client.post('/organizations', headers=headers, json={'code': ' one ', 'name': ' One '})
    second = client.post('/organizations', headers=headers, json={'code': 'TWO', 'name': 'Two'})

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()['tenant_id'] == authority.tenant_id
    assert first.json()['code'] == 'ONE'
    assert first.json()['name'] == 'One'
    assert first.json()['status'] == 'ACTIVE'
    listing = client.get('/organizations', headers=headers)
    assert [item['id'] for item in listing.json()['items']] == [first.json()['id'], second.json()['id']]


def test_organization_uniqueness_isolation_patch_and_validation(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    other = _seed_authority(connection, f'{prefix}-other')
    headers = _login(client, authority)
    created = client.post('/organizations', headers=headers, json={'code': 'ROOT', 'name': 'Root'})
    organization_id = created.json()['id']

    duplicate = client.post('/organizations', headers=headers, json={'code': 'root', 'name': 'Duplicate'})
    assert duplicate.status_code == 409
    _organization(connection, other.tenant_id, 'ROOT')
    foreign_id = _organization(connection, other.tenant_id, 'FOREIGN')
    assert client.get(f'/organizations/{foreign_id}', headers=headers).status_code == 404
    assert client.patch(f'/organizations/{foreign_id}', headers=headers, json={'name': 'No'}).status_code == 404
    assert all(item['tenant_id'] == authority.tenant_id for item in client.get('/organizations', headers=headers).json()['items'])

    updated = client.patch(
        f'/organizations/{organization_id}',
        headers=headers,
        json={'code': 'new-code', 'name': ' Updated ', 'status': 'INACTIVE'},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()['code'] == 'NEW-CODE'
    assert updated.json()['name'] == 'Updated'
    assert updated.json()['status'] == 'INACTIVE'
    assert client.get(f'/organizations/{organization_id}', headers=headers).status_code == 200
    assert client.patch(f'/organizations/{organization_id}', headers=headers, json={}).status_code == 422
    assert client.patch(f'/organizations/{organization_id}', headers=headers, json={'status': 'SUSPENDED'}).status_code == 422
    assert client.post('/organizations', headers=headers, json={'tenant_id': other.tenant_id, 'code': 'X', 'name': 'X'}).status_code == 422


def test_organization_duplicate_classification_is_constraint_specific() -> None:
    assert is_organization_code_conflict(
        _integrity_error(
            "Duplicate entry '1-ROOT' for key 'organizations.uq_organizations_tenant_code'"
        )
    )
    assert is_organization_code_conflict(
        _integrity_error("Duplicate entry '1-ROOT' for key 'uq_organizations_tenant_code'")
    )
    assert not is_organization_code_conflict(
        _integrity_error("Duplicate entry '1-ROOT' for key 'uq_organizations_id_tenant'")
    )
    assert not is_organization_code_conflict(
        _integrity_error('Cannot add or update a child row', code=1452)
    )


def test_location_api_crud_cardinality_uniqueness_and_optional_fields(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    headers = _login(client, authority)
    organization_id = _organization(connection, authority.tenant_id, 'ORG')
    other_organization_id = _organization(connection, authority.tenant_id, 'ORG2')
    payload = {
        'organization_id': organization_id,
        'code': ' centro ',
        'name': ' Centro ',
        'timezone': 'America/Mexico_City',
        'address_line1': ' Main Street 1 ',
        'country_code': 'mx',
        'email': ' BRANCH@EXAMPLE.TEST ',
    }

    first = client.post('/locations', headers=headers, json=payload)
    second = client.post('/locations', headers=headers, json={**payload, 'code': 'NORTE', 'name': 'Norte'})
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()['tenant_id'] == authority.tenant_id
    assert first.json()['code'] == 'CENTRO'
    assert first.json()['name'] == 'Centro'
    assert first.json()['country_code'] == 'MX'
    assert first.json()['email'] == 'branch@example.test'
    assert first.json()['status'] == 'ACTIVE'
    assert client.post('/locations', headers=headers, json=payload).status_code == 409
    same_code_other_org = client.post(
        '/locations', headers=headers, json={**payload, 'organization_id': other_organization_id}
    )
    assert same_code_other_org.status_code == 201, same_code_other_org.text

    listing = client.get(f'/locations?organization_id={organization_id}', headers=headers)
    assert [item['id'] for item in listing.json()['items']] == [first.json()['id'], second.json()['id']]
    updated = client.patch(
        f"/locations/{first.json()['id']}",
        headers=headers,
        json={'name': 'Renamed', 'status': 'INACTIVE', 'address_line2': None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()['name'] == 'Renamed'
    assert updated.json()['status'] == 'INACTIVE'
    assert client.get(f"/locations/{first.json()['id']}", headers=headers).status_code == 200
    assert client.patch(f"/locations/{first.json()['id']}", headers=headers, json={}).status_code == 422
    assert client.delete(f"/locations/{first.json()['id']}", headers=headers).status_code == 405


def test_location_auth_permission_validation_and_immutable_ownership(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix, permissions=())
    organization_id = _organization(connection, authority.tenant_id, 'ORG')
    headers = _login(client, authority)
    payload = {
        'organization_id': organization_id,
        'code': 'LOC',
        'name': 'Location',
        'timezone': 'America/Mexico_City',
    }

    assert client.get('/locations').status_code == 401
    assert client.post('/locations', headers=headers, json=payload).status_code == 403
    _assign_permission(connection, authority.role_id, 'location.read')
    _assign_permission(connection, authority.role_id, 'location.manage')
    assert client.post('/locations', headers=headers, json={**payload, 'timezone': 'Mexico/Unknown'}).status_code == 422
    assert client.post('/locations', headers=headers, json={**payload, 'country_code': 'MEX'}).status_code == 422
    assert client.post('/locations', headers=headers, json={**payload, 'tenant_id': authority.tenant_id}).status_code == 422
    created = client.post('/locations', headers=headers, json=payload)
    assert created.status_code == 201
    assert client.patch(
        f"/locations/{created.json()['id']}",
        headers=headers,
        json={'organization_id': organization_id},
    ).status_code == 422


def test_location_duplicate_classification_is_constraint_specific() -> None:
    assert is_location_code_conflict(
        _integrity_error(
            "Duplicate entry '1-CENTRO' for key 'locations.uq_locations_organization_code'"
        )
    )
    assert is_location_code_conflict(
        _integrity_error("Duplicate entry '1-CENTRO' for key 'uq_locations_organization_code'")
    )
    assert not is_location_code_conflict(
        _integrity_error("Duplicate entry '1-CENTRO' for key 'uq_locations_id_tenant'")
    )
    assert not is_location_code_conflict(
        _integrity_error('Cannot add or update a child row', code=1452)
    )


@pytest.mark.parametrize(
    'timezone',
    ['America/Mexico_City', 'America/New_York', 'US/Eastern'],
)
def test_valid_iana_timezones_are_accepted(timezone: str) -> None:
    assert validate_timezone(timezone) == timezone


def test_inactive_and_cross_tenant_parent_rules_are_enforced(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    other = _seed_authority(connection, f'{prefix}-other')
    headers = _login(client, authority)
    inactive_organization_id = _organization(connection, authority.tenant_id, 'INACTIVE', 'INACTIVE')
    foreign_organization_id = _organization(connection, other.tenant_id, 'FOREIGN')
    payload = {
        'code': 'LOC',
        'name': 'Location',
        'timezone': 'America/Mexico_City',
    }

    assert client.post(
        '/locations', headers=headers, json={**payload, 'organization_id': inactive_organization_id}
    ).status_code == 409
    assert client.post(
        '/locations', headers=headers, json={**payload, 'organization_id': foreign_organization_id}
    ).status_code == 404
    assert client.get(
        f'/locations?organization_id={foreign_organization_id}', headers=headers
    ).status_code == 404

    active_organization_id = _organization(connection, authority.tenant_id, 'ACTIVE')
    location_id = _location(connection, authority.tenant_id, active_organization_id, 'OWN')
    _execute(
        connection,
        'UPDATE organizations SET status = %s WHERE id = %s',
        ('INACTIVE', active_organization_id),
    )
    _execute(connection, 'UPDATE locations SET status = %s WHERE id = %s', ('INACTIVE', location_id))
    assert client.patch(f'/locations/{location_id}', headers=headers, json={'status': 'ACTIVE'}).status_code == 409

    foreign_location_id = _location(connection, other.tenant_id, foreign_organization_id, 'OTHER')
    assert client.get(f'/locations/{foreign_location_id}', headers=headers).status_code == 404
    assert client.patch(f'/locations/{foreign_location_id}', headers=headers, json={'name': 'No'}).status_code == 404
    assert all(item['tenant_id'] == authority.tenant_id for item in client.get('/locations', headers=headers).json()['items'])


def test_database_rejects_cross_tenant_location_and_invalid_lifecycle(sql_connection) -> None:
    connection, prefix = sql_connection
    tenant_a = _seed_authority(connection, prefix)
    tenant_b = _seed_authority(connection, f'{prefix}-other')
    organization_a = _organization(connection, tenant_a.tenant_id, 'A')
    organization_b = _organization(connection, tenant_b.tenant_id, 'B')

    with pytest.raises(pymysql.err.IntegrityError):
        _location(connection, tenant_a.tenant_id, organization_b, 'CROSS')
    with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
        _execute(
            connection,
            'INSERT INTO organizations (tenant_id, code, name, status) VALUES (%s, %s, %s, %s)',
            (tenant_a.tenant_id, 'BAD', 'Bad', 'SUSPENDED'),
        )
    with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
        _execute(
            connection,
            '''
            INSERT INTO locations
                (tenant_id, organization_id, code, name, timezone, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ''',
            (
                tenant_a.tenant_id,
                organization_a,
                'BAD',
                'Bad',
                'America/Mexico_City',
                'SUSPENDED',
            ),
        )
