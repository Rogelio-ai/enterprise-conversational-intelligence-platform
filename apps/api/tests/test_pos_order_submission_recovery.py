from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4
from threading import Event

from fastapi.testclient import TestClient
import pytest

from app.core.security import hash_password
from app.db.session import DatabaseManager
from app.main import create_app
from app.restaurant.integrations.pos.mock import (
    MockPosAdapter,
    MockPosFailureMode,
    build_mock_pos_dataset,
)
from app.restaurant.pos_submissions import service as submission_service


PASSWORD = 'Test Password 123!'
CONNECTOR = 'mock-pos'


@dataclass(frozen=True)
class Scope:
    tenant_id: int
    organization_id: int
    location_id: int
    resource_id: int
    email: str


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _scope(connection, prefix: str, *, include_pos_permissions: bool = True) -> Scope:
    tenant_id = _execute(connection, "INSERT INTO tenants (name,slug,status) VALUES ('POS Tenant',%s,'ACTIVE')", (prefix,))
    email = f'{prefix}@example.test'
    user_id = _execute(connection, "INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,'Staff','ACTIVE')", (email, hash_password(PASSWORD)))
    membership_id = _execute(connection, "INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,'ACTIVE')", (tenant_id, user_id))
    role_id = _execute(connection, "INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,'Role','ACTIVE')", (tenant_id, f'POS_{uuid4().hex}'))
    _execute(connection, 'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)', (tenant_id, membership_id, role_id))
    permissions = [
        'restaurant_service.read', 'restaurant_service.manage', 'order_draft.read',
        'order_draft.manage', 'conversation.read', 'conversation.manage',
        'restaurant_order.read',
        'preparation.read', 'preparation.route', 'preparation.configure',
    ]
    if include_pos_permissions:
        permissions.extend(('pos_submission.read', 'pos_submission.submit', 'pos_submission.retry', 'pos_submission.recover'))
    for code in permissions:
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
        _execute(connection, 'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)', (role_id, permission_id))
    organization_id = _execute(connection, "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,'Organization','ACTIVE')", (tenant_id, f'ORG-{uuid4().hex[:12]}'))
    location_id = _execute(connection, "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,%s,'Location','America/Mexico_City','ACTIVE')", (tenant_id, organization_id, f'LOC-{uuid4().hex[:12]}'))
    resource_id = _execute(connection, "INSERT INTO resources (tenant_id,location_id,code,name,resource_type,status) VALUES (%s,%s,%s,'Table','TABLE','ACTIVE')", (tenant_id, location_id, f'T-{uuid4().hex[:12]}'))
    return Scope(tenant_id, organization_id, location_id, resource_id, email)


def _headers(client: TestClient, scope: Scope) -> dict[str, str]:
    response = client.post('/auth/login', json={'email': scope.email, 'password': PASSWORD})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _accepted_order(client: TestClient, connection, scope: Scope, *, name='Burger', amount='99.90') -> tuple[int, int, int]:
    staff = _headers(client, scope)
    opened = client.post(f'/resources/{scope.resource_id}/service-sessions', headers=staff, json={'party_size': 2})
    assert opened.status_code == 201, opened.text
    joined = client.post('/diner-sessions/join', json={
        'join_context_key': opened.json()['join_context_key'],
        'access_code': opened.json()['access_code'],
        'display_name': 'Diner',
    })
    assert joined.status_code == 201, joined.text
    diner = {'Authorization': f"Bearer {joined.json()['access_token']}"}
    product_id = _execute(connection, "INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,%s,'ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id, name))
    menu_id = _execute(connection, "INSERT INTO menus (tenant_id,organization_id,name,status) VALUES (%s,%s,'Menu','ACTIVE')", (scope.tenant_id, scope.organization_id))
    _execute(connection, "INSERT INTO menu_locations (tenant_id,organization_id,menu_id,location_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, menu_id, scope.location_id))
    section_id = _execute(connection, "INSERT INTO menu_sections (tenant_id,organization_id,menu_id,name,status) VALUES (%s,%s,%s,'Food','ACTIVE')", (scope.tenant_id, scope.organization_id, menu_id))
    _execute(connection, "INSERT INTO menu_items (tenant_id,organization_id,menu_id,section_id,product_id,status) VALUES (%s,%s,%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, menu_id, section_id, product_id))
    _execute(connection, "INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,%s,'MXN','ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id, product_id, scope.location_id, amount))
    draft = client.post('/diner/order-draft', headers=diner).json()
    added = client.post('/diner/order-draft/items', headers=diner, json={'product_id': product_id, 'quantity': '1', 'expected_version': draft['version']})
    assert added.status_code == 201, added.text
    preview = client.get('/diner/checkout-preview', headers=diner).json()
    accepted = client.post('/diner/order/confirm', headers={**diner, 'Idempotency-Key': uuid4().hex}, json={
        'expected_draft_version': preview['draft_version'],
        'expected_commercial_fingerprint': preview['commercial_fingerprint'],
    })
    assert accepted.status_code == 201, accepted.text
    return accepted.json()['id'], product_id, opened.json()['id']


def _configure(connection, scope: Scope, product_id: int, *, recovery=True, stable=True) -> MockPosAdapter:
    _execute(connection, "INSERT INTO location_preparation_configurations (tenant_id,organization_id,location_id,preparation_owner) VALUES (%s,%s,%s,'EXTERNAL_POS')", (scope.tenant_id, scope.organization_id, scope.location_id))
    _execute(connection, 'INSERT INTO product_external_mappings (tenant_id,product_id,connector_key,external_product_id) VALUES (%s,%s,%s,%s)', (scope.tenant_id, product_id, CONNECTOR, 'product-001'))
    _execute(connection, "INSERT INTO location_pos_connections (tenant_id,organization_id,location_id,connector_key,external_location_id,status,active_slot,stable_replay_supported,recovery_supported) VALUES (%s,%s,%s,%s,'location-001','ACTIVE',1,%s,%s)", (scope.tenant_id, scope.organization_id, scope.location_id, CONNECTOR, stable, recovery))
    return MockPosAdapter(build_mock_pos_dataset(tenant_id=scope.tenant_id, connector_key=CONNECTOR, location_ids=(scope.location_id, scope.location_id + 1_000_000)))


def _accepted_complex_order(
    client: TestClient, connection, scope: Scope, *, parent_quantity='1', fixed_quantity='1'
):
    staff = _headers(client, scope)
    opened = client.post(f'/resources/{scope.resource_id}/service-sessions', headers=staff, json={'party_size': 2}).json()
    joined = client.post('/diner-sessions/join', json={
        'join_context_key': opened['join_context_key'], 'access_code': opened['access_code'],
        'display_name': 'Diner',
    }).json()
    diner = {'Authorization': f"Bearer {joined['access_token']}"}
    parent = _execute(connection, "INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,'Combo','ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id))
    fixed = _execute(connection, "INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,'Fries','ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id))
    option_product = _execute(connection, "INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,'Cola','ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id))
    menu = _execute(connection, "INSERT INTO menus (tenant_id,organization_id,name,status) VALUES (%s,%s,'Menu','ACTIVE')", (scope.tenant_id, scope.organization_id))
    _execute(connection, "INSERT INTO menu_locations (tenant_id,organization_id,menu_id,location_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, menu, scope.location_id))
    section = _execute(connection, "INSERT INTO menu_sections (tenant_id,organization_id,menu_id,name,status) VALUES (%s,%s,%s,'Food','ACTIVE')", (scope.tenant_id, scope.organization_id, menu))
    _execute(connection, "INSERT INTO menu_items (tenant_id,organization_id,menu_id,section_id,product_id,status) VALUES (%s,%s,%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, menu, section, parent))
    _execute(connection, "INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,150,'MXN','ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id, parent, scope.location_id))
    composition = _execute(connection, "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, parent))
    _execute(connection, "INSERT INTO product_components (tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,%s,0,'ACTIVE')", (scope.tenant_id, scope.organization_id, composition, fixed, fixed_quantity))
    group = _execute(connection, "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Drink',1,1,0,'ACTIVE')", (scope.tenant_id, scope.organization_id, composition))
    option = _execute(connection, "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')", (scope.tenant_id, scope.organization_id, group, option_product))
    promotion = _execute(connection, "INSERT INTO promotions (tenant_id,organization_id,name,promotion_type,benefit_value,currency,starts_at,ends_at,applies_to_all_locations,is_combinable,priority,status,source) VALUES (%s,%s,'Combo offer','PERCENTAGE_DISCOUNT',10,NULL,CURRENT_TIMESTAMP - INTERVAL 1 HOUR,CURRENT_TIMESTAMP + INTERVAL 1 HOUR,1,0,1,'ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id))
    _execute(connection, "INSERT INTO promotion_products (tenant_id,organization_id,promotion_id,product_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, promotion, parent))
    draft = client.post('/diner/order-draft', headers=diner).json()
    added = client.post('/diner/order-draft/items', headers=diner, json={'product_id': parent, 'quantity': parent_quantity, 'expected_version': draft['version']}).json()
    selected = client.put(f"/diner/order-draft/items/{added['items'][0]['item_id']}/choice-groups/{group}", headers=diner, json={'option_ids': [option], 'expected_version': added['version']})
    assert selected.status_code == 200, selected.text
    preview = client.get('/diner/checkout-preview', headers=diner).json()
    accepted = client.post('/diner/order/confirm', headers={**diner, 'Idempotency-Key': uuid4().hex}, json={'expected_draft_version': preview['draft_version'], 'expected_commercial_fingerprint': preview['commercial_fingerprint']})
    assert accepted.status_code == 201, accepted.text
    return accepted.json()['id'], parent, fixed, option_product, promotion


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def test_success_is_stable_idempotent_attributed_and_concurrency_safe(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    adapter = _configure(connection, scope, product_id)
    initial_order_count = len(adapter._orders)
    client.app.state.pos_adapters[CONNECTOR] = adapter
    headers = _headers(client, scope)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(f'/restaurant-orders/{order_id}/pos-submission', headers=headers), range(2)))
    assert {response.status_code for response in responses} == {200}
    assert {response.json()['id'] for response in responses}.__len__() == 1
    bodies = [response.json() for response in responses]
    assert {body['state'] for body in bodies}.issubset({'IN_PROGRESS', 'SUCCEEDED'})
    body = next(body for body in bodies if body['state'] == 'SUCCEEDED')
    assert body['idempotency_key'].startswith(f'pos-create-v1:{scope.tenant_id}:{order_id}:')
    assert len(body['request_fingerprint']) == 64
    assert body['attempts'][0]['actor_type'] == 'EMPLOYEE'
    assert body['attempts'][0]['actor_membership_id'] is not None
    replay = client.post(
        f'/restaurant-orders/{order_id}/pos-submission',
        headers=headers,
        json={'actor_membership_id': 9_999_999, 'actor_type': 'SYSTEM'},
    )
    assert replay.status_code == 200 and replay.json()['external_order_id'] == body['external_order_id']
    assert replay.json()['attempts'][0]['actor_membership_id'] == body['attempts'][0]['actor_membership_id']
    assert len(adapter._orders) == initial_order_count + 1


def test_active_claim_returns_in_progress_without_a_second_network_call(client, sql_connection):
    class BlockingAdapter(MockPosAdapter):
        def __init__(self, dataset):
            super().__init__(dataset)
            self.entered = Event()
            self.release = Event()

        async def create_order(self, *args, **kwargs):
            self.entered.set()
            assert await asyncio.to_thread(self.release.wait, 10)
            return await super().create_order(*args, **kwargs)

    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    configured = _configure(connection, scope, product_id)
    adapter = BlockingAdapter(configured.dataset)
    client.app.state.pos_adapters[CONNECTOR] = adapter
    headers = _headers(client, scope)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, f'/restaurant-orders/{order_id}/pos-submission', headers=headers)
        assert adapter.entered.wait(10)
        second = pool.submit(client.post, f'/restaurant-orders/{order_id}/pos-submission', headers=headers)
        concurrent = second.result(timeout=10)
        assert concurrent.status_code == 200 and concurrent.json()['state'] == 'IN_PROGRESS'
        assert adapter.create_history == []
        adapter.release.set()
        completed = first.result(timeout=10)
    assert completed.status_code == 200 and completed.json()['state'] == 'SUCCEEDED'
    assert len(adapter.create_history) == 1


def test_retry_uses_frozen_accepted_values_and_mapping(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope, name='Original Burger', amount='99.90')
    adapter = _configure(connection, scope, product_id)
    adapter.failure_mode = MockPosFailureMode.POS_UNAVAILABLE
    client.app.state.pos_adapters[CONNECTOR] = adapter
    headers = _headers(client, scope)
    failed = client.post(f'/restaurant-orders/{order_id}/pos-submission', headers=headers)
    assert failed.status_code == 200 and failed.json()['state'] == 'RETRYABLE_FAILURE'

    connection.cursor().execute("UPDATE products SET name='Mutated Product' WHERE id=%s", (product_id,))
    connection.cursor().execute('UPDATE product_prices SET amount=777 WHERE product_id=%s', (product_id,))
    connection.cursor().execute("UPDATE product_external_mappings SET external_product_id='product-002' WHERE tenant_id=%s AND product_id=%s", (scope.tenant_id, product_id))
    adapter.failure_mode = MockPosFailureMode.NONE
    retried = client.post(f'/restaurant-orders/{order_id}/pos-submission/retry', headers=headers)
    assert retried.status_code == 200 and retried.json()['state'] == 'SUCCEEDED'
    request = adapter.create_history[-1]
    assert request.items[0].name == 'Original Burger'
    assert request.items[0].unit_price == Decimal('99.90')
    assert request.items[0].product_external_id == 'product-001'
    assert [attempt['attempt_type'] for attempt in retried.json()['attempts']] == ['CREATE', 'RETRY']


def test_components_choices_and_promotions_reconstruct_from_accepted_snapshot(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, parent, fixed, option, promotion = _accepted_complex_order(client, connection, scope)
    adapter = _configure(connection, scope, parent)
    _execute(connection, 'INSERT INTO product_external_mappings (tenant_id,product_id,connector_key,external_product_id) VALUES (%s,%s,%s,%s)', (scope.tenant_id, fixed, CONNECTOR, 'product-002'))
    _execute(connection, 'INSERT INTO product_external_mappings (tenant_id,product_id,connector_key,external_product_id) VALUES (%s,%s,%s,%s)', (scope.tenant_id, option, CONNECTOR, 'product-003'))
    adapter.failure_mode = MockPosFailureMode.POS_UNAVAILABLE
    client.app.state.pos_adapters[CONNECTOR] = adapter
    headers = _headers(client, scope)
    assert client.post(f'/restaurant-orders/{order_id}/pos-submission', headers=headers).json()['state'] == 'RETRYABLE_FAILURE'
    connection.cursor().execute("UPDATE products SET name=CONCAT(name,' changed') WHERE id IN (%s,%s,%s)", (parent, fixed, option))
    connection.cursor().execute("UPDATE promotions SET name='Changed offer',benefit_value=20 WHERE id=%s", (promotion,))
    adapter.failure_mode = MockPosFailureMode.NONE
    result = client.post(f'/restaurant-orders/{order_id}/pos-submission/retry', headers=headers)
    assert result.status_code == 200 and result.json()['state'] == 'SUCCEEDED'
    request = adapter.create_history[-1]
    assert request.items[0].name == 'Combo'
    assert [(value.kind, value.name, value.product_external_id) for value in request.items[0].components] == [
        ('FIXED', 'Fries', 'product-002'), ('CHOICE', 'Cola', 'product-003')
    ]
    assert [(value.name, value.calculated_discount) for value in request.items[0].promotions] == [
        ('Combo offer', Decimal('15.0000'))
    ]


def test_uncertain_result_recovers_without_duplicate_external_order(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    adapter = _configure(connection, scope, product_id)
    initial_order_count = len(adapter._orders)
    adapter.failure_mode = MockPosFailureMode.ORDER_UNCERTAIN_ONCE
    client.app.state.pos_adapters[CONNECTOR] = adapter
    headers = _headers(client, scope)
    uncertain = client.post(f'/restaurant-orders/{order_id}/pos-submission', headers=headers)
    assert uncertain.status_code == 200 and uncertain.json()['state'] == 'UNCERTAIN'
    recovered = client.post(f'/restaurant-orders/{order_id}/pos-submission/recover', headers=headers)
    assert recovered.status_code == 200 and recovered.json()['state'] == 'SUCCEEDED'
    assert adapter.recovery_calls == 1
    assert len(adapter._orders) == initial_order_count + 1
    assert [value['result'] for value in recovered.json()['attempts']] == ['UNCERTAIN', 'SUCCEEDED']


def test_expired_post_call_claim_is_recovered_and_old_fence_cannot_overwrite(
    client, sql_connection, integration_settings
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    adapter = _configure(connection, scope, product_id)
    adapter.failure_mode = MockPosFailureMode.ORDER_UNCERTAIN_ONCE
    client.app.state.pos_adapters[CONNECTOR] = adapter
    headers = _headers(client, scope)
    uncertain = client.post(f'/restaurant-orders/{order_id}/pos-submission', headers=headers).json()
    assert uncertain['state'] == 'UNCERTAIN'
    stale_token = str(uuid4())
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM tenant_memberships WHERE tenant_id=%s', (scope.tenant_id,))
        membership_id = int(cursor.fetchone()['id'])
        cursor.execute(
            "UPDATE pos_order_submissions SET state='IN_PROGRESS',claim_token=%s,"
            'claim_expires_at=CURRENT_TIMESTAMP - INTERVAL 1 MINUTE,attempt_count=2 WHERE id=%s',
            (stale_token, uncertain['id']),
        )
        cursor.execute(
            "INSERT INTO pos_order_submission_attempts "
            '(tenant_id,submission_id,attempt_sequence,attempt_type,claim_token,actor_type,'
            'actor_membership_id,correlation_id,started_at,result) '
            "VALUES (%s,%s,2,'CREATE',%s,'EMPLOYEE',%s,'crash-window',"
            "CURRENT_TIMESTAMP - INTERVAL 1 MINUTE,'IN_PROGRESS')",
            (scope.tenant_id, uncertain['id'], stale_token, membership_id),
        )
    recovered = client.post(f'/restaurant-orders/{order_id}/pos-submission', headers=headers)
    assert recovered.status_code == 200 and recovered.json()['state'] == 'SUCCEEDED'
    assert [value['attempt_type'] for value in recovered.json()['attempts']] == [
        'CREATE', 'CREATE', 'STALE_RECOVERY'
    ]

    async def attempt_stale_finish():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                return await submission_service._finish(
                    db,
                    tenant_id=scope.tenant_id,
                    submission_id=uncertain['id'],
                    token=stale_token,
                    state='ACTION_REQUIRED',
                    error_kind='MAPPING',
                    error_message='late stale worker',
                )
        finally:
            await manager.dispose()

    winner = asyncio.run(attempt_stale_finish())
    assert winner.state == 'SUCCEEDED'
    read = client.get(f'/restaurant-orders/{order_id}/pos-submission', headers=headers)
    assert read.json()['state'] == 'SUCCEEDED'


def test_rejection_is_terminal_and_retry_is_forbidden(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    adapter = _configure(connection, scope, product_id)
    adapter.failure_mode = MockPosFailureMode.ORDER_REJECTED
    client.app.state.pos_adapters[CONNECTOR] = adapter
    headers = _headers(client, scope)
    rejected = client.post(f'/restaurant-orders/{order_id}/pos-submission', headers=headers)
    assert rejected.status_code == 200 and rejected.json()['state'] == 'REJECTED'
    assert client.post(f'/restaurant-orders/{order_id}/pos-submission/retry', headers=headers).status_code == 409


def test_ambiguous_mapping_persists_action_required_without_external_call(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, _ = _accepted_order(client, connection, scope)
    adapter = _configure(connection, scope, product_id)
    initial_order_count = len(adapter._orders)
    _execute(
        connection,
        'INSERT INTO product_external_mappings (tenant_id,product_id,connector_key,external_product_id) VALUES (%s,%s,%s,%s)',
        (scope.tenant_id, product_id, CONNECTOR, 'product-002'),
    )
    client.app.state.pos_adapters[CONNECTOR] = adapter
    response = client.post(f'/restaurant-orders/{order_id}/pos-submission', headers=_headers(client, scope))
    assert response.status_code == 200 and response.json()['state'] == 'ACTION_REQUIRED'
    assert response.json()['last_error_kind'] == 'MAPPING'
    assert len(adapter._orders) == initial_order_count


def test_permissions_scope_and_closed_service_do_not_invalidate_accepted_order(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    order_id, product_id, service_id = _accepted_order(client, connection, scope)
    adapter = _configure(connection, scope, product_id)
    client.app.state.pos_adapters[CONNECTOR] = adapter
    headers = _headers(client, scope)
    closed = client.post(f'/restaurant-service-sessions/{service_id}/close', headers=headers)
    assert closed.status_code == 200, closed.text
    submitted = client.post(f'/restaurant-orders/{order_id}/pos-submission', headers=headers)
    assert submitted.status_code == 200 and submitted.json()['state'] == 'SUCCEEDED'

    denied_scope = _scope(connection, f'{prefix}-denied', include_pos_permissions=False)
    denied_headers = _headers(client, denied_scope)
    denied_calls = (
        client.get(f'/restaurant-orders/{order_id}/pos-submission', headers=denied_headers),
        client.post(f'/restaurant-orders/{order_id}/pos-submission', headers=denied_headers),
        client.post(f'/restaurant-orders/{order_id}/pos-submission/retry', headers=denied_headers),
        client.post(f'/restaurant-orders/{order_id}/pos-submission/recover', headers=denied_headers),
    )
    assert [response.status_code for response in denied_calls] == [403, 403, 403, 403]
