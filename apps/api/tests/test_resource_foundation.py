from __future__ import annotations

from dataclasses import dataclass
import logging

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.routes.resources import _is_duplicate_code_error as is_resource_code_conflict
from app.core.security import hash_password
from app.main import create_app


PASSWORD = 'Test Password 123!'
RESOURCE_PERMISSIONS = ('resource.read', 'resource.manage')


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


def _seed_authority(connection, slug: str, permissions=RESOURCE_PERMISSIONS) -> Authority:
    tenant_id = _execute(
        connection,
        'INSERT INTO tenants (name, slug, status) VALUES (%s, %s, %s)',
        ('Resource Tenant', slug, 'ACTIVE'),
    )
    email = f'{slug}@example.test'
    user_id = _execute(
        connection,
        'INSERT INTO users (email, password_hash, display_name, status) VALUES (%s, %s, %s, %s)',
        (email, hash_password(PASSWORD), 'Resource User', 'ACTIVE'),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id, user_id, status) VALUES (%s, %s, %s)',
        (tenant_id, user_id, 'ACTIVE'),
    )
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id, name, description, status) VALUES (%s, %s, %s, %s)',
        (tenant_id, 'RESOURCE_TEST_ROLE', 'Resource test role', 'ACTIVE'),
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


def _organization(connection, tenant_id: int, code: str) -> int:
    return _execute(
        connection,
        'INSERT INTO organizations (tenant_id, code, name, status) VALUES (%s, %s, %s, %s)',
        (tenant_id, code, f'Organization {code}', 'ACTIVE'),
    )


def _location(
    connection,
    tenant_id: int,
    organization_id: int,
    code: str,
    status: str = 'ACTIVE',
) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO locations (tenant_id, organization_id, code, name, timezone, status)
        VALUES (%s, %s, %s, %s, 'America/Mexico_City', %s)
        ''',
        (tenant_id, organization_id, code, f'Location {code}', status),
    )


def _resource(
    connection,
    tenant_id: int,
    location_id: int,
    code: str,
    resource_type: str = 'EQUIPMENT',
    status: str = 'ACTIVE',
) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO resources (tenant_id, location_id, code, name, resource_type, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''',
        (tenant_id, location_id, code, f'Resource {code}', resource_type, status),
    )


def _integrity_error(message: str, code: int = 1062) -> IntegrityError:
    return IntegrityError(None, None, pymysql.err.IntegrityError(code, message))


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as test_client:
        yield test_client


def test_resource_auth_permissions_creation_and_logging(
    client, sql_connection, caplog: pytest.LogCaptureFixture
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix, permissions=())
    organization_id = _organization(connection, authority.tenant_id, 'ORG')
    location_id = _location(connection, authority.tenant_id, organization_id, 'LOC')
    headers = _login(client, authority)
    payload = {
        'location_id': location_id,
        'code': ' grill-1 ',
        'name': ' Grill One ',
        'resource_type': 'EQUIPMENT',
    }

    assert client.get('/resources').status_code == 401
    assert client.get('/resources', headers=headers).status_code == 403
    assert client.post('/resources', headers=headers, json=payload).status_code == 403
    _assign_permission(connection, authority.role_id, 'resource.read')
    assert client.get('/resources', headers=headers).status_code == 200
    assert client.post('/resources', headers=headers, json=payload).status_code == 403
    _assign_permission(connection, authority.role_id, 'resource.manage')

    with caplog.at_level(logging.INFO, logger='ecip.resources'):
        created = client.post('/resources', headers=headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()['tenant_id'] == authority.tenant_id
    assert created.json()['location_id'] == location_id
    assert created.json()['code'] == 'GRILL-1'
    assert created.json()['name'] == 'Grill One'
    assert created.json()['resource_type'] == 'EQUIPMENT'
    assert created.json()['status'] == 'ACTIVE'
    record = next(record for record in caplog.records if record.name == 'ecip.resources')
    assert record.event == 'resource_created'
    assert record.operation == 'create'
    assert record.tenant_id == authority.tenant_id
    assert record.location_id == location_id
    assert record.resource_id == created.json()['id']
    assert record.correlation_id


def test_resource_list_filters_pagination_detail_patch_and_no_delete(
    client, sql_connection
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    organization_id = _organization(connection, authority.tenant_id, 'ORG')
    first_location = _location(connection, authority.tenant_id, organization_id, 'ONE')
    second_location = _location(connection, authority.tenant_id, organization_id, 'TWO')
    headers = _login(client, authority)

    first = client.post(
        '/resources',
        headers=headers,
        json={
            'location_id': first_location,
            'code': 'TABLE-1',
            'name': 'Table One',
            'resource_type': 'TABLE',
        },
    )
    second = client.post(
        '/resources',
        headers=headers,
        json={
            'location_id': first_location,
            'code': 'OVEN-1',
            'name': 'Oven One',
            'resource_type': 'EQUIPMENT',
        },
    )
    third = client.post(
        '/resources',
        headers=headers,
        json={
            'location_id': second_location,
            'code': 'TABLE-1',
            'name': 'Other Table',
            'resource_type': 'TABLE',
        },
    )
    assert {first.status_code, second.status_code, third.status_code} == {201}

    resource_id = first.json()['id']
    assert client.get(f'/resources/{resource_id}', headers=headers).json()['code'] == 'TABLE-1'
    by_location = client.get(f'/resources?location_id={first_location}', headers=headers).json()
    assert [item['id'] for item in by_location['items']] == [
        first.json()['id'],
        second.json()['id'],
    ]
    by_type = client.get('/resources?resource_type=TABLE', headers=headers).json()
    assert [item['id'] for item in by_type['items']] == [first.json()['id'], third.json()['id']]

    updated = client.patch(
        f'/resources/{resource_id}',
        headers=headers,
        json={'code': ' table-main ', 'name': ' Main Table ', 'status': 'INACTIVE'},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()['code'] == 'TABLE-MAIN'
    assert updated.json()['name'] == 'Main Table'
    assert updated.json()['status'] == 'INACTIVE'
    inactive = client.get('/resources?status=INACTIVE', headers=headers).json()['items']
    assert [item['id'] for item in inactive] == [resource_id]
    page = client.get('/resources?limit=1&offset=1', headers=headers).json()
    assert page['limit'] == 1
    assert page['offset'] == 1
    assert [item['id'] for item in page['items']] == [second.json()['id']]
    assert client.get(f'/resources/{resource_id}', headers=headers).status_code == 200
    assert client.delete(f'/resources/{resource_id}', headers=headers).status_code == 405


def test_resource_validation_and_immutable_ownership(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    organization_id = _organization(connection, authority.tenant_id, 'ORG')
    location_id = _location(connection, authority.tenant_id, organization_id, 'LOC')
    headers = _login(client, authority)
    payload = {
        'location_id': location_id,
        'code': 'RESOURCE',
        'name': 'Resource',
        'resource_type': 'DEVICE',
    }

    assert (
        client.post(
            '/resources', headers=headers, json={**payload, 'tenant_id': authority.tenant_id}
        ).status_code
        == 422
    )
    assert (
        client.post(
            '/resources', headers=headers, json={**payload, 'resource_type': 'OTHER'}
        ).status_code
        == 422
    )
    assert (
        client.post(
            '/resources', headers=headers, json={**payload, 'code': 'bad code'}
        ).status_code
        == 422
    )
    created = client.post('/resources', headers=headers, json=payload)
    resource_id = created.json()['id']
    assert client.patch(f'/resources/{resource_id}', headers=headers, json={}).status_code == 422
    invalid_updates = (
        {'name': None},
        {'status': 'MAINTENANCE'},
        {'resource_type': 'OTHER'},
        {'location_id': location_id},
        {'tenant_id': authority.tenant_id},
    )
    for update in invalid_updates:
        assert (
            client.patch(f'/resources/{resource_id}', headers=headers, json=update).status_code
            == 422
        )


def test_resource_uniqueness_scopes_and_duplicate_classification(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    other = _seed_authority(connection, f'{prefix}-other')
    organization_id = _organization(connection, authority.tenant_id, 'ORG')
    other_organization_id = _organization(connection, other.tenant_id, 'ORG')
    first_location = _location(connection, authority.tenant_id, organization_id, 'ONE')
    second_location = _location(connection, authority.tenant_id, organization_id, 'TWO')
    other_location = _location(connection, other.tenant_id, other_organization_id, 'ONE')
    headers = _login(client, authority)
    payload = {
        'location_id': first_location,
        'code': 'SHARED',
        'name': 'Shared',
        'resource_type': 'AREA',
    }

    assert client.post('/resources', headers=headers, json=payload).status_code == 201
    assert client.post('/resources', headers=headers, json=payload).status_code == 409
    assert (
        client.post(
            '/resources', headers=headers, json={**payload, 'location_id': second_location}
        ).status_code
        == 201
    )
    _resource(connection, other.tenant_id, other_location, 'SHARED', 'AREA')

    assert is_resource_code_conflict(
        _integrity_error(
            "Duplicate entry '1-SHARED' for key 'resources.uq_resources_location_code'"
        )
    )
    assert is_resource_code_conflict(
        _integrity_error("Duplicate entry '1-SHARED' for key 'uq_resources_location_code'")
    )
    assert not is_resource_code_conflict(
        _integrity_error("Duplicate entry '1-1' for key 'uq_resources_id_tenant'")
    )
    assert not is_resource_code_conflict(
        _integrity_error('Cannot add or update a child row', code=1452)
    )


def test_resource_tenant_isolation_and_foreign_location_is_hidden(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    other = _seed_authority(connection, f'{prefix}-other')
    organization_id = _organization(connection, authority.tenant_id, 'ORG')
    other_organization_id = _organization(connection, other.tenant_id, 'ORG')
    own_location = _location(connection, authority.tenant_id, organization_id, 'OWN')
    foreign_location = _location(connection, other.tenant_id, other_organization_id, 'FOREIGN')
    own_resource = _resource(connection, authority.tenant_id, own_location, 'OWN')
    foreign_resource = _resource(connection, other.tenant_id, foreign_location, 'FOREIGN')
    headers = _login(client, authority)
    payload = {
        'location_id': foreign_location,
        'code': 'NO',
        'name': 'No',
        'resource_type': 'EQUIPMENT',
    }

    assert client.post('/resources', headers=headers, json=payload).status_code == 404
    assert (
        client.get(f'/resources?location_id={foreign_location}', headers=headers).status_code
        == 404
    )
    assert client.get(f'/resources/{foreign_resource}', headers=headers).status_code == 404
    assert (
        client.patch(
            f'/resources/{foreign_resource}', headers=headers, json={'name': 'No'}
        ).status_code
        == 404
    )
    listing = client.get('/resources', headers=headers).json()['items']
    assert [item['id'] for item in listing] == [own_resource]
    assert all(item['tenant_id'] == authority.tenant_id for item in listing)


def test_parent_location_lifecycle_rules(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    organization_id = _organization(connection, authority.tenant_id, 'ORG')
    inactive_location = _location(
        connection, authority.tenant_id, organization_id, 'INACTIVE', 'INACTIVE'
    )
    active_location = _location(connection, authority.tenant_id, organization_id, 'ACTIVE')
    headers = _login(client, authority)
    payload = {
        'code': 'RESOURCE',
        'name': 'Resource',
        'resource_type': 'WORKSTATION',
    }

    assert (
        client.post(
            '/resources', headers=headers, json={**payload, 'location_id': inactive_location}
        ).status_code
        == 409
    )
    created = client.post(
        '/resources', headers=headers, json={**payload, 'location_id': active_location}
    )
    resource_id = created.json()['id']
    _execute(
        connection,
        'UPDATE locations SET status = %s WHERE id = %s',
        ('INACTIVE', active_location),
    )
    assert client.get(f'/resources/{resource_id}', headers=headers).json()['status'] == 'ACTIVE'
    assert (
        client.patch(
            f'/resources/{resource_id}', headers=headers, json={'status': 'INACTIVE'}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f'/resources/{resource_id}', headers=headers, json={'status': 'ACTIVE'}
        ).status_code
        == 409
    )


def test_database_rejects_cross_tenant_location_invalid_type_and_status(sql_connection) -> None:
    connection, prefix = sql_connection
    tenant_a = _seed_authority(connection, prefix)
    tenant_b = _seed_authority(connection, f'{prefix}-other')
    organization_a = _organization(connection, tenant_a.tenant_id, 'A')
    organization_b = _organization(connection, tenant_b.tenant_id, 'B')
    location_a = _location(connection, tenant_a.tenant_id, organization_a, 'A')
    location_b = _location(connection, tenant_b.tenant_id, organization_b, 'B')

    with pytest.raises(pymysql.err.IntegrityError):
        _resource(connection, tenant_a.tenant_id, location_b, 'CROSS')
    with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
        _resource(connection, tenant_a.tenant_id, location_a, 'BAD-TYPE', 'UNKNOWN')
    with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
        _resource(connection, tenant_a.tenant_id, location_a, 'BAD-STATUS', status='MAINTENANCE')
