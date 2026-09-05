from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pymysql
import pytest
from fastapi.testclient import TestClient

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


def _permission(connection, role_id: int, code: str) -> None:
    _execute(
        connection,
        'INSERT IGNORE INTO permissions (code, description) VALUES (%s, %s)',
        (code, f'Permission {code}'),
    )
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
        permission_id = int(cursor.fetchone()['id'])
    _execute(
        connection,
        'INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)',
        (role_id, permission_id),
    )


def _authority(connection, slug: str, permissions=()) -> Authority:
    tenant_id = _execute(
        connection,
        'INSERT INTO tenants (name, slug, status) VALUES (%s, %s, %s)',
        ('Cash Tenant', slug, 'ACTIVE'),
    )
    email = f'{slug}@example.test'
    user_id = _execute(
        connection,
        'INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,%s,%s)',
        (email, hash_password(PASSWORD), 'Cash User', 'ACTIVE'),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,%s)',
        (tenant_id, user_id, 'ACTIVE'),
    )
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,%s)',
        (tenant_id, 'CASH_TEST_ROLE', 'Cash tests', 'ACTIVE'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',
        (tenant_id, membership_id, role_id),
    )
    for permission in permissions:
        _permission(connection, role_id, permission)
    return Authority(tenant_id, membership_id, role_id, email)


def _organization_location(connection, tenant_id: int, suffix: str) -> tuple[int, int]:
    organization_id = _execute(
        connection,
        'INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,%s,%s)',
        (tenant_id, f'ORG-{suffix}', f'Organization {suffix}', 'ACTIVE'),
    )
    location_id = _execute(
        connection,
        'INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) '
        'VALUES (%s,%s,%s,%s,%s,%s)',
        (
            tenant_id, organization_id, f'LOC-{suffix}', f'Location {suffix}',
            'America/Mexico_City', 'ACTIVE',
        ),
    )
    return organization_id, location_id


def _headers(client: TestClient, authority: Authority) -> dict[str, str]:
    response = client.post(
        '/auth/login', json={'email': authority.email, 'password': PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _resource(
    client: TestClient,
    headers: dict[str, str],
    location_id: int,
    code: str,
    resource_type: str = 'CASH_REGISTER',
) -> dict:
    response = client.post(
        '/resources',
        headers=headers,
        json={
            'location_id': location_id,
            'code': code,
            'name': code,
            'resource_type': resource_type,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def test_cash_register_type_activation_is_permanent_and_existing_types_remain_valid(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    authority = _authority(connection, prefix, ('resource.manage', 'resource.read'))
    _, location_id = _organization_location(connection, authority.tenant_id, 'ONE')
    headers = _headers(client, authority)

    for index, resource_type in enumerate((
        'AREA', 'TABLE', 'WORKSTATION', 'EQUIPMENT', 'VEHICLE', 'DEVICE',
    )):
        _resource(client, headers, location_id, f'R-{index}', resource_type)
    register = _resource(client, headers, location_id, 'REGISTER')
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT cash_management_activated_at FROM locations WHERE id=%s',
            (location_id,),
        )
        activated_at = cursor.fetchone()['cash_management_activated_at']
    assert activated_at is not None

    inactive = client.patch(
        f"/resources/{register['id']}",
        headers=headers,
        json={'status': 'INACTIVE'},
    )
    assert inactive.status_code == 200
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT cash_management_activated_at FROM locations WHERE id=%s',
            (location_id,),
        )
        assert cursor.fetchone()['cash_management_activated_at'] == activated_at


def test_open_read_permissions_identity_lifecycle_and_inactive_survival(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    authority = _authority(connection, prefix, ('resource.manage',))
    _, location_id = _organization_location(connection, authority.tenant_id, 'ONE')
    headers = _headers(client, authority)
    register = _resource(client, headers, location_id, 'REGISTER')

    url = f"/resources/{register['id']}/cash-sessions"
    assert client.post(
        url, headers={**headers, 'Idempotency-Key': 'open'}, json={'currency': 'MXN'}
    ).status_code == 403
    _permission(connection, authority.role_id, 'cash_session.manage')
    opened = client.post(
        url, headers={**headers, 'Idempotency-Key': 'open'}, json={'currency': 'mxn'}
    )
    assert opened.status_code == 201, opened.text
    body = opened.json()
    assert body['cashier_membership_id'] == authority.membership_id
    assert body['opened_by_actor_type'] == 'EMPLOYEE'
    assert body['opened_by_actor_id'] == authority.membership_id
    assert body['opened_by_actor_reference'] is None
    assert body['currency'] == 'MXN'
    assert body['status'] == 'OPEN'
    assert body['movement_version'] == 0

    assert client.get(f"/cash-sessions/{body['id']}", headers=headers).status_code == 403
    _permission(connection, authority.role_id, 'cash_management.read')
    assert client.get(
        f"/cash-sessions/{body['id']}", headers=headers
    ).json() == body

    assert client.patch(
        f"/resources/{register['id']}",
        headers=headers,
        json={'status': 'INACTIVE'},
    ).status_code == 200
    assert client.get(
        f"/cash-sessions/{body['id']}", headers=headers
    ).status_code == 200


def test_open_rejects_non_register_inactive_register_invalid_currency_and_second_session(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    permissions = ('resource.manage', 'cash_session.manage')
    authority = _authority(connection, prefix, permissions)
    _, location_id = _organization_location(connection, authority.tenant_id, 'ONE')
    headers = _headers(client, authority)
    table = _resource(client, headers, location_id, 'TABLE', 'TABLE')
    register = _resource(client, headers, location_id, 'REGISTER')

    def open_session(resource_id: int, key: str, currency: str = 'MXN'):
        return client.post(
            f'/resources/{resource_id}/cash-sessions',
            headers={**headers, 'Idempotency-Key': key},
            json={'currency': currency},
        )

    invalid_type = open_session(table['id'], 'table')
    assert invalid_type.status_code == 409
    assert invalid_type.json()['error']['code'] == 'INVALID_CASH_REGISTER'
    assert open_session(register['id'], 'bad-currency', '12$').status_code == 422
    assert open_session(register['id'], 'first').status_code == 201
    assert open_session(register['id'], 'second').status_code == 409

    other = _resource(client, headers, location_id, 'INACTIVE')
    assert client.patch(
        f"/resources/{other['id']}", headers=headers, json={'status': 'INACTIVE'}
    ).status_code == 200
    inactive = open_session(other['id'], 'inactive')
    assert inactive.status_code == 409
    assert inactive.json()['error']['code'] == 'CASH_REGISTER_INACTIVE'


def test_open_idempotency_replay_conflict_and_concurrent_open(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    authority = _authority(
        connection, prefix, ('resource.manage', 'cash_session.manage')
    )
    _, location_id = _organization_location(connection, authority.tenant_id, 'ONE')
    headers = _headers(client, authority)
    first = _resource(client, headers, location_id, 'FIRST')
    second = _resource(client, headers, location_id, 'SECOND')
    third = _resource(client, headers, location_id, 'THIRD')

    def open_session(resource_id: int, key: str, currency: str = 'MXN'):
        return client.post(
            f'/resources/{resource_id}/cash-sessions',
            headers={**headers, 'Idempotency-Key': key},
            json={'currency': currency},
        )

    created = open_session(first['id'], 'stable')
    replay = open_session(first['id'], 'stable', 'mxn')
    conflict = open_session(first['id'], 'stable', 'USD')
    assert created.status_code == 201
    assert replay.status_code == 200
    assert replay.json()['id'] == created.json()['id']
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'CASH_SESSION_IDEMPOTENCY_CONFLICT'

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(future.result() for future in (
            pool.submit(open_session, second['id'], 'race-a'),
            pool.submit(open_session, second['id'], 'race-b'),
        ))
    assert sorted(response.status_code for response in results) == [201, 409]
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS count FROM cash_sessions "
            "WHERE resource_id=%s AND status='OPEN'",
            (second['id'],),
        )
        assert cursor.fetchone()['count'] == 1

    with ThreadPoolExecutor(max_workers=2) as pool:
        same_key_results = tuple(future.result() for future in (
            pool.submit(open_session, third['id'], 'same-race'),
            pool.submit(open_session, third['id'], 'same-race'),
        ))
    assert sorted(response.status_code for response in same_key_results) == [200, 201]
    assert len({response.json()['id'] for response in same_key_results}) == 1


def test_tenant_isolation_and_scoped_foreign_keys(client, sql_connection) -> None:
    connection, prefix = sql_connection
    permissions = (
        'resource.manage', 'cash_session.manage', 'cash_management.read',
    )
    first = _authority(connection, prefix, permissions)
    second = _authority(connection, f'{prefix}-other', permissions)
    organization_id, location_id = _organization_location(
        connection, first.tenant_id, 'ONE'
    )
    _, other_location_id = _organization_location(connection, second.tenant_id, 'TWO')
    first_headers = _headers(client, first)
    second_headers = _headers(client, second)
    register = _resource(client, first_headers, location_id, 'REGISTER')
    unused_register = _resource(client, first_headers, location_id, 'UNUSED')
    _resource(client, second_headers, other_location_id, 'REGISTER')
    opened = client.post(
        f"/resources/{register['id']}/cash-sessions",
        headers={**first_headers, 'Idempotency-Key': 'open'},
        json={'currency': 'MXN'},
    )
    assert opened.status_code == 201
    session_id = opened.json()['id']
    assert client.get(
        f'/cash-sessions/{session_id}', headers=second_headers
    ).status_code == 404
    assert client.post(
        f"/resources/{register['id']}/cash-sessions",
        headers={**second_headers, 'Idempotency-Key': 'foreign'},
        json={'currency': 'MXN'},
    ).status_code == 404

    with pytest.raises(pymysql.err.IntegrityError):
        _execute(
            connection,
            'INSERT INTO cash_sessions '
            '(tenant_id,organization_id,location_id,resource_id,cashier_membership_id,'
            'currency,status,opened_at,opened_by_actor_type,opened_by_actor_id,'
            'movement_version,open_slot,open_actor_scope,open_idempotency_key,'
            'open_request_schema_version,open_request_fingerprint) '
            "VALUES (%s,%s,%s,%s,%s,'MXN','OPEN',CURRENT_TIMESTAMP,'EMPLOYEE',%s,"
            "0,1,'EMPLOYEE:foreign','foreign',1,%s)",
            (
                first.tenant_id, organization_id, location_id, unused_register['id'],
                second.membership_id, second.membership_id, '0' * 64,
            ),
        )
    with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
        _execute(
            connection,
            'INSERT INTO cash_sessions '
            '(tenant_id,organization_id,location_id,resource_id,cashier_membership_id,'
            'currency,status,opened_at,opened_by_actor_type,opened_by_actor_id,'
            'movement_version,open_slot,open_actor_scope,open_idempotency_key,'
            'open_request_schema_version,open_request_fingerprint) '
            "VALUES (%s,%s,%s,%s,%s,'MXN','CLOSED',CURRENT_TIMESTAMP,'EMPLOYEE',%s,"
            "0,NULL,'EMPLOYEE:scope','scope',1,%s)",
            (
                first.tenant_id, organization_id, other_location_id,
                unused_register['id'], first.membership_id, first.membership_id,
                '1' * 64,
            ),
        )


def test_cash_management_does_not_change_payment(sql_connection) -> None:
    connection, _ = sql_connection
    with connection.cursor() as cursor:
        cursor.execute('SHOW COLUMNS FROM restaurant_payments')
        payment_columns = {row['Field'] for row in cursor.fetchall()}
    assert 'cash_session_id' not in payment_columns
