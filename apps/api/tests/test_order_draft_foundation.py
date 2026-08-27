from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import DatabaseManager
from app.main import create_app
from app.restaurant.orders import errors, service


PASSWORD = 'Test Password 123!'


@dataclass(frozen=True)
class Scope:
    tenant_id: int
    organization_id: int
    location_id: int
    conversation_id: int
    email: str


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _scope(
    connection,
    prefix: str,
    *,
    permissions: tuple[str, ...] = ('order_draft.read', 'order_draft.manage'),
    with_location: bool = True,
) -> Scope:
    tenant_id = _execute(
        connection,
        "INSERT INTO tenants (name,slug,status) VALUES ('Draft Tenant',%s,'ACTIVE')",
        (prefix,),
    )
    email = f'{prefix}@example.test'
    user_id = _execute(
        connection,
        "INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,'User','ACTIVE')",
        (email, hash_password(PASSWORD)),
    )
    membership_id = _execute(
        connection,
        "INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,'ACTIVE')",
        (tenant_id, user_id),
    )
    role_id = _execute(
        connection,
        "INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,'Role','ACTIVE')",
        (tenant_id, f'DRAFT_{uuid4().hex}'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',
        (tenant_id, membership_id, role_id),
    )
    for code in permissions:
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
        _execute(
            connection,
            'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
            (role_id, permission_id),
        )
    organization_id = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,'Organization','ACTIVE')",
        (tenant_id, f'ORG-{uuid4().hex[:12]}'),
    )
    location_id = _execute(
        connection,
        "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) "
        "VALUES (%s,%s,%s,'Location','America/Mexico_City','ACTIVE')",
        (tenant_id, organization_id, f'LOC-{uuid4().hex[:12]}'),
    )
    conversation_id = _execute(
        connection,
        "INSERT INTO conversations "
        "(tenant_id,organization_id,location_id,channel,status,next_message_sequence) "
        "VALUES (%s,%s,%s,'MOBILE_APP','ACTIVE',1)",
        (tenant_id, organization_id, location_id if with_location else None),
    )
    return Scope(tenant_id, organization_id, location_id, conversation_id, email)


def _product(connection, scope: Scope, name: str, *, status: str = 'ACTIVE') -> int:
    return _execute(
        connection,
        "INSERT INTO products (tenant_id,organization_id,name,status,source) "
        "VALUES (%s,%s,%s,%s,'PLATFORM')",
        (scope.tenant_id, scope.organization_id, name, status),
    )


def _expose(connection, scope: Scope, product_ids: tuple[int, ...]) -> tuple[int, tuple[int, ...]]:
    menu_id = _execute(
        connection,
        "INSERT INTO menus (tenant_id,organization_id,name,status) VALUES (%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, f'Menu-{uuid4().hex}'),
    )
    menu_location_id = _execute(
        connection,
        "INSERT INTO menu_locations (tenant_id,organization_id,menu_id,location_id,status) "
        "VALUES (%s,%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, menu_id, scope.location_id),
    )
    section_id = _execute(
        connection,
        "INSERT INTO menu_sections (tenant_id,organization_id,menu_id,name,status) "
        "VALUES (%s,%s,%s,'Section','ACTIVE')",
        (scope.tenant_id, scope.organization_id, menu_id),
    )
    item_ids = tuple(
        _execute(
            connection,
            "INSERT INTO menu_items "
            "(tenant_id,organization_id,menu_id,section_id,product_id,status) "
            "VALUES (%s,%s,%s,%s,%s,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, menu_id, section_id, product_id),
        )
        for product_id in product_ids
    )
    return menu_location_id, item_ids


def _composition(connection, scope: Scope, parent_id: int):
    fixed_id = _product(connection, scope, 'Fixed component')
    option_ids = tuple(_product(connection, scope, name) for name in ('Coffee', 'Juice', 'Water'))
    composition_id = _execute(
        connection,
        "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) "
        "VALUES (%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, parent_id),
    )
    _execute(
        connection,
        "INSERT INTO product_components "
        "(tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) "
        "VALUES (%s,%s,%s,%s,1.5000,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id, fixed_id),
    )
    group_id = _execute(
        connection,
        "INSERT INTO product_choice_groups "
        "(tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) "
        "VALUES (%s,%s,%s,'Beverage',1,2,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id),
    )
    choice_option_ids = tuple(
        _execute(
            connection,
            "INSERT INTO product_choice_options "
            "(tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) "
            "VALUES (%s,%s,%s,%s,1.0000,%s,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, group_id, product_id, position),
        )
        for position, product_id in enumerate(option_ids)
    )
    return composition_id, fixed_id, group_id, choice_option_ids


def _headers(client: TestClient, scope: Scope) -> dict[str, str]:
    response = client.post('/auth/login', json={'email': scope.email, 'password': PASSWORD})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as test_client:
        yield test_client


def test_draft_creation_scope_empty_rbac_and_closed_lifecycle(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)

    created = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    )
    assert created.status_code == 201
    draft = created.json()
    assert draft == {
        'draft_id': draft['draft_id'],
        'tenant_id': scope.tenant_id,
        'organization_id': scope.organization_id,
        'location_id': scope.location_id,
        'conversation_id': scope.conversation_id,
        'version': 1,
        'readiness': 'EMPTY',
        'items': [],
    }
    repeated = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    )
    assert repeated.status_code == 201
    assert repeated.json()['draft_id'] == draft['draft_id']
    assert client.get(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).json() == draft
    assert client.get(f"/order-drafts/{draft['draft_id']}", headers=headers).json() == draft

    read_only = _scope(connection, f'{prefix}-read', permissions=('order_draft.read',))
    read_headers = _headers(client, read_only)
    assert client.get(f"/order-drafts/{draft['draft_id']}", headers=read_headers).status_code == 404
    assert client.post(
        f'/conversations/{read_only.conversation_id}/order-draft', headers=read_headers
    ).status_code == 403
    assert client.get(f"/order-drafts/{draft['draft_id']}").status_code == 401

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE conversations SET status='CLOSED',closed_at=CURRENT_TIMESTAMP WHERE id=%s",
            (scope.conversation_id,),
        )
    assert client.get(f"/order-drafts/{draft['draft_id']}", headers=headers).status_code == 200
    assert client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).status_code == 409
    assert client.post(
        f"/order-drafts/{draft['draft_id']}/items",
        headers=headers,
        json={'product_id': 999999, 'quantity': '1', 'expected_version': 1},
    ).status_code == 409


def test_draft_creation_requires_active_location_and_is_one_per_conversation(
    client, sql_connection
):
    connection, prefix = sql_connection
    no_location = _scope(connection, prefix, with_location=False)
    headers = _headers(client, no_location)
    response = client.post(
        f'/conversations/{no_location.conversation_id}/order-draft', headers=headers
    )
    assert response.status_code == 409

    with connection.cursor() as cursor:
        cursor.execute(
            'UPDATE conversations SET location_id=%s WHERE id=%s',
            (no_location.location_id, no_location.conversation_id),
        )
        cursor.execute('UPDATE locations SET status=\'INACTIVE\' WHERE id=%s', (no_location.location_id,))
    assert client.post(
        f'/conversations/{no_location.conversation_id}/order-draft', headers=headers
    ).status_code == 409
    with connection.cursor() as cursor:
        cursor.execute('UPDATE locations SET status=\'ACTIVE\' WHERE id=%s', (no_location.location_id,))
    first = client.post(
        f'/conversations/{no_location.conversation_id}/order-draft', headers=headers
    )
    assert first.status_code == 201
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM order_drafts WHERE tenant_id=%s AND conversation_id=%s',
            (no_location.tenant_id, no_location.conversation_id),
        )
        assert cursor.fetchone()['count'] == 1


@pytest.mark.parametrize('quantity', [1.0, '0', '-1', '1.00001', '1000000000000000'])
def test_item_quantity_boundary_rejects_invalid_values(client, sql_connection, quantity):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product_id = _product(connection, scope, 'Coffee')
    _expose(connection, scope, (product_id,))
    headers = _headers(client, scope)
    draft = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).json()
    response = client.post(
        f"/order-drafts/{draft['draft_id']}/items",
        headers=headers,
        json={'product_id': product_id, 'quantity': quantity, 'expected_version': 1},
    )
    assert response.status_code == 422
    assert client.get(f"/order-drafts/{draft['draft_id']}", headers=headers).json()['version'] == 1


def test_simple_items_mutations_ordering_no_merge_and_stale_version(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product_id = _product(connection, scope, 'Coffee')
    _expose(connection, scope, (product_id,))
    headers = _headers(client, scope)
    draft = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).json()
    first = client.post(
        f"/order-drafts/{draft['draft_id']}/items",
        headers=headers,
        json={'product_id': product_id, 'quantity': '1.2500', 'expected_version': 1},
    )
    assert first.status_code == 201
    first_value = first.json()
    assert first_value['version'] == 2
    assert first_value['readiness'] == 'READY'
    assert first_value['items'][0]['quantity'] == '1.2500'
    assert first_value['items'][0]['position'] == 0
    item_id = first_value['items'][0]['item_id']

    stale = client.post(
        f"/order-drafts/{draft['draft_id']}/items",
        headers=headers,
        json={'product_id': product_id, 'quantity': '1', 'expected_version': 1},
    )
    assert stale.status_code == 409
    second = client.post(
        f"/order-drafts/{draft['draft_id']}/items",
        headers=headers,
        json={'product_id': product_id, 'quantity': '1', 'expected_version': 2},
    )
    assert second.status_code == 201
    assert [(item['position'], item['product_id']) for item in second.json()['items']] == [
        (0, product_id),
        (1, product_id),
    ]
    assert len({item['item_id'] for item in second.json()['items']}) == 2

    changed = client.patch(
        f"/order-drafts/{draft['draft_id']}/items/{item_id}",
        headers=headers,
        json={'quantity': '2.5000', 'expected_version': 3},
    )
    assert changed.status_code == 200
    assert changed.json()['version'] == 4
    second_item_id = changed.json()['items'][1]['item_id']
    removed = client.delete(
        f"/order-drafts/{draft['draft_id']}/items/{second_item_id}",
        headers=headers,
        params={'expected_version': 4},
    )
    assert removed.status_code == 200
    assert removed.json()['version'] == 5
    assert [item['item_id'] for item in removed.json()['items']] == [item_id]


def test_add_rejects_nonorderable_inactive_and_inactive_composition(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    nonorderable = _product(connection, scope, 'Hidden')
    inactive = _product(connection, scope, 'Inactive', status='INACTIVE')
    composed = _product(connection, scope, 'Inactive composition')
    _expose(connection, scope, (inactive, composed))
    _execute(
        connection,
        "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) "
        "VALUES (%s,%s,%s,'INACTIVE')",
        (scope.tenant_id, scope.organization_id, composed),
    )
    headers = _headers(client, scope)
    draft = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).json()
    for product_id in (nonorderable, inactive, composed):
        response = client.post(
            f"/order-drafts/{draft['draft_id']}/items",
            headers=headers,
            json={'product_id': product_id, 'quantity': '1', 'expected_version': 1},
        )
        assert response.status_code == 409
    assert client.get(f"/order-drafts/{draft['draft_id']}", headers=headers).json()['items'] == []


def test_composed_item_incomplete_valid_multiselect_and_drift(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    parent_id = _product(connection, scope, 'Breakfast')
    _expose(connection, scope, (parent_id,))
    composition_id, fixed_id, group_id, option_ids = _composition(connection, scope, parent_id)
    headers = _headers(client, scope)
    draft = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).json()
    added = client.post(
        f"/order-drafts/{draft['draft_id']}/items",
        headers=headers,
        json={'product_id': parent_id, 'quantity': '1', 'expected_version': 1},
    )
    assert added.status_code == 201
    value = added.json()
    item = value['items'][0]
    assert value['readiness'] == item['readiness'] == 'INCOMPLETE'
    assert item['composition_id'] == composition_id
    assert item['missing_choice_groups'][0] == {
        'group_id': group_id,
        'group_name': 'Beverage',
        'min_selections': 1,
        'max_selections': 2,
        'selected_option_ids': [],
    }
    assert item['fixed_components'] == [
        {'product_id': fixed_id, 'product_name': 'Fixed component', 'quantity': '1.5000'}
    ]

    selected = client.put(
        f"/order-drafts/{draft['draft_id']}/items/{item['item_id']}/choice-groups/{group_id}",
        headers=headers,
        json={'option_ids': list(option_ids[:2]), 'expected_version': 2},
    )
    assert selected.status_code == 200
    selected_value = selected.json()
    assert selected_value['readiness'] == 'READY'
    assert selected_value['version'] == 3
    assert [row['choice_option_id'] for row in selected_value['items'][0]['selections']] == list(
        option_ids[:2]
    )

    too_many = client.put(
        f"/order-drafts/{draft['draft_id']}/items/{item['item_id']}/choice-groups/{group_id}",
        headers=headers,
        json={'option_ids': list(option_ids), 'expected_version': 3},
    )
    assert too_many.status_code == 422
    unchanged = client.get(f"/order-drafts/{draft['draft_id']}", headers=headers).json()
    assert unchanged['version'] == 3
    assert len(unchanged['items'][0]['selections']) == 2

    duplicate = client.put(
        f"/order-drafts/{draft['draft_id']}/items/{item['item_id']}/choice-groups/{group_id}",
        headers=headers,
        json={'option_ids': [option_ids[0], option_ids[0]], 'expected_version': 3},
    )
    assert duplicate.status_code == 422
    emptied = client.put(
        f"/order-drafts/{draft['draft_id']}/items/{item['item_id']}/choice-groups/{group_id}",
        headers=headers,
        json={'option_ids': [], 'expected_version': 3},
    )
    assert emptied.status_code == 200
    assert emptied.json()['readiness'] == 'INCOMPLETE'
    assert emptied.json()['items'][0]['selections'] == []

    restored = client.put(
        f"/order-drafts/{draft['draft_id']}/items/{item['item_id']}/choice-groups/{group_id}",
        headers=headers,
        json={'option_ids': [option_ids[0]], 'expected_version': 4},
    )
    assert restored.status_code == 200
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE product_choice_options SET status='INACTIVE' WHERE id=%s", (option_ids[0],)
        )
    drifted = client.get(f"/order-drafts/{draft['draft_id']}", headers=headers).json()
    assert drifted['readiness'] == 'INVALID'
    assert drifted['items'][0]['selections'][0]['choice_option_id'] == option_ids[0]


def test_wrong_group_option_and_cross_draft_item_are_rejected(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    parent_a = _product(connection, scope, 'Breakfast A')
    parent_b = _product(connection, scope, 'Breakfast B')
    _expose(connection, scope, (parent_a, parent_b))
    _, _, group_a, options_a = _composition(connection, scope, parent_a)
    _, _, group_b, options_b = _composition(connection, scope, parent_b)
    headers = _headers(client, scope)
    first_draft = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).json()
    first = client.post(
        f"/order-drafts/{first_draft['draft_id']}/items",
        headers=headers,
        json={'product_id': parent_a, 'quantity': '1', 'expected_version': 1},
    ).json()
    item_id = first['items'][0]['item_id']
    assert client.put(
        f"/order-drafts/{first_draft['draft_id']}/items/{item_id}/choice-groups/{group_b}",
        headers=headers,
        json={'option_ids': [options_b[0]], 'expected_version': 2},
    ).status_code == 422
    assert client.put(
        f"/order-drafts/{first_draft['draft_id']}/items/{item_id}/choice-groups/{group_a}",
        headers=headers,
        json={'option_ids': [options_b[0]], 'expected_version': 2},
    ).status_code == 422
    assert client.put(
        f"/order-drafts/{first_draft['draft_id']}/items/{item_id + 999999}/choice-groups/{group_a}",
        headers=headers,
        json={'option_ids': [options_a[0]], 'expected_version': 2},
    ).status_code == 404


@pytest.mark.parametrize('inactive_kind', ['group', 'option', 'option_product'])
def test_inactive_choice_state_is_rejected_without_mutation(
    client, sql_connection, inactive_kind
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    parent_id = _product(connection, scope, 'Breakfast')
    _expose(connection, scope, (parent_id,))
    _, _, group_id, option_ids = _composition(connection, scope, parent_id)
    headers = _headers(client, scope)
    draft = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).json()
    added = client.post(
        f"/order-drafts/{draft['draft_id']}/items",
        headers=headers,
        json={'product_id': parent_id, 'quantity': '1', 'expected_version': 1},
    ).json()
    item_id = added['items'][0]['item_id']
    with connection.cursor() as cursor:
        if inactive_kind == 'group':
            cursor.execute("UPDATE product_choice_groups SET status='INACTIVE' WHERE id=%s", (group_id,))
        elif inactive_kind == 'option':
            cursor.execute(
                "UPDATE product_choice_options SET status='INACTIVE' WHERE id=%s", (option_ids[0],)
            )
        else:
            cursor.execute(
                "UPDATE products AS P JOIN product_choice_options AS O ON O.option_product_id=P.id "
                "SET P.status='INACTIVE' WHERE O.id=%s",
                (option_ids[0],),
            )
    response = client.put(
        f"/order-drafts/{draft['draft_id']}/items/{item_id}/choice-groups/{group_id}",
        headers=headers,
        json={'option_ids': [option_ids[0]], 'expected_version': 2},
    )
    assert response.status_code == 422
    current = client.get(f"/order-drafts/{draft['draft_id']}", headers=headers).json()
    assert current['version'] == 2
    assert current['items'][0]['selections'] == []


def test_product_menu_and_composition_drift_retain_customer_intent(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    simple_id = _product(connection, scope, 'Simple')
    parent_id = _product(connection, scope, 'Composed')
    menu_location_id, menu_items = _expose(connection, scope, (simple_id, parent_id))
    composition_id, _, _, _ = _composition(connection, scope, parent_id)
    headers = _headers(client, scope)
    draft = client.post(
        f'/conversations/{scope.conversation_id}/order-draft', headers=headers
    ).json()
    first = client.post(
        f"/order-drafts/{draft['draft_id']}/items",
        headers=headers,
        json={'product_id': simple_id, 'quantity': '1', 'expected_version': 1},
    ).json()
    second = client.post(
        f"/order-drafts/{draft['draft_id']}/items",
        headers=headers,
        json={'product_id': parent_id, 'quantity': '1', 'expected_version': 2},
    ).json()
    assert len(second['items']) == 2
    with connection.cursor() as cursor:
        cursor.execute("UPDATE products SET status='INACTIVE' WHERE id=%s", (simple_id,))
        cursor.execute("UPDATE menu_locations SET status='INACTIVE' WHERE id=%s", (menu_location_id,))
        cursor.execute(
            "UPDATE product_compositions SET status='INACTIVE' WHERE id=%s", (composition_id,)
        )
    drifted = client.get(f"/order-drafts/{draft['draft_id']}", headers=headers).json()
    assert drifted['readiness'] == 'INVALID'
    assert [item['item_id'] for item in drifted['items']] == [
        first['items'][0]['item_id'],
        second['items'][1]['item_id'],
    ]
    assert menu_items


def test_concurrent_create_and_add_use_one_draft_and_one_version_winner(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product_id = _product(connection, scope, 'Concurrent Coffee')
    _expose(connection, scope, (product_id,))

    async def create_once():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as session:
                return await service.get_or_create_draft(
                    session, tenant_id=scope.tenant_id, conversation_id=scope.conversation_id
                )
        finally:
            await manager.dispose()

    async def create_both():
        return await asyncio.gather(create_once(), create_once())

    created = asyncio.run(create_both())
    assert created[0].draft_id == created[1].draft_id
    assert created[0].version == created[1].version == 1

    async def add_once():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as session:
                return await service.add_item(
                    session,
                    tenant_id=scope.tenant_id,
                    draft_id=created[0].draft_id,
                    product_id=product_id,
                    quantity=Decimal('1'),
                    expected_version=1,
                )
        finally:
            await manager.dispose()

    async def add_both():
        return await asyncio.gather(add_once(), add_once(), return_exceptions=True)

    outcomes = asyncio.run(add_both())
    assert sum(not isinstance(value, Exception) for value in outcomes) == 1
    assert sum(isinstance(value, errors.DraftConcurrencyConflictError) for value in outcomes) == 1, outcomes
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT version FROM order_drafts WHERE id=%s', (created[0].draft_id,)
        )
        assert cursor.fetchone()['version'] == 2
        cursor.execute(
            'SELECT COUNT(*) AS count FROM order_draft_items WHERE draft_id=%s',
            (created[0].draft_id,),
        )
        assert cursor.fetchone()['count'] == 1


def test_concurrent_remove_vs_selection_has_one_winner_and_no_corruption(
    integration_settings, sql_connection
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    parent_id = _product(connection, scope, 'Concurrent Breakfast')
    _expose(connection, scope, (parent_id,))
    _, _, group_id, option_ids = _composition(connection, scope, parent_id)

    async def setup():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as session:
                draft = await service.get_or_create_draft(
                    session, tenant_id=scope.tenant_id, conversation_id=scope.conversation_id
                )
                return await service.add_item(
                    session,
                    tenant_id=scope.tenant_id,
                    draft_id=draft.draft_id,
                    product_id=parent_id,
                    quantity=Decimal('1'),
                    expected_version=1,
                )
        finally:
            await manager.dispose()

    draft = asyncio.run(setup())
    item_id = draft.items[0].item_id

    async def remove():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as session:
                return await service.remove_item(
                    session,
                    tenant_id=scope.tenant_id,
                    draft_id=draft.draft_id,
                    item_id=item_id,
                    expected_version=2,
                )
        finally:
            await manager.dispose()

    async def select_option():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as session:
                return await service.replace_group_selections(
                    session,
                    tenant_id=scope.tenant_id,
                    draft_id=draft.draft_id,
                    item_id=item_id,
                    group_id=group_id,
                    option_ids=(option_ids[0],),
                    expected_version=2,
                )
        finally:
            await manager.dispose()

    async def race():
        return await asyncio.gather(remove(), select_option(), return_exceptions=True)

    outcomes = asyncio.run(race())
    assert sum(not isinstance(value, Exception) for value in outcomes) == 1
    assert sum(isinstance(value, errors.DraftConcurrencyConflictError) for value in outcomes) == 1
    with connection.cursor() as cursor:
        cursor.execute('SELECT version FROM order_drafts WHERE id=%s', (draft.draft_id,))
        assert cursor.fetchone()['version'] == 3
        cursor.execute(
            'SELECT COUNT(*) AS count FROM order_draft_items WHERE id=%s', (item_id,)
        )
        item_count = cursor.fetchone()['count']
        cursor.execute(
            'SELECT COUNT(*) AS count FROM order_draft_item_selections WHERE draft_item_id=%s',
            (item_id,),
        )
        selection_count = cursor.fetchone()['count']
    assert (item_count, selection_count) in {(0, 0), (1, 1)}


def test_internal_quantity_contract_rejects_binary_float():
    with pytest.raises(errors.InvalidDraftQuantityError):
        service.validate_quantity(1.0)
    assert service.validate_quantity(Decimal('0.0001')) == Decimal('0.0001')
