from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import (
    TokenValidationError,
    create_access_token,
    create_diner_access_token,
    decode_access_token,
    decode_diner_access_token,
    hash_password,
)
from app.db.session import DatabaseManager
from app.main import create_app
from app.restaurant.orders import errors as draft_errors
from app.restaurant.orders import service as draft_service
from app.restaurant.service_sessions import errors, service


PASSWORD = 'Test Password 123!'


@dataclass(frozen=True)
class Scope:
    tenant_id: int
    organization_id: int
    location_id: int
    resource_id: int
    membership_id: int
    email: str


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _scope(connection, prefix: str, *, resource_type: str = 'TABLE', resource_status: str = 'ACTIVE') -> Scope:
    tenant_id = _execute(connection, "INSERT INTO tenants (name,slug,status) VALUES ('Service Tenant',%s,'ACTIVE')", (prefix,))
    email = f'{prefix}@example.test'
    user_id = _execute(connection, "INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,'Staff','ACTIVE')", (email, hash_password(PASSWORD)))
    membership_id = _execute(connection, "INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,'ACTIVE')", (tenant_id, user_id))
    role_id = _execute(connection, "INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,'Role','ACTIVE')", (tenant_id, f'SERVICE_{uuid4().hex}'))
    _execute(connection, 'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)', (tenant_id, membership_id, role_id))
    for code in ('restaurant_service.read', 'restaurant_service.manage', 'order_draft.read', 'order_draft.manage'):
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
        _execute(connection, 'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)', (role_id, permission_id))
    organization_id = _execute(connection, "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,'Organization','ACTIVE')", (tenant_id, f'ORG-{uuid4().hex[:12]}'))
    location_id = _execute(connection, "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,%s,'Location','America/Mexico_City','ACTIVE')", (tenant_id, organization_id, f'LOC-{uuid4().hex[:12]}'))
    resource_id = _execute(connection, "INSERT INTO resources (tenant_id,location_id,code,name,resource_type,status) VALUES (%s,%s,%s,'Table',%s,%s)", (tenant_id, location_id, f'T-{uuid4().hex[:12]}', resource_type, resource_status))
    return Scope(tenant_id, organization_id, location_id, resource_id, membership_id, email)


def _headers(client: TestClient, scope: Scope) -> dict[str, str]:
    response = client.post('/auth/login', json={'email': scope.email, 'password': PASSWORD})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _open(client: TestClient, scope: Scope, party_size: int = 4):
    response = client.post(f'/resources/{scope.resource_id}/service-sessions', headers=_headers(client, scope), json={'party_size': party_size})
    assert response.status_code == 201, response.text
    return response.json()


def _join(client: TestClient, opened: dict, name: str, email: str | None = None, code: str | None = None):
    payload = {'join_context_key': opened['join_context_key'], 'display_name': name, 'access_code': code or opened['access_code']}
    if email is not None:
        payload['email'] = email
    return client.post('/diner-sessions/join', json=payload)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def test_code_generation_is_four_digit_text_and_preserves_leading_zero(monkeypatch):
    monkeypatch.setattr(service.secrets, 'randbelow', lambda _: 42)
    assert service.generate_access_code() == '0042'


def test_staff_open_read_validation_regenerate_close_and_resource_lifecycle(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    opened = _open(client, scope, party_size=2)
    assert len(opened['access_code']) == 4 and opened['access_code'].isdigit()
    with connection.cursor() as cursor:
        cursor.execute('SELECT access_code_digest,status FROM restaurant_service_sessions WHERE id=%s', (opened['id'],))
        persisted = cursor.fetchone()
    assert persisted['access_code_digest'] != opened['access_code']
    assert opened['access_code'] not in persisted['access_code_digest']
    current = client.get(f'/resources/{scope.resource_id}/service-sessions/current', headers=_headers(client, scope))
    assert current.status_code == 200
    assert 'access_code' not in current.json() and 'access_code_digest' not in current.json()
    assert client.post(f'/resources/{scope.resource_id}/service-sessions', headers=_headers(client, scope), json={'party_size': 2}).status_code == 409
    regenerated = client.post(f"/restaurant-service-sessions/{opened['id']}/access-code/regenerate", headers=_headers(client, scope))
    assert regenerated.status_code == 200 and regenerated.json()['access_code_version'] == 2
    assert _join(client, opened, 'Old Code').status_code == 401
    opened['access_code'] = regenerated.json()['access_code']
    joined = _join(client, opened, 'Diner')
    assert joined.status_code == 201
    closed = client.post(f"/restaurant-service-sessions/{opened['id']}/close", headers=_headers(client, scope))
    assert closed.status_code == 200 and closed.json()['status'] == 'CLOSED'
    assert client.get('/diner-session', headers={'Authorization': f"Bearer {joined.json()['access_token']}"}).status_code == 401
    with connection.cursor() as cursor:
        cursor.execute('SELECT status FROM resources WHERE id=%s', (scope.resource_id,))
        assert cursor.fetchone()['status'] == 'ACTIVE'
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_service_sessions WHERE resource_id=%s', (scope.resource_id,))
        assert cursor.fetchone()['count'] == 1
    reopened = _open(client, scope, party_size=1)
    assert reopened['id'] != opened['id']


@pytest.mark.parametrize('resource_type,resource_status', [('AREA', 'ACTIVE'), ('TABLE', 'INACTIVE')])
def test_open_rejects_non_serviceable_resource(client, sql_connection, resource_type, resource_status):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, resource_type=resource_type, resource_status=resource_status)
    assert client.post(f'/resources/{scope.resource_id}/service-sessions', headers=_headers(client, scope), json={'party_size': 1}).status_code == 404


def test_join_identity_capacity_conversation_draft_end_and_token_separation(client, sql_connection, integration_settings):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    opened = _open(client, scope, party_size=2)
    first = _join(client, opened, '  Alex  ', '  DINER@Example.Test ')
    assert first.status_code == 201, first.text
    first_body = first.json()
    diner_headers = {'Authorization': f"Bearer {first_body['access_token']}"}
    own = client.get('/diner-session', headers=diner_headers)
    assert own.status_code == 200 and own.json()['display_name'] == 'Alex'
    conversation = client.get('/diner/conversation', headers=diner_headers)
    assert conversation.status_code == 200 and conversation.json()['id'] == first_body['conversation_id']
    message = client.post('/diner/conversation/messages', headers=diner_headers, json={'modality': 'TEXT', 'content_text': 'Please add water'})
    assert message.status_code == 201 and message.json()['conversation_id'] == first_body['conversation_id']
    draft = client.post('/diner/order-draft', headers=diner_headers)
    assert draft.status_code == 201
    product_id = _execute(connection, "INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,'Coffee','ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id))
    menu_id = _execute(connection, "INSERT INTO menus (tenant_id,organization_id,name,status) VALUES (%s,%s,'Diner Menu','ACTIVE')", (scope.tenant_id, scope.organization_id))
    _execute(connection, "INSERT INTO menu_locations (tenant_id,organization_id,menu_id,location_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, menu_id, scope.location_id))
    section_id = _execute(connection, "INSERT INTO menu_sections (tenant_id,organization_id,menu_id,name,status) VALUES (%s,%s,%s,'Drinks','ACTIVE')", (scope.tenant_id, scope.organization_id, menu_id))
    _execute(connection, "INSERT INTO menu_items (tenant_id,organization_id,menu_id,section_id,product_id,status) VALUES (%s,%s,%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, menu_id, section_id, product_id))
    _execute(connection, "INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,50,'MXN','ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id, product_id, scope.location_id))
    added = client.post('/diner/order-draft/items', headers=diner_headers, json={'product_id': product_id, 'quantity': '1', 'expected_version': 1})
    assert added.status_code == 201 and added.json()['readiness'] == 'READY'
    preview = client.get('/diner/checkout-preview', headers=diner_headers)
    assert preview.status_code == 200 and preview.json()['payable_total'] == '50.00'
    with connection.cursor() as cursor:
        cursor.execute('SELECT normalized_email,customer_id FROM diner_sessions WHERE id=%s', (first_body['diner_session_id'],))
        row = cursor.fetchone()
        assert row == {'normalized_email': 'diner@example.test', 'customer_id': None}
        cursor.execute('SELECT participant_type FROM conversation_participants WHERE conversation_id=%s ORDER BY id', (first_body['conversation_id'],))
        assert {value['participant_type'] for value in cursor.fetchall()} == {'CUSTOMER', 'DIGITAL_WAITER'}
    assert _join(client, opened, 'Same Identity', 'diner@example.test').status_code == 409
    second = _join(client, opened, 'Alex')
    assert second.status_code == 201
    assert _join(client, opened, 'Over Capacity').status_code == 409
    assert client.get('/auth/me', headers=diner_headers).status_code == 401
    staff_token = _headers(client, scope)['Authorization'].split()[1]
    assert client.get('/diner-session', headers={'Authorization': f'Bearer {staff_token}'}).status_code == 401
    ended = client.post('/diner-session/end', headers=diner_headers)
    assert ended.status_code == 200 and ended.json()['status'] == 'ENDED'
    assert client.get('/diner-session', headers=diner_headers).status_code == 401
    replacement = _join(client, opened, 'Alex Again', 'DINER@example.test')
    assert replacement.status_code == 201
    with pytest.raises(TokenValidationError):
        decode_access_token(first_body['access_token'], settings=integration_settings)
    staff_created = create_access_token(settings=integration_settings, user_id=1, tenant_id=1, membership_id=1)
    with pytest.raises(TokenValidationError):
        decode_diner_access_token(staff_created, settings=integration_settings)


def test_customer_resolution_links_exact_one_but_never_creates_or_merges(client, sql_connection):
    connection, prefix = sql_connection
    exact = _scope(connection, prefix)
    exact_customer_id = _execute(connection, "INSERT INTO customers (tenant_id,display_name,email,status,source) VALUES (%s,'Known','known@example.test','ACTIVE','PLATFORM')", (exact.tenant_id,))
    exact_opened = _open(client, exact, party_size=1)
    exact_join = _join(client, exact_opened, 'Known', ' KNOWN@example.test ')
    assert exact_join.status_code == 201 and exact_join.json()['customer_id'] == exact_customer_id

    ambiguous = _scope(connection, f'{prefix}-ambiguous')
    for label in ('One', 'Two'):
        _execute(connection, "INSERT INTO customers (tenant_id,display_name,email,status,source) VALUES (%s,%s,'shared@example.test','ACTIVE','PLATFORM')", (ambiguous.tenant_id, label))
    ambiguous_opened = _open(client, ambiguous, party_size=2)
    ambiguous_join = _join(client, ambiguous_opened, 'Shared', 'shared@example.test')
    no_email_join = _join(client, ambiguous_opened, 'Anonymous')
    assert ambiguous_join.status_code == 201 and ambiguous_join.json()['customer_id'] is None
    assert no_email_join.status_code == 201 and no_email_join.json()['customer_id'] is None
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM customers WHERE tenant_id=%s', (ambiguous.tenant_id,))
        assert cursor.fetchone()['count'] == 2


def test_failed_attempt_lockout_is_persistent_and_unknown_context_is_generic(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    opened = _open(client, scope, party_size=1)
    unknown = _join(client, {**opened, 'join_context_key': 'x' * 43}, 'Unknown', code='9999')
    wrong = [_join(client, opened, 'Wrong', code='9999') for _ in range(5)]
    assert unknown.status_code == 401
    assert [value.status_code for value in wrong[:4]] == [401] * 4
    assert wrong[4].status_code == 429
    locked = _join(client, opened, 'Correct')
    assert locked.status_code == 429 and 1 <= int(locked.headers['retry-after']) <= 300
    with connection.cursor() as cursor:
        cursor.execute('SELECT failed_join_attempts,join_locked_until FROM restaurant_service_sessions WHERE id=%s', (opened['id'],))
        row = cursor.fetchone()
    assert row['failed_join_attempts'] == 5 and row['join_locked_until'] is not None


def test_diner_service_ownership_defense_blocks_another_conversation(client, sql_connection, integration_settings):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    opened = _open(client, scope, party_size=2)
    a = _join(client, opened, 'A').json()
    b = _join(client, opened, 'B').json()
    assert client.post('/diner/order-draft', headers={'Authorization': f"Bearer {b['access_token']}"}).status_code == 201
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM order_drafts WHERE conversation_id=%s', (b['conversation_id'],))
        b_draft_id = int(cursor.fetchone()['id'])

    async def probe():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                with pytest.raises(draft_errors.DraftNotFoundError):
                    await draft_service.get_draft(
                        db,
                        tenant_id=scope.tenant_id,
                        draft_id=b_draft_id,
                        owner_diner_session_id=a['diner_session_id'],
                        owned_conversation_id=a['conversation_id'],
                    )
        finally:
            await manager.dispose()

    asyncio.run(probe())


def test_real_concurrent_final_slot_and_duplicate_email(client, sql_connection, integration_settings):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    opened = _open(client, scope, party_size=4)
    for index in range(3):
        assert _join(client, opened, f'Existing {index}').status_code == 201

    async def concurrent(email_a: str | None, email_b: str | None):
        manager = DatabaseManager(integration_settings)
        async def one(label: str, email: str | None):
            async with manager.session_factory() as db:
                try:
                    await service.join_diner(db, settings=integration_settings, join_context_key=opened['join_context_key'], access_code=opened['access_code'], display_name=label, email=email)
                    return 'success'
                except errors.CapacityConflictError:
                    return 'capacity'
                except errors.DuplicateDinerIdentityError:
                    return 'duplicate'
        try:
            return await asyncio.gather(one('Concurrent A', email_a), one('Concurrent B', email_b))
        finally:
            await manager.dispose()

    assert sorted(asyncio.run(concurrent(None, None))) == ['capacity', 'success']
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM diner_sessions WHERE service_session_id=%s AND active_slot=1', (opened['id'],))
        assert cursor.fetchone()['count'] == 4

    second_scope = _scope(connection, f'{prefix}-duplicate')
    second_opened = _open(client, second_scope, party_size=2)
    opened = second_opened
    results = asyncio.run(concurrent('same@example.test', ' SAME@example.test '))
    assert sorted(results) == ['duplicate', 'success']


def test_real_concurrent_open_has_one_winner(sql_connection, integration_settings):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)

    async def run():
        manager = DatabaseManager(integration_settings)
        async def one():
            async with manager.session_factory() as db:
                try:
                    await service.open_service_session(db, settings=integration_settings, tenant_id=scope.tenant_id, membership_id=scope.membership_id, resource_id=scope.resource_id, party_size=2)
                    return 'success'
                except errors.ResourceAlreadyOccupiedError:
                    return 'occupied'
        try:
            return await asyncio.gather(one(), one())
        finally:
            await manager.dispose()

    assert sorted(asyncio.run(run())) == ['occupied', 'success']
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_service_sessions WHERE resource_id=%s AND open_slot=1', (scope.resource_id,))
        assert cursor.fetchone()['count'] == 1


def test_real_concurrent_join_vs_party_size_decrease_preserves_capacity(client, sql_connection, integration_settings):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    opened = _open(client, scope, party_size=2)
    assert _join(client, opened, 'Existing').status_code == 201

    async def run():
        manager = DatabaseManager(integration_settings)

        async def join():
            async with manager.session_factory() as db:
                try:
                    await service.join_diner(db, settings=integration_settings, join_context_key=opened['join_context_key'], access_code=opened['access_code'], display_name='Concurrent', email=None)
                    return 'joined'
                except errors.CapacityConflictError:
                    return 'capacity'

        async def decrease():
            async with manager.session_factory() as db:
                try:
                    await service.update_party_size(db, tenant_id=scope.tenant_id, session_id=opened['id'], party_size=1)
                    return 'decreased'
                except errors.PartySizeConflictError:
                    return 'party_conflict'

        try:
            return await asyncio.gather(join(), decrease())
        finally:
            await manager.dispose()

    results = asyncio.run(run())
    assert results in (['joined', 'party_conflict'], ['capacity', 'decreased'])
    with connection.cursor() as cursor:
        cursor.execute('SELECT party_size FROM restaurant_service_sessions WHERE id=%s', (opened['id'],))
        party_size = cursor.fetchone()['party_size']
        cursor.execute('SELECT COUNT(*) AS count FROM diner_sessions WHERE service_session_id=%s AND active_slot=1', (opened['id'],))
        active = cursor.fetchone()['count']
    assert active <= party_size
