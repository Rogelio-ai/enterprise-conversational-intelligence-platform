from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import DatabaseManager
from app.main import create_app
from app.models import Customer, CustomerExternalIdentity
from app.restaurant.customers.service import resolve_external_customer
from app.restaurant.integrations.pos.contracts import (
    ExternalCustomer,
    ExternalEntityStatus,
    PosRequestContext,
)
from app.restaurant.integrations.pos.mock import MockPosAdapter, build_mock_pos_dataset


PASSWORD = 'Test Password 123!'
CUSTOMER_PERMISSIONS = ('customer.read', 'customer.manage')


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


def _seed_authority(connection, slug: str, permissions=CUSTOMER_PERMISSIONS) -> Authority:
    tenant_id = _execute(
        connection,
        'INSERT INTO tenants (name, slug, status) VALUES (%s, %s, %s)',
        ('Customer Tenant', slug, 'ACTIVE'),
    )
    email = f'{slug}@example.test'
    user_id = _execute(
        connection,
        'INSERT INTO users (email, password_hash, display_name, status) VALUES (%s, %s, %s, %s)',
        (email, hash_password(PASSWORD), 'Customer User', 'ACTIVE'),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id, user_id, status) VALUES (%s, %s, %s)',
        (tenant_id, user_id, 'ACTIVE'),
    )
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id, name, description, status) VALUES (%s, %s, %s, %s)',
        (tenant_id, 'CUSTOMER_TEST_ROLE', 'Customer test role', 'ACTIVE'),
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
    response = client.post('/auth/login', json={'email': authority.email, 'password': PASSWORD})
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _customer(
    connection,
    tenant_id: int,
    *,
    display_name: str | None = 'Customer',
    email: str | None = None,
    phone: str | None = None,
    source: str = 'PLATFORM',
    status: str = 'ACTIVE',
) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO customers (tenant_id, display_name, email, phone, status, source)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''',
        (tenant_id, display_name, email, phone, status, source),
    )


def _mapping(
    connection,
    tenant_id: int,
    customer_id: int,
    connector_key: str,
    external_customer_id: str,
) -> int:
    return _execute(
        connection,
        '''
        INSERT INTO customer_external_identities
            (tenant_id, customer_id, connector_key, external_customer_id)
        VALUES (%s, %s, %s, %s)
        ''',
        (tenant_id, customer_id, connector_key, external_customer_id),
    )


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as test_client:
        yield test_client


def test_customer_auth_permissions_creation_normalization_and_safe_logging(
    client, sql_connection, caplog: pytest.LogCaptureFixture
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix, permissions=())
    headers = _login(client, authority)
    payload = {
        'display_name': '  Ana Rivera  ',
        'email': '  ANA@Example.Test ',
        'phone': ' +52 (55) 0000-0001 ',
    }

    assert client.get('/customers').status_code == 401
    assert client.get('/customers', headers=headers).status_code == 403
    assert client.post('/customers', headers=headers, json=payload).status_code == 403
    _assign_permission(connection, authority.role_id, 'customer.read')
    assert client.get('/customers', headers=headers).status_code == 200
    assert client.post('/customers', headers=headers, json=payload).status_code == 403
    _assign_permission(connection, authority.role_id, 'customer.manage')

    with caplog.at_level(logging.INFO, logger='ecip.customers'):
        response = client.post('/customers', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body['tenant_id'] == authority.tenant_id
    assert body['display_name'] == 'Ana Rivera'
    assert body['email'] == 'ana@example.test'
    assert body['phone'] == '+525500000001'
    assert body['status'] == 'ACTIVE'
    assert body['source'] == 'PLATFORM'
    customer_logs = [record for record in caplog.records if record.name == 'ecip.customers']
    assert customer_logs[-1].event == 'customer_created'
    assert customer_logs[-1].customer_id == body['id']
    rendered = ' '.join(record.getMessage() for record in customer_logs)
    assert 'Ana Rivera' not in rendered
    assert 'ana@example.test' not in rendered
    assert '+525500000001' not in rendered


def test_customer_validation_immutable_fields_and_no_delete(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    headers = _login(client, authority)

    for payload in ({}, {'display_name': '  ', 'email': '', 'phone': None}):
        assert client.post('/customers', headers=headers, json=payload).status_code == 422
    invalid_phone = 'private-invalid-phone-555-0000'
    invalid_response = client.post(
        '/customers', headers=headers, json={'phone': invalid_phone}
    )
    assert invalid_response.status_code == 422
    assert invalid_phone not in invalid_response.text
    forbidden_create_fields = ('tenant_id', 'source', 'status', 'id', 'created_at', 'updated_at')
    for field in forbidden_create_fields:
        response = client.post(
            '/customers',
            headers=headers,
            json={'display_name': 'Customer', field: authority.tenant_id},
        )
        assert response.status_code == 422

    created = client.post('/customers', headers=headers, json={'display_name': 'Customer'})
    customer_id = created.json()['id']
    assert client.patch(f'/customers/{customer_id}', headers=headers, json={}).status_code == 422
    for payload in (
        {'status': 'VIP'},
        {'status': None},
        {'source': 'POS'},
        {'tenant_id': authority.tenant_id},
    ):
        assert (
            client.patch(f'/customers/{customer_id}', headers=headers, json=payload).status_code
            == 422
        )
    assert client.delete(f'/customers/{customer_id}', headers=headers).status_code == 405


def test_customer_list_exact_search_shared_contacts_detail_patch_and_inactive(
    client, sql_connection
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    headers = _login(client, authority)
    shared = {'email': 'shared@example.test', 'phone': '+525500000099'}
    first = client.post(
        '/customers', headers=headers, json={'display_name': 'First', **shared}
    ).json()
    second = client.post(
        '/customers', headers=headers, json={'display_name': 'Second', **shared}
    ).json()
    third = client.post(
        '/customers', headers=headers, json={'display_name': 'Third', 'phone': '+525500000100'}
    ).json()

    listing = client.get('/customers', headers=headers).json()['items']
    assert [item['id'] for item in listing] == [first['id'], second['id'], third['id']]
    by_email = client.get('/customers?email=SHARED%40EXAMPLE.TEST', headers=headers).json()
    assert [item['id'] for item in by_email['items']] == [first['id'], second['id']]
    by_phone = client.get('/customers?phone=%2B52%20(55)%200000-0099', headers=headers).json()
    assert [item['id'] for item in by_phone['items']] == [first['id'], second['id']]
    combined = client.get(
        '/customers?email=shared%40example.test&phone=%2B525500000099', headers=headers
    ).json()
    assert [item['id'] for item in combined['items']] == [first['id'], second['id']]

    updated = client.patch(
        f"/customers/{first['id']}",
        headers=headers,
        json={'display_name': ' Updated ', 'email': '', 'phone': None, 'status': 'INACTIVE'},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()['display_name'] == 'Updated'
    assert updated.json()['email'] is None
    assert updated.json()['phone'] is None
    assert updated.json()['status'] == 'INACTIVE'
    assert client.get(f"/customers/{first['id']}", headers=headers).status_code == 200
    inactive = client.get('/customers?status=INACTIVE', headers=headers).json()['items']
    assert [item['id'] for item in inactive] == [first['id']]


def test_customer_tenant_isolation_and_patch_identity_invariant(client, sql_connection) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    other = _seed_authority(connection, f'{prefix}-other')
    own_id = _customer(connection, authority.tenant_id, display_name='Own')
    foreign_id = _customer(connection, other.tenant_id, display_name='Foreign')
    headers = _login(client, authority)

    assert client.get(f'/customers/{foreign_id}', headers=headers).status_code == 404
    assert (
        client.patch(
            f'/customers/{foreign_id}', headers=headers, json={'display_name': 'Hidden'}
        ).status_code
        == 404
    )
    assert [item['id'] for item in client.get('/customers', headers=headers).json()['items']] == [
        own_id
    ]
    assert (
        client.patch(f'/customers/{own_id}', headers=headers, json={'display_name': None}).status_code
        == 422
    )
    _mapping(connection, authority.tenant_id, own_id, 'primary-pos', 'external-empty')
    cleared = client.patch(
        f'/customers/{own_id}', headers=headers, json={'display_name': None}
    )
    assert cleared.status_code == 200
    assert cleared.json()['display_name'] is None


def test_external_identity_scopes_case_sensitivity_and_cross_tenant_fk(sql_connection) -> None:
    connection, prefix = sql_connection
    tenant_a = _seed_authority(connection, prefix)
    tenant_b = _seed_authority(connection, f'{prefix}-other')
    customer_a = _customer(connection, tenant_a.tenant_id)
    customer_b = _customer(connection, tenant_b.tenant_id)

    _mapping(connection, tenant_a.tenant_id, customer_a, 'primary-pos', 'Customer-ABC')
    with pytest.raises(pymysql.err.IntegrityError):
        _mapping(connection, tenant_a.tenant_id, customer_a, 'primary-pos', 'Customer-ABC')
    _mapping(connection, tenant_a.tenant_id, customer_a, 'primary-pos', 'customer-abc')
    _mapping(connection, tenant_a.tenant_id, customer_a, 'secondary-pos', 'Customer-ABC')
    _mapping(connection, tenant_b.tenant_id, customer_b, 'primary-pos', 'Customer-ABC')
    with pytest.raises(pymysql.err.IntegrityError):
        _mapping(connection, tenant_a.tenant_id, customer_b, 'cross-tenant', 'customer')


def test_customer_port_resolution_is_idempotent_non_merging_and_pii_safe(
    integration_settings, sql_connection, caplog: pytest.LogCaptureFixture
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    existing_id = _customer(
        connection,
        authority.tenant_id,
        display_name='Existing',
        email='ana@example.test',
        phone='+525500000001',
    )
    adapter = MockPosAdapter(
        build_mock_pos_dataset(
            tenant_id=authority.tenant_id,
            connector_key='primary-pos',
            location_ids=(101, 102),
        )
    )
    context = PosRequestContext(
        tenant_id=authority.tenant_id,
        connector_key='primary-pos',
        correlation_id='customer-resolution-test',
    )

    async def exercise() -> tuple[int, int]:
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                first = await resolve_external_customer(
                    db, adapter, context, external_customer_id='customer-001'
                )
                first_id = first.id
            with connection.cursor() as cursor:
                cursor.execute(
                    'UPDATE customers SET display_name = %s WHERE id = %s',
                    ('Canonical Name', first_id),
                )
            async with manager.session_factory() as db:
                second = await resolve_external_customer(
                    db, adapter, context, external_customer_id='customer-001'
                )
                assert second.display_name == 'Canonical Name'
                customer_count = await db.scalar(
                    select(func.count(Customer.id)).where(Customer.tenant_id == authority.tenant_id)
                )
                mapping_count = await db.scalar(
                    select(func.count(CustomerExternalIdentity.id)).where(
                        CustomerExternalIdentity.tenant_id == authority.tenant_id
                    )
                )
                assert customer_count == 2
                assert mapping_count == 1
                return first_id, second.id
        finally:
            await manager.dispose()

    with caplog.at_level(logging.INFO, logger='ecip.customers'):
        first_id, second_id = asyncio.run(exercise())
    assert first_id == second_id
    assert first_id != existing_id
    rendered = ' '.join(record.getMessage() for record in caplog.records if record.name == 'ecip.customers')
    for pii in ('Ana Rivera', 'ana@example.test', '+525500000001', 'customer-001'):
        assert pii not in rendered


def test_pos_customer_without_contact_data_can_be_resolved(
    integration_settings, sql_connection
) -> None:
    connection, prefix = sql_connection
    authority = _seed_authority(connection, prefix)
    context = PosRequestContext(
        tenant_id=authority.tenant_id,
        connector_key='no-contact-pos',
        correlation_id='no-contact-test',
    )

    class NoContactCustomerPort:
        async def get_customer(self, context, *, external_customer_id):
            return ExternalCustomer(
                external_id=external_customer_id,
                status=ExternalEntityStatus.ACTIVE,
            )

    async def exercise() -> int:
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                customer = await resolve_external_customer(
                    db,
                    NoContactCustomerPort(),  # type: ignore[arg-type]
                    context,
                    external_customer_id='anonymous-pos-customer',
                )
                assert customer.source == 'POS'
                assert customer.display_name is None
                assert customer.email is None
                assert customer.phone is None
                return customer.id
        finally:
            await manager.dispose()

    customer_id = asyncio.run(exercise())
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM customer_external_identities WHERE customer_id = %s',
            (customer_id,),
        )
        assert cursor.fetchone()['count'] == 1
