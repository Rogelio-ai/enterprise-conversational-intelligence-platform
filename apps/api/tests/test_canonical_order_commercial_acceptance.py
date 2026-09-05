from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from uuid import uuid4

import pymysql
import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import create_app


PASSWORD = 'Test Password 123!'


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


def _scope(connection, prefix: str, *, order_read: bool = True) -> Scope:
    tenant_id = _execute(connection, "INSERT INTO tenants (name,slug,status) VALUES ('Order Tenant',%s,'ACTIVE')", (prefix,))
    email = f'{prefix}@example.test'
    user_id = _execute(connection, "INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,'Staff','ACTIVE')", (email, hash_password(PASSWORD)))
    membership_id = _execute(connection, "INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,'ACTIVE')", (tenant_id, user_id))
    role_id = _execute(connection, "INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,'Role','ACTIVE')", (tenant_id, f'ORDER_{uuid4().hex}'))
    _execute(connection, 'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)', (tenant_id, membership_id, role_id))
    permissions = [
        'restaurant_service.read', 'restaurant_service.manage',
        'order_draft.read', 'order_draft.manage',
        'conversation.read', 'conversation.manage',
    ]
    if order_read:
        permissions.append('restaurant_order.read')
    for code in permissions:
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
        _execute(connection, 'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)', (role_id, permission_id))
    organization_id = _execute(connection, "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,'Organization','ACTIVE')", (tenant_id, f'ORG-{uuid4().hex[:12]}'))
    location_id = _execute(connection, "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,country_code,status) VALUES (%s,%s,%s,'Location','America/Mexico_City','MX','ACTIVE')", (tenant_id, organization_id, f'LOC-{uuid4().hex[:12]}'))
    resource_id = _execute(connection, "INSERT INTO resources (tenant_id,location_id,code,name,resource_type,status) VALUES (%s,%s,%s,'Table','TABLE','ACTIVE')", (tenant_id, location_id, f'T-{uuid4().hex[:12]}'))
    return Scope(tenant_id, organization_id, location_id, resource_id, email)


def _staff_headers(client: TestClient, scope: Scope) -> dict[str, str]:
    login = client.post('/auth/login', json={'email': scope.email, 'password': PASSWORD})
    assert login.status_code == 200
    return {'Authorization': f"Bearer {login.json()['access_token']}"}


def _open_and_join(client: TestClient, scope: Scope, *, name: str = 'Diner') -> tuple[dict, dict[str, str]]:
    opened = client.post(
        f'/resources/{scope.resource_id}/service-sessions',
        headers=_staff_headers(client, scope),
        json={'party_size': 4},
    )
    assert opened.status_code == 201, opened.text
    joined = client.post('/diner-sessions/join', json={
        'join_context_key': opened.json()['join_context_key'],
        'access_code': opened.json()['access_code'],
        'display_name': name,
    })
    assert joined.status_code == 201, joined.text
    return opened.json(), {'Authorization': f"Bearer {joined.json()['access_token']}"}


def _product(connection, scope: Scope, *, name: str = 'Hamburguesa Especial', amount: str = '150') -> int:
    product_id = _execute(connection, "INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,%s,'ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id, name))
    classification = f'PRODUCT-{product_id}'
    connection.cursor().execute(
        'UPDATE products SET tax_classification_code=%s WHERE id=%s',
        (classification, product_id),
    )
    _execute(
        connection,
        "INSERT INTO restaurant_tax_rules (tenant_id,organization_id,location_id,"
        "tax_classification_code,jurisdiction_code,tax_category,tax_treatment,tax_effect,tax_rate,"
        "calculation_policy,rounding_policy,effective_from,effective_to,status) "
        "VALUES (%s,%s,NULL,%s,'TEST-JURISDICTION','SALES_TAX','TAXABLE','TRANSFERRED',0.160000,"
        "'INCLUDED_PRICE_SINGLE_TAX','DECIMAL_4_HALF_UP',CURRENT_TIMESTAMP - INTERVAL 1 DAY,NULL,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, classification),
    )
    _execute(
        connection,
        "INSERT INTO product_fiscal_classifications (tenant_id,organization_id,product_id,"
        "fiscal_jurisdiction_code,product_classification_scheme,"
        "product_classification_code,unit_classification_scheme,unit_classification_code,"
        "effective_from,effective_to,status) VALUES (%s,%s,%s,'MX','TEST-PRODUCT-SCHEME',"
        "%s,'TEST-UNIT-SCHEME','EACH',CURRENT_TIMESTAMP - INTERVAL 1 DAY,NULL,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, product_id, f'FISCAL-{product_id}'),
    )
    menu_id = _execute(connection, "INSERT INTO menus (tenant_id,organization_id,name,status) VALUES (%s,%s,'Menu','ACTIVE')", (scope.tenant_id, scope.organization_id))
    _execute(connection, "INSERT INTO menu_locations (tenant_id,organization_id,menu_id,location_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, menu_id, scope.location_id))
    section_id = _execute(connection, "INSERT INTO menu_sections (tenant_id,organization_id,menu_id,name,status) VALUES (%s,%s,%s,'Food','ACTIVE')", (scope.tenant_id, scope.organization_id, menu_id))
    _execute(connection, "INSERT INTO menu_items (tenant_id,organization_id,menu_id,section_id,product_id,status) VALUES (%s,%s,%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, menu_id, section_id, product_id))
    _execute(connection, "INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,%s,'MXN','ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id, product_id, scope.location_id, amount))
    return product_id


def _preview(client: TestClient, diner_headers: dict[str, str], product_id: int) -> dict:
    draft = client.post('/diner/order-draft', headers=diner_headers)
    assert draft.status_code == 201, draft.text
    added = client.post('/diner/order-draft/items', headers=diner_headers, json={
        'product_id': product_id, 'quantity': '1', 'expected_version': draft.json()['version']
    })
    assert added.status_code == 201, added.text
    preview = client.get('/diner/checkout-preview', headers=diner_headers)
    assert preview.status_code == 200, preview.text
    return preview.json()


def _confirm(client: TestClient, diner_headers: dict[str, str], preview: dict, key: str):
    return client.post('/diner/order/confirm', headers={**diner_headers, 'Idempotency-Key': key}, json={
        'expected_draft_version': preview['draft_version'],
        'expected_commercial_fingerprint': preview['commercial_fingerprint'],
    })


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def test_three_cycles_idempotency_freshness_snapshot_and_reads(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope)

    preview1 = _preview(client, diner_headers, product_id)
    connection.cursor().execute("UPDATE products SET name='Hamburguesa Especial de la Casa' WHERE id=%s", (product_id,))
    first = _confirm(client, diner_headers, preview1, 'Case-Sensitive-Key-1')
    assert first.status_code == 201, first.text
    assert first.json()['items'][0]['product_name'] == 'Hamburguesa Especial de la Casa'
    replay = _confirm(client, diner_headers, preview1, 'Case-Sensitive-Key-1')
    assert replay.status_code == 200 and replay.json()['id'] == first.json()['id']

    preview2 = _preview(client, diner_headers, product_id)
    connection.cursor().execute('UPDATE product_prices SET amount=151 WHERE product_id=%s AND location_id=%s', (product_id, scope.location_id))
    stale = _confirm(client, diner_headers, preview2, 'Case-Sensitive-Key-2')
    assert stale.status_code == 409
    fresh2 = client.get('/diner/checkout-preview', headers=diner_headers).json()
    second = _confirm(client, diner_headers, fresh2, 'Case-Sensitive-Key-2')
    assert second.status_code == 201, second.text

    preview3 = _preview(client, diner_headers, product_id)
    reused = _confirm(client, diner_headers, preview3, 'Case-Sensitive-Key-1')
    assert reused.status_code == 409
    third = _confirm(client, diner_headers, preview3, 'case-sensitive-key-1')
    assert third.status_code == 201, third.text

    diner_orders = client.get('/diner/orders', headers=diner_headers)
    assert diner_orders.status_code == 200
    assert [value['id'] for value in diner_orders.json()] == [first.json()['id'], second.json()['id'], third.json()['id']]
    staff_orders = client.get('/restaurant-orders', headers=_staff_headers(client, scope))
    assert staff_orders.status_code == 200 and len(staff_orders.json()) == 3
    with connection.cursor() as cursor:
        cursor.execute('SELECT status,current_slot,terminal_at FROM order_drafts WHERE conversation_id=(SELECT conversation_id FROM diner_sessions WHERE tenant_id=%s LIMIT 1) ORDER BY id', (scope.tenant_id,))
        drafts = cursor.fetchall()
    assert len(drafts) == 3
    assert all(value['status'] == 'ACCEPTED' and value['current_slot'] is None and value['terminal_at'] is not None for value in drafts)


def test_double_confirm_same_key_creates_exactly_one_order(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    preview = _preview(client, diner_headers, _product(connection, scope, name='Coffee', amount='50'))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: _confirm(client, diner_headers, preview, 'concurrent-key'), range(2)))
    assert sorted(value.status_code for value in responses) == [200, 201]
    assert len({value.json()['id'] for value in responses}) == 1
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_orders WHERE tenant_id=%s', (scope.tenant_id,))
        assert cursor.fetchone()['count'] == 1


def test_concurrent_different_keys_and_lazy_next_draft_creation(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope, name='Tea', amount='45')
    preview = _preview(client, diner_headers, product_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(
            lambda key: _confirm(client, diner_headers, preview, key),
            ('different-key-a', 'different-key-b'),
        ))
    assert sorted(value.status_code for value in responses) == [201, 409]

    with ThreadPoolExecutor(max_workers=2) as pool:
        drafts = list(pool.map(
            lambda _: client.post('/diner/order-draft', headers=diner_headers), range(2)
        ))
    assert [value.status_code for value in drafts] == [201, 201]
    assert len({value.json()['draft_id'] for value in drafts}) == 1
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM order_drafts WHERE tenant_id=%s AND status='OPEN' AND current_slot=1", (scope.tenant_id,))
        assert cursor.fetchone()['count'] == 1


def test_confirm_vs_mutation_has_one_serialized_winner(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    preview = _preview(client, diner_headers, _product(connection, scope, name='Juice', amount='60'))
    item_id = preview['lines'][0]['draft_item_id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        confirmation = pool.submit(_confirm, client, diner_headers, preview, 'mutation-race-key')
        mutation = pool.submit(
            client.put,
            f'/diner/order-draft/items/{item_id}/quantity',
            headers=diner_headers,
            json={'quantity': '2', 'expected_version': preview['draft_version']},
        )
        confirm_response = confirmation.result()
        mutation_response = mutation.result()
    assert sorted((confirm_response.status_code, mutation_response.status_code)) in ([200, 409], [201, 409])
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) AS count FROM restaurant_orders WHERE tenant_id=%s', (scope.tenant_id,))
        count = cursor.fetchone()['count']
    assert count == (1 if confirm_response.status_code == 201 else 0)


def test_end_is_blocked_when_it_would_orphan_accepted_consumption(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope, name='Water', amount='30')
    preview = _preview(client, diner_headers, product_id)
    accepted = _confirm(client, diner_headers, preview, 'accepted-key')
    assert accepted.status_code == 201
    next_draft = client.post('/diner/order-draft', headers=diner_headers)
    assert next_draft.status_code == 201
    ended = client.post('/diner-session/end', headers=diner_headers)
    assert ended.status_code == 409
    assert ended.json()['error']['code'] == 'TABLE_NOT_ELIGIBLE_FOR_CLOSURE'
    with connection.cursor() as cursor:
        cursor.execute('SELECT status,current_slot FROM order_drafts WHERE tenant_id=%s ORDER BY id', (scope.tenant_id,))
        rows = cursor.fetchall()
    assert [value['status'] for value in rows] == ['ACCEPTED', 'OPEN']
    assert rows[0]['current_slot'] is None and rows[1]['current_slot'] == 1


@pytest.mark.parametrize('closure', ['conversation', 'service'])
def test_lifecycle_closure_abandons_only_current_draft(client, sql_connection, closure):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    opened, diner_headers = _open_and_join(client, scope)
    current = client.post('/diner/order-draft', headers=diner_headers)
    assert current.status_code == 201
    if closure == 'conversation':
        response = client.patch(
            f"/conversations/{current.json()['conversation_id']}",
            headers=_staff_headers(client, scope),
            json={'status': 'CLOSED'},
        )
    else:
        response = client.post(
            f"/restaurant-service-sessions/{opened['id']}/close",
            headers=_staff_headers(client, scope),
        )
    assert response.status_code == 200, response.text
    with connection.cursor() as cursor:
        cursor.execute('SELECT status,current_slot,terminal_at FROM order_drafts WHERE id=%s', (current.json()['draft_id'],))
        row = cursor.fetchone()
    assert row['status'] == 'ABANDONED' and row['current_slot'] is None and row['terminal_at'] is not None


def test_database_current_slot_and_one_order_per_draft_invariants(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    draft = client.post('/diner/order-draft', headers=diner_headers).json()
    with pytest.raises(pymysql.err.IntegrityError):
        _execute(connection, "INSERT INTO order_drafts (tenant_id,organization_id,location_id,conversation_id,version,status,current_slot) VALUES (%s,%s,%s,%s,1,'OPEN',1)", (scope.tenant_id, scope.organization_id, scope.location_id, draft['conversation_id']))


def test_complex_configuration_and_promotion_are_immutable_snapshots(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    parent_id = _product(connection, scope, name='Combo', amount='150')
    with connection.cursor() as cursor:
        cursor.execute('SELECT tax_classification_code FROM products WHERE id=%s', (parent_id,))
        classification = cursor.fetchone()['tax_classification_code']
    fixed_id = _execute(connection, "INSERT INTO products (tenant_id,organization_id,name,tax_classification_code,status,source) VALUES (%s,%s,'Fries',%s,'ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id, classification))
    option_product_id = _execute(connection, "INSERT INTO products (tenant_id,organization_id,name,tax_classification_code,status,source) VALUES (%s,%s,'Cola',%s,'ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id, classification))
    composition_id = _execute(connection, "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, parent_id))
    _execute(connection, "INSERT INTO product_components (tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')", (scope.tenant_id, scope.organization_id, composition_id, fixed_id))
    group_id = _execute(connection, "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Drink',1,1,0,'ACTIVE')", (scope.tenant_id, scope.organization_id, composition_id))
    option_id = _execute(connection, "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')", (scope.tenant_id, scope.organization_id, group_id, option_product_id))
    promotion_id = _execute(connection, "INSERT INTO promotions (tenant_id,organization_id,name,promotion_type,benefit_value,currency,starts_at,ends_at,applies_to_all_locations,is_combinable,priority,status,source) VALUES (%s,%s,'Combo offer','PERCENTAGE_DISCOUNT',10,NULL,CURRENT_TIMESTAMP - INTERVAL 1 HOUR,CURRENT_TIMESTAMP + INTERVAL 1 HOUR,1,0,1,'ACTIVE','PLATFORM')", (scope.tenant_id, scope.organization_id))
    _execute(connection, "INSERT INTO promotion_products (tenant_id,organization_id,promotion_id,product_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')", (scope.tenant_id, scope.organization_id, promotion_id, parent_id))

    draft = client.post('/diner/order-draft', headers=diner_headers).json()
    item = client.post('/diner/order-draft/items', headers=diner_headers, json={'product_id': parent_id, 'quantity': '1', 'expected_version': draft['version']}).json()
    selected = client.put(
        f"/diner/order-draft/items/{item['items'][0]['item_id']}/choice-groups/{group_id}",
        headers=diner_headers,
        json={'option_ids': [option_id], 'expected_version': item['version']},
    )
    assert selected.status_code == 200 and selected.json()['readiness'] == 'READY'
    preview = client.get('/diner/checkout-preview', headers=diner_headers).json()
    accepted = _confirm(client, diner_headers, preview, 'complex-snapshot-key')
    assert accepted.status_code == 201, accepted.text
    body = accepted.json()
    assert [(value['kind'], value['product_name']) for value in body['items'][0]['components']] == [('FIXED', 'Fries'), ('CHOICE', 'Cola')]
    assert body['items'][0]['promotions'][0]['promotion_name'] == 'Combo offer'
    assert body['items'][0]['promotions'][0]['calculated_discount'] == '15.0000'

    connection.cursor().execute("UPDATE products SET name=CONCAT(name,' changed') WHERE id IN (%s,%s,%s)", (parent_id, fixed_id, option_product_id))
    connection.cursor().execute("UPDATE promotions SET name='Changed offer',benefit_value=20 WHERE id=%s", (promotion_id,))
    connection.cursor().execute('UPDATE product_prices SET amount=999 WHERE product_id=%s', (parent_id,))
    historical = client.get(f"/diner/orders/{body['id']}", headers=diner_headers)
    assert historical.status_code == 200
    stored = historical.json()
    assert stored['items'][0]['product_name'] == 'Combo'
    assert [(value['kind'], value['product_name']) for value in stored['items'][0]['components']] == [('FIXED', 'Fries'), ('CHOICE', 'Cola')]
    assert stored['items'][0]['promotions'][0]['promotion_name'] == 'Combo offer'
    assert stored['payable_total'] == body['payable_total']
