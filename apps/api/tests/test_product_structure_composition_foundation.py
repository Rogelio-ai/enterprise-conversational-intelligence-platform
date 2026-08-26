from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

import pymysql
import pytest
from fastapi.testclient import TestClient
from app.core.security import hash_password
from app.db.session import DatabaseManager
from app.main import create_app
from app.models import ProductComponent
from app.restaurant.catalog import structure
from app.restaurant.knowledge import service as knowledge


PASSWORD = 'Test Password 123!'


@dataclass(frozen=True)
class Scope:
    tenant_id: int
    organization_id: int
    role_id: int
    email: str


def _execute(connection, statement: str, parameters=()) -> int:
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def _scope(connection, prefix: str) -> Scope:
    tenant_id = _execute(
        connection,
        "INSERT INTO tenants (name,slug,status) VALUES ('Structure Tenant',%s,'ACTIVE')",
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
        (tenant_id, f'STRUCTURE_{uuid4().hex}'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',
        (tenant_id, membership_id, role_id),
    )
    for permission in ('product.read', 'product.manage'):
        with connection.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (permission,))
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
    return Scope(tenant_id, organization_id, role_id, email)


def _headers(client: TestClient, scope: Scope) -> dict[str, str]:
    response = client.post('/auth/login', json={'email': scope.email, 'password': PASSWORD})
    assert response.status_code == 200
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _product(connection, scope: Scope, name: str, status='ACTIVE') -> int:
    return _execute(
        connection,
        "INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,%s,%s,'PLATFORM')",
        (scope.tenant_id, scope.organization_id, name, status),
    )


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as test_client:
        yield test_client


def test_category_hierarchy_ordering_flat_compatibility_and_cycles(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    flat = client.post(
        '/product-categories',
        headers=headers,
        json={'organization_id': scope.organization_id, 'name': 'Flat'},
    )
    root = client.post(
        '/product-categories',
        headers=headers,
        json={'organization_id': scope.organization_id, 'name': 'Agrupador', 'display_order': 20},
    )
    child = client.post(
        '/product-categories',
        headers=headers,
        json={
            'organization_id': scope.organization_id,
            'parent_id': root.json()['id'],
            'name': 'Familia',
            'display_order': 10,
        },
    )
    assert flat.status_code == root.status_code == child.status_code == 201
    assert flat.json()['parent_id'] is None and flat.json()['display_order'] == 0
    assert child.json()['parent_id'] == root.json()['id']
    assert client.post(
        '/product-categories',
        headers=headers,
        json={
            'organization_id': scope.organization_id,
            'name': 'Invalid order',
            'display_order': -1,
        },
    ).status_code == 422
    listed = client.get(
        '/product-categories',
        headers=headers,
        params={'organization_id': scope.organization_id},
    ).json()['items']
    assert [item['id'] for item in listed] == [flat.json()['id'], child.json()['id'], root.json()['id']]
    assert client.patch(
        f"/product-categories/{root.json()['id']}",
        headers=headers,
        json={'parent_id': root.json()['id']},
    ).status_code == 409
    assert client.patch(
        f"/product-categories/{root.json()['id']}",
        headers=headers,
        json={'parent_id': child.json()['id']},
    ).status_code == 409
    detached = client.patch(
        f"/product-categories/{child.json()['id']}",
        headers=headers,
        json={'parent_id': None, 'display_order': 5},
    )
    assert detached.status_code == 200 and detached.json()['parent_id'] is None
    assert client.delete(
        f"/product-categories/{child.json()['id']}", headers=headers
    ).status_code == 405


def test_category_scope_integrity_and_no_cascade(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    sibling_org = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'SIBLING','Sibling','ACTIVE')",
        (scope.tenant_id,),
    )
    sibling_category = _execute(
        connection,
        "INSERT INTO product_categories (tenant_id,organization_id,name,status) VALUES (%s,%s,'Sibling','ACTIVE')",
        (scope.tenant_id, sibling_org),
    )
    other = _scope(connection, f'{prefix}-other')
    other_category = _execute(
        connection,
        "INSERT INTO product_categories (tenant_id,organization_id,name,status) VALUES (%s,%s,'Other','ACTIVE')",
        (other.tenant_id, other.organization_id),
    )
    headers = _headers(client, scope)
    for parent_id in (sibling_category, other_category):
        response = client.post(
            '/product-categories',
            headers=headers,
            json={
                'organization_id': scope.organization_id,
                'parent_id': parent_id,
                'name': f'Invalid {parent_id}',
            },
        )
        assert response.status_code == 404
    parent = client.post(
        '/product-categories',
        headers=headers,
        json={'organization_id': scope.organization_id, 'name': 'Parent'},
    ).json()
    child = client.post(
        '/product-categories',
        headers=headers,
        json={'organization_id': scope.organization_id, 'parent_id': parent['id'], 'name': 'Child'},
    ).json()
    product_id = _execute(
        connection,
        "INSERT INTO products (tenant_id,organization_id,category_id,name,status,source) VALUES (%s,%s,%s,'Product','ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id, child['id']),
    )
    assert client.patch(
        f"/product-categories/{parent['id']}", headers=headers, json={'status': 'INACTIVE'}
    ).status_code == 200
    with connection.cursor() as cursor:
        cursor.execute('SELECT status FROM products WHERE id=%s', (product_id,))
        assert cursor.fetchone()['status'] == 'ACTIVE'
        cursor.execute('SELECT status,parent_id FROM product_categories WHERE id=%s', (child['id'],))
        assert cursor.fetchone() == {'status': 'ACTIVE', 'parent_id': parent['id']}


def test_composition_api_activation_ordering_and_knowledge(client, integration_settings, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    parent = _product(connection, scope, 'Comida corrida')
    soup = _product(connection, scope, 'Sopa')
    main_a = _product(connection, scope, 'Milanesa')
    main_b = _product(connection, scope, 'Chile relleno')
    hidden = _product(connection, scope, 'Hidden')
    headers = _headers(client, scope)
    created = client.post(f'/products/{parent}/composition', headers=headers)
    assert created.status_code == 201 and created.json()['status'] == 'INACTIVE'
    assert client.post(f'/products/{parent}/composition', headers=headers).status_code == 409
    component = client.post(
        f'/products/{parent}/composition/components',
        headers=headers,
        json={'component_product_id': soup, 'quantity': '1.0000', 'display_order': 20},
    )
    assert component.status_code == 201 and component.json()['quantity'] == '1.0000'
    group = client.post(
        f'/products/{parent}/composition/choice-groups',
        headers=headers,
        json={'name': 'Plato fuerte', 'min_selections': 1, 'max_selections': 1, 'display_order': 10},
    )
    assert group.status_code == 201
    assert client.patch(
        f'/products/{parent}/composition', headers=headers, json={'status': 'ACTIVE'}
    ).status_code == 409
    option_b = client.post(
        f"/products/{parent}/composition/choice-groups/{group.json()['id']}/options",
        headers=headers,
        json={'option_product_id': main_b, 'quantity': '1', 'display_order': 20},
    ).json()
    option_a = client.post(
        f"/products/{parent}/composition/choice-groups/{group.json()['id']}/options",
        headers=headers,
        json={'option_product_id': main_a, 'quantity': '1.5000', 'display_order': 10},
    ).json()
    hidden_option = client.post(
        f"/products/{parent}/composition/choice-groups/{group.json()['id']}/options",
        headers=headers,
        json={'option_product_id': hidden, 'quantity': '1', 'display_order': 5},
    ).json()
    client.patch(
        f"/products/{parent}/composition/choice-groups/{group.json()['id']}/options/{hidden_option['id']}",
        headers=headers,
        json={'status': 'INACTIVE'},
    )
    activated = client.patch(
        f'/products/{parent}/composition', headers=headers, json={'status': 'ACTIVE'}
    )
    assert activated.status_code == 200 and activated.json()['status'] == 'ACTIVE'
    detail = client.get(f'/products/{parent}/composition', headers=headers).json()
    assert [item['option_product_id'] for item in detail['choice_groups'][0]['options']] == [
        hidden,
        main_a,
        main_b,
    ]

    async def scenario():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                return await knowledge.get_product_composition(
                    db,
                    tenant_id=scope.tenant_id,
                    organization_id=scope.organization_id,
                    product_id=parent,
                )
        finally:
            await manager.dispose()

    projection = asyncio.run(scenario())
    assert [item.product.id for item in projection.fixed_components] == [soup]
    assert [item.product.id for item in projection.choice_groups[0].options] == [main_a, main_b]
    assert projection.choice_groups[0].options[0].quantity == Decimal('1.5000')
    assert not hasattr(projection, 'availability')
    assert {'price_delta', 'price', 'availability'}.isdisjoint(detail['choice_groups'][0]['options'][0])
    assert option_a['id'] != option_b['id']


def test_component_option_constraints_activation_and_single_level(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    parent = _product(connection, scope, 'Parent')
    child = _product(connection, scope, 'Child')
    inactive = _product(connection, scope, 'Inactive', status='INACTIVE')
    headers = _headers(client, scope)
    client.post(f'/products/{parent}/composition', headers=headers)
    for invalid in ('0', '-1', '1.00001'):
        assert client.post(
            f'/products/{parent}/composition/components',
            headers=headers,
            json={'component_product_id': child, 'quantity': invalid},
        ).status_code == 422
    assert client.post(
        f'/products/{parent}/composition/components',
        headers=headers,
        json={'component_product_id': parent, 'quantity': '1'},
    ).status_code == 409
    first = client.post(
        f'/products/{parent}/composition/components',
        headers=headers,
        json={'component_product_id': child, 'quantity': '2'},
    )
    assert first.status_code == 201
    assert client.post(
        f'/products/{parent}/composition/components',
        headers=headers,
        json={'component_product_id': child, 'quantity': '2'},
    ).status_code == 409
    assert client.post(f'/products/{child}/composition', headers=headers).status_code == 409
    created_group_ids = []
    for payload in (
        {'name': 'Optional', 'min_selections': 0, 'max_selections': 2},
        {'name': 'Exactly one', 'min_selections': 1, 'max_selections': 1},
    ):
        created_group = client.post(
            f'/products/{parent}/composition/choice-groups', headers=headers, json=payload
        )
        assert created_group.status_code == 201
        created_group_ids.append(created_group.json()['id'])
    for payload in (
        {'name': ' ', 'min_selections': 0, 'max_selections': 1},
        {'name': 'Bad minimum', 'min_selections': -1, 'max_selections': 1},
        {'name': 'Bad maximum', 'min_selections': 0, 'max_selections': 0},
        {'name': 'Bad range', 'min_selections': 2, 'max_selections': 1},
    ):
        assert client.post(
            f'/products/{parent}/composition/choice-groups', headers=headers, json=payload
        ).status_code == 422
    option_group = client.post(
        f'/products/{parent}/composition/choice-groups',
        headers=headers,
        json={'name': 'Options', 'min_selections': 0, 'max_selections': 1},
    ).json()
    for invalid in ('0', '-1', '1.00001'):
        assert client.post(
            f"/products/{parent}/composition/choice-groups/{option_group['id']}/options",
            headers=headers,
            json={'option_product_id': child, 'quantity': invalid},
        ).status_code == 422
    option = client.post(
        f"/products/{parent}/composition/choice-groups/{option_group['id']}/options",
        headers=headers,
        json={'option_product_id': child, 'quantity': '1.2500'},
    )
    assert option.status_code == 201 and option.json()['quantity'] == '1.2500'
    assert client.post(
        f"/products/{parent}/composition/choice-groups/{option_group['id']}/options",
        headers=headers,
        json={'option_product_id': child, 'quantity': '1'},
    ).status_code == 409
    for group_id in (*created_group_ids, option_group['id']):
        assert client.patch(
            f'/products/{parent}/composition/choice-groups/{group_id}',
            headers=headers,
            json={'status': 'INACTIVE'},
        ).status_code == 200
    inactive_component = client.post(
        f'/products/{parent}/composition/components',
        headers=headers,
        json={'component_product_id': inactive, 'quantity': '1'},
    )
    assert inactive_component.status_code == 201
    assert client.patch(
        f'/products/{parent}/composition', headers=headers, json={'status': 'ACTIVE'}
    ).status_code == 409
    assert client.patch(
        f"/products/{parent}/composition/components/{inactive_component.json()['id']}",
        headers=headers,
        json={'status': 'INACTIVE'},
    ).status_code == 200
    assert client.patch(
        f'/products/{parent}/composition', headers=headers, json={'status': 'ACTIVE'}
    ).status_code == 200
    assert client.patch(
        f"/products/{parent}/composition/components/{first.json()['id']}",
        headers=headers,
        json={'status': 'INACTIVE'},
    ).status_code == 200
    assert client.get(f'/products/{parent}/composition', headers=headers).json()['status'] == 'ACTIVE'
    assert client.delete(f'/products/{parent}/composition', headers=headers).status_code == 405


def test_typed_selection_validation_is_deterministic_and_read_only(integration_settings, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    parent = _product(connection, scope, 'Breakfast')
    fixed = _product(connection, scope, 'Chilaquiles')
    coffee = _product(connection, scope, 'Coffee')
    juice = _product(connection, scope, 'Juice')
    composition_id = _execute(
        connection,
        "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, parent),
    )
    _execute(
        connection,
        "INSERT INTO product_components (tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1.0000,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id, fixed),
    )
    group_id = _execute(
        connection,
        "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Beverage',1,1,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id),
    )
    coffee_option = _execute(
        connection,
        "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1.0000,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, group_id, coffee),
    )
    juice_option = _execute(
        connection,
        "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1.0000,1,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, group_id, juice),
    )
    inactive_option = _execute(
        connection,
        "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1.0000,2,'INACTIVE')",
        (scope.tenant_id, scope.organization_id, group_id, _product(connection, scope, 'Tea')),
    )
    inactive_product = _product(connection, scope, 'Inactive milk', status='INACTIVE')
    inactive_product_option = _execute(
        connection,
        "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1.0000,3,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, group_id, inactive_product),
    )
    inactive_group = _execute(
        connection,
        "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Inactive group',0,1,1,'INACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id),
    )
    inactive_group_option = _execute(
        connection,
        "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1.0000,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, inactive_group, coffee),
    )
    foreign_group = _execute(
        connection,
        "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Foreign option source',0,1,2,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id),
    )
    foreign_option = _execute(
        connection,
        "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1.0000,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, foreign_group, coffee),
    )
    inactive_parent = _product(connection, scope, 'Inactive composition parent')
    _execute(
        connection,
        "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'INACTIVE')",
        (scope.tenant_id, scope.organization_id, inactive_parent),
    )
    simple_product = _product(connection, scope, 'No composition')
    other = _scope(connection, f'{prefix}-other')
    other_parent = _product(connection, other, 'Other parent')
    other_option_product = _product(connection, other, 'Other option')
    other_composition = _execute(
        connection,
        "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'ACTIVE')",
        (other.tenant_id, other.organization_id, other_parent),
    )
    other_group = _execute(
        connection,
        "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Other',0,1,0,'ACTIVE')",
        (other.tenant_id, other.organization_id, other_composition),
    )
    other_option = _execute(
        connection,
        "INSERT INTO product_choice_options (tenant_id,organization_id,group_id,option_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1.0000,0,'ACTIVE')",
        (other.tenant_id, other.organization_id, other_group, other_option_product),
    )

    async def scenario():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                valid = await structure.validate_selection(
                    db,
                    tenant_id=scope.tenant_id,
                    product_id=parent,
                    selections=(structure.ChoiceSelection(group_id, (coffee_option,)),),
                )
                missing = await structure.validate_selection(
                    db, tenant_id=scope.tenant_id, product_id=parent, selections=()
                )
                invalid = await structure.validate_selection(
                    db,
                    tenant_id=scope.tenant_id,
                    product_id=parent,
                    selections=(
                        structure.ChoiceSelection(
                            group_id, (coffee_option, coffee_option, juice_option, 999999999)
                        ),
                        structure.ChoiceSelection(999999999, (coffee_option,)),
                    ),
                )
                too_few = await structure.validate_selection(
                    db,
                    tenant_id=scope.tenant_id,
                    product_id=parent,
                    selections=(structure.ChoiceSelection(group_id, ()),),
                )
                inactive_cases = await structure.validate_selection(
                    db,
                    tenant_id=scope.tenant_id,
                    product_id=parent,
                    selections=(
                        structure.ChoiceSelection(group_id, (inactive_option,)),
                        structure.ChoiceSelection(inactive_group, (inactive_group_option,)),
                    ),
                )
                inactive_product_case = await structure.validate_selection(
                    db,
                    tenant_id=scope.tenant_id,
                    product_id=parent,
                    selections=(
                        structure.ChoiceSelection(group_id, (inactive_product_option,)),
                    ),
                )
                foreign_cases = await structure.validate_selection(
                    db,
                    tenant_id=scope.tenant_id,
                    product_id=parent,
                    selections=(
                        structure.ChoiceSelection(group_id, (foreign_option, other_option)),
                        structure.ChoiceSelection(other_group, (other_option,)),
                    ),
                )
                inactive_composition = await structure.validate_selection(
                    db, tenant_id=scope.tenant_id, product_id=inactive_parent, selections=()
                )
                absent_composition = await structure.validate_selection(
                    db, tenant_id=scope.tenant_id, product_id=simple_product, selections=()
                )
                invalid_again = await structure.validate_selection(
                    db,
                    tenant_id=scope.tenant_id,
                    product_id=parent,
                    selections=(
                        structure.ChoiceSelection(
                            group_id, (coffee_option, coffee_option, juice_option, 999999999)
                        ),
                        structure.ChoiceSelection(999999999, (coffee_option,)),
                    ),
                )
                return (
                    valid,
                    missing,
                    invalid,
                    too_few,
                    inactive_cases,
                    inactive_product_case,
                    foreign_cases,
                    inactive_composition,
                    absent_composition,
                    invalid_again,
                )
        finally:
            await manager.dispose()

    before = {}
    with connection.cursor() as cursor:
        for table in ('product_compositions', 'product_components', 'product_choice_options'):
            cursor.execute(f'SELECT COUNT(*) AS count FROM {table} WHERE tenant_id=%s', (scope.tenant_id,))
            before[table] = cursor.fetchone()['count']
    (
        valid,
        missing,
        invalid,
        too_few,
        inactive_cases,
        inactive_product_case,
        foreign_cases,
        inactive_composition,
        absent_composition,
        invalid_again,
    ) = asyncio.run(scenario())
    assert valid.is_valid
    assert valid.fixed_components == (structure.ResolvedProductQuantity(fixed, Decimal('1.0000')),)
    assert valid.selected_options[0].product_id == coffee
    assert [item.code for item in missing.violations] == [
        structure.SelectionViolationCode.REQUIRED_GROUP_MISSING
    ]
    assert {item.code for item in invalid.violations} == {
        structure.SelectionViolationCode.DUPLICATE_OPTION,
        structure.SelectionViolationCode.INVALID_GROUP,
        structure.SelectionViolationCode.INVALID_OPTION,
        structure.SelectionViolationCode.TOO_MANY_SELECTIONS,
    }
    assert invalid == invalid_again
    assert {item.code for item in too_few.violations} == {
        structure.SelectionViolationCode.TOO_FEW_SELECTIONS
    }
    assert {item.code for item in inactive_cases.violations} == {
        structure.SelectionViolationCode.INACTIVE_GROUP,
        structure.SelectionViolationCode.INACTIVE_OPTION,
        structure.SelectionViolationCode.TOO_FEW_SELECTIONS,
    }
    assert {item.code for item in inactive_product_case.violations} == {
        structure.SelectionViolationCode.INACTIVE_PRODUCT,
        structure.SelectionViolationCode.TOO_FEW_SELECTIONS,
    }
    assert {item.code for item in foreign_cases.violations} == {
        structure.SelectionViolationCode.INVALID_GROUP,
        structure.SelectionViolationCode.INVALID_OPTION,
        structure.SelectionViolationCode.TOO_FEW_SELECTIONS,
    }
    assert [item.code for item in inactive_composition.violations] == [
        structure.SelectionViolationCode.COMPOSITION_NOT_ACTIVE
    ]
    assert [item.code for item in absent_composition.violations] == [
        structure.SelectionViolationCode.COMPOSITION_NOT_FOUND
    ]
    assert not hasattr(valid, 'price')
    with connection.cursor() as cursor:
        for table, count in before.items():
            cursor.execute(f'SELECT COUNT(*) AS count FROM {table} WHERE tenant_id=%s', (scope.tenant_id,))
            assert cursor.fetchone()['count'] == count


def test_raw_scope_and_business_constraints(sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    other = _scope(connection, f'{prefix}-other')
    parent = _product(connection, scope, 'Parent')
    child = _product(connection, scope, 'Child')
    other_product = _product(connection, other, 'Other')
    composition = _execute(
        connection,
        "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'INACTIVE')",
        (scope.tenant_id, scope.organization_id, parent),
    )
    invalid = (
        (
            "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'INACTIVE')",
            (other.tenant_id, other.organization_id, parent),
        ),
        (
            "INSERT INTO product_components (tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,1,0,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, composition, other_product),
        ),
        (
            "INSERT INTO product_components (tenant_id,organization_id,composition_id,component_product_id,quantity,display_order,status) VALUES (%s,%s,%s,%s,0,0,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, composition, child),
        ),
        (
            "INSERT INTO product_choice_groups (tenant_id,organization_id,composition_id,name,min_selections,max_selections,display_order,status) VALUES (%s,%s,%s,'Invalid',2,1,0,'ACTIVE')",
            (scope.tenant_id, scope.organization_id, composition),
        ),
    )
    for statement, parameters in invalid:
        with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
            _execute(connection, statement, parameters)


def test_composition_api_reuses_product_rbac_and_derived_scope(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product_id = _product(connection, scope, 'Read only composition')
    _execute(
        connection,
        "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'INACTIVE')",
        (scope.tenant_id, scope.organization_id, product_id),
    )
    headers = _headers(client, scope)
    assert client.post(
        '/product-categories',
        headers=headers,
        json={
            'organization_id': scope.organization_id,
            'tenant_id': scope.tenant_id,
            'name': 'Untrusted scope',
        },
    ).status_code == 422
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE rp FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id WHERE rp.role_id=%s AND p.code='product.manage'",
            (scope.role_id,),
        )
    assert client.get(f'/products/{product_id}/composition', headers=headers).status_code == 200
    assert client.patch(
        f'/products/{product_id}/composition', headers=headers, json={'status': 'ACTIVE'}
    ).status_code == 403
    assert client.get(f'/products/{product_id}/composition').status_code == 401


def test_concurrent_category_cycle_is_not_persisted(integration_settings, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    category_a = _execute(
        connection,
        "INSERT INTO product_categories (tenant_id,organization_id,name,status) VALUES (%s,%s,'A','ACTIVE')",
        (scope.tenant_id, scope.organization_id),
    )
    category_b = _execute(
        connection,
        "INSERT INTO product_categories (tenant_id,organization_id,name,status) VALUES (%s,%s,'B','ACTIVE')",
        (scope.tenant_id, scope.organization_id),
    )

    async def scenario():
        manager = DatabaseManager(integration_settings)

        async def assign(category_id, parent_id):
            try:
                async with manager.session_factory() as db:
                    await structure.set_category_parent(
                        db,
                        tenant_id=scope.tenant_id,
                        category_id=category_id,
                        parent_id=parent_id,
                    )
                    await db.commit()
                    return 'committed'
            except structure.StructureConflictError:
                return 'rejected'

        try:
            return await asyncio.gather(
                assign(category_a, category_b), assign(category_b, category_a)
            )
        finally:
            await manager.dispose()

    assert sorted(asyncio.run(scenario())) == ['committed', 'rejected']
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id,parent_id FROM product_categories WHERE id IN (%s,%s) ORDER BY id',
            (category_a, category_b),
        )
        rows = cursor.fetchall()
    assert sum(row['parent_id'] is not None for row in rows) == 1


def test_concurrent_nested_composition_is_not_persisted(integration_settings, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    product_a = _product(connection, scope, 'A')
    product_b = _product(connection, scope, 'B')
    composition_b = _execute(
        connection,
        "INSERT INTO product_compositions (tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,'INACTIVE')",
        (scope.tenant_id, scope.organization_id, product_b),
    )

    async def scenario():
        manager = DatabaseManager(integration_settings)

        async def own_composition():
            try:
                async with manager.session_factory() as db:
                    await structure.create_composition(
                        db, tenant_id=scope.tenant_id, product_id=product_a
                    )
                    await db.commit()
                    return 'composition'
            except structure.StructureConflictError:
                return 'rejected'

        async def become_component():
            try:
                async with manager.session_factory() as db:
                    composition = await structure.require_composition(
                        db, tenant_id=scope.tenant_id, product_id=product_b
                    )
                    await structure.validate_child_product(
                        db, composition=composition, child_product_id=product_a
                    )
                    db.add(
                        ProductComponent(
                            tenant_id=scope.tenant_id,
                            organization_id=scope.organization_id,
                            composition_id=composition_b,
                            component_product_id=product_a,
                            quantity=Decimal('1'),
                            display_order=0,
                            status='ACTIVE',
                        )
                    )
                    await db.commit()
                    return 'component'
            except structure.StructureConflictError:
                return 'rejected'

        try:
            return await asyncio.gather(own_composition(), become_component())
        finally:
            await manager.dispose()

    outcomes = asyncio.run(scenario())
    assert 'rejected' in outcomes
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM product_compositions WHERE tenant_id=%s AND product_id=%s',
            (scope.tenant_id, product_a),
        )
        composition_count = cursor.fetchone()['count']
        cursor.execute(
            'SELECT COUNT(*) AS count FROM product_components WHERE tenant_id=%s AND component_product_id=%s',
            (scope.tenant_id, product_a),
        )
        component_count = cursor.fetchone()['count']
    assert composition_count + component_count == 1
