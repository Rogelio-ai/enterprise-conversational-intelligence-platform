from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import create_app
from app.restaurant.inventory.units import UnitConversionError, convert_quantity


PASSWORD = 'Test Password 123!'


@dataclass(frozen=True)
class Scope:
    tenant_id: int
    organization_id: int
    location_id: int
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
        'INSERT IGNORE INTO permissions (code,description) VALUES (%s,%s)',
        (code, f'Permission {code}'),
    )
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
        permission_id = int(cursor.fetchone()['id'])
    _execute(
        connection,
        'INSERT IGNORE INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
        (role_id, permission_id),
    )


def _scope(connection, slug: str, permissions=()) -> Scope:
    tenant_id = _execute(
        connection,
        'INSERT INTO tenants (name,slug,status) VALUES (%s,%s,%s)',
        ('Inventory Tenant', slug, 'ACTIVE'),
    )
    organization_id = _execute(
        connection,
        'INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,%s,%s)',
        (tenant_id, 'ORG', 'Inventory Organization', 'ACTIVE'),
    )
    location_id = _execute(
        connection,
        'INSERT INTO locations '
        '(tenant_id,organization_id,code,name,timezone,status) '
        'VALUES (%s,%s,%s,%s,%s,%s)',
        (
            tenant_id, organization_id, 'LOC', 'Inventory Location',
            'America/Mexico_City', 'ACTIVE',
        ),
    )
    email = f'{slug}@example.test'
    user_id = _execute(
        connection,
        'INSERT INTO users (email,password_hash,display_name,status) '
        'VALUES (%s,%s,%s,%s)',
        (email, hash_password(PASSWORD), 'Inventory User', 'ACTIVE'),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,%s)',
        (tenant_id, user_id, 'ACTIVE'),
    )
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,%s)',
        (tenant_id, 'INVENTORY_TEST_ROLE', 'Inventory tests', 'ACTIVE'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) '
        'VALUES (%s,%s,%s)',
        (tenant_id, membership_id, role_id),
    )
    for permission in permissions:
        _permission(connection, role_id, permission)
    return Scope(
        tenant_id, organization_id, location_id, membership_id, role_id, email
    )


def _headers(client: TestClient, scope: Scope) -> dict[str, str]:
    response = client.post(
        '/auth/login', json={'email': scope.email, 'password': PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def _item(
    client: TestClient, headers: dict[str, str], location_id: int,
    code: str, *, uom: str = 'G', cost: str = '0.010000', currency: str = 'MXN',
) -> dict:
    response = client.post(
        '/inventory-items',
        headers=headers,
        json={
            'location_id': location_id,
            'code': code,
            'name': f'Item {code}',
            'base_uom': uom,
            'standard_unit_cost': cost,
            'currency': currency,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _product(connection, scope: Scope, name: str = 'Recipe Product') -> int:
    return _execute(
        connection,
        'INSERT INTO products (tenant_id,organization_id,name,status,source) '
        "VALUES (%s,%s,%s,'ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id, name),
    )


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def test_minimal_units_are_exact_and_reject_incompatible_families() -> None:
    assert convert_quantity(Decimal('1'), from_uom='KG', to_uom='G') == Decimal('1000')
    assert convert_quantity(Decimal('1'), from_uom='L', to_uom='ML') == Decimal('1000')
    assert convert_quantity(Decimal('1250'), from_uom='G', to_uom='KG') == Decimal('1.250000')
    assert convert_quantity(Decimal('2'), from_uom='UNIT', to_uom='UNIT') == Decimal('2')
    with pytest.raises(UnitConversionError):
        convert_quantity(Decimal('1'), from_uom='KG', to_uom='L')
    with pytest.raises(UnitConversionError):
        convert_quantity(Decimal('1'), from_uom='UNIT', to_uom='PORTION')
    with pytest.raises(UnitConversionError):
        convert_quantity(1.0, from_uom='KG', to_uom='G')  # type: ignore[arg-type]


def test_inventory_item_permissions_validation_and_optimistic_update(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    headers = _headers(client, scope)
    payload = {
        'location_id': scope.location_id,
        'code': 'flour',
        'name': 'Flour',
        'base_uom': 'G',
        'standard_unit_cost': '0.025000',
        'currency': 'mxn',
    }
    assert client.post('/inventory-items', headers=headers, json=payload).status_code == 403
    _permission(connection, scope.role_id, 'inventory.manage')
    created = client.post('/inventory-items', headers=headers, json=payload)
    assert created.status_code == 201, created.text
    item = created.json()
    assert (item['code'], item['base_uom'], item['currency'], item['version']) == (
        'FLOUR', 'G', 'MXN', 1,
    )
    assert client.post('/inventory-items', headers=headers, json=payload).status_code == 409
    assert client.post(
        '/inventory-items', headers=headers,
        json={**payload, 'code': 'BAD', 'standard_unit_cost': '-0.000001'},
    ).status_code == 422
    assert client.patch(
        f"/inventory-items/{item['id']}", headers=headers,
        json={'expected_version': 1, 'base_uom': 'KG'},
    ).status_code == 422
    updated = client.patch(
        f"/inventory-items/{item['id']}", headers=headers,
        json={'expected_version': 1, 'name': 'Fine Flour', 'standard_unit_cost': '0.030000'},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()['version'] == 2
    assert client.patch(
        f"/inventory-items/{item['id']}", headers=headers,
        json={'expected_version': 1, 'status': 'INACTIVE'},
    ).status_code == 409
    assert client.get(
        '/inventory-items', headers=headers,
        params={'location_id': scope.location_id},
    ).status_code == 403
    _permission(connection, scope.role_id, 'inventory.read')
    listed = client.get(
        '/inventory-items', headers=headers,
        params={'location_id': scope.location_id},
    )
    assert listed.status_code == 200
    assert [value['id'] for value in listed.json()['items']] == [item['id']]


def test_recipe_replacement_normalization_versioning_and_cost_semantics(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, ('inventory.manage', 'inventory.read'))
    headers = _headers(client, scope)
    flour = _item(client, headers, scope.location_id, 'FLOUR', cost='0.020000')
    milk = _item(
        client, headers, scope.location_id, 'MILK', uom='ML',
        cost='0.030000', currency='MXN',
    )
    product_id = _product(connection, scope)
    url = f'/products/{product_id}/consumption-definition'
    created = client.put(
        url, headers=headers, params={'location_id': scope.location_id},
        json={
            'expected_version': 0,
            'tracking_mode': 'DERIVABLE',
            'components': [
                {'inventory_item_id': flour['id'], 'quantity': '0.250000', 'uom': 'KG'},
                {'inventory_item_id': milk['id'], 'quantity': '0.100000', 'uom': 'L'},
            ],
        },
    )
    assert created.status_code == 200, created.text
    definition = created.json()
    assert definition['version'] == 1
    assert [value['quantity'] for value in definition['components']] == [
        '250.000000', '100.000000',
    ]

    invalid = client.put(
        url, headers=headers, params={'location_id': scope.location_id},
        json={
            'expected_version': 1,
            'tracking_mode': 'DERIVABLE',
            'components': [
                {'inventory_item_id': flour['id'], 'quantity': '1.000000', 'uom': 'L'},
            ],
        },
    )
    assert invalid.status_code == 422
    unchanged = client.get(
        url, headers=headers, params={'location_id': scope.location_id}
    ).json()
    assert unchanged == definition

    cost = client.post(
        f'/products/{product_id}/theoretical-cost:resolve', headers=headers,
        json={'location_id': scope.location_id},
    )
    assert cost.status_code == 200, cost.text
    assert cost.json()['cost_status'] == 'RESOLVED'
    assert cost.json()['currency'] == 'MXN'
    assert Decimal(cost.json()['total_theoretical_cost']) == Decimal('8.000000000000')

    replaced = client.put(
        url, headers=headers, params={'location_id': scope.location_id},
        json={
            'expected_version': 1,
            'tracking_mode': 'NON_DERIVABLE',
            'components': [],
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()['version'] == 2
    non_derivable = client.post(
        f'/products/{product_id}/theoretical-cost:resolve', headers=headers,
        json={'location_id': scope.location_id},
    ).json()
    assert non_derivable['cost_status'] == 'NON_DERIVABLE'
    assert non_derivable['total_theoretical_cost'] is None
    assert client.put(
        url, headers=headers, params={'location_id': scope.location_id},
        json={
            'expected_version': 1,
            'tracking_mode': 'DERIVABLE',
            'components': [],
        },
    ).status_code == 409


def test_mixed_currency_cost_is_explicitly_unsupported(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, ('inventory.manage', 'inventory.read'))
    headers = _headers(client, scope)
    mxn = _item(client, headers, scope.location_id, 'MXN', cost='2.000000')
    usd = _item(
        client, headers, scope.location_id, 'USD', cost='3.000000', currency='USD'
    )
    product_id = _product(connection, scope, 'Mixed Currency')
    response = client.put(
        f'/products/{product_id}/consumption-definition', headers=headers,
        params={'location_id': scope.location_id},
        json={
            'expected_version': 0,
            'tracking_mode': 'DERIVABLE',
            'components': [
                {'inventory_item_id': mxn['id'], 'quantity': '1.000000', 'uom': 'G'},
                {'inventory_item_id': usd['id'], 'quantity': '1.000000', 'uom': 'G'},
            ],
        },
    )
    assert response.status_code == 200, response.text
    cost = client.post(
        f'/products/{product_id}/theoretical-cost:resolve', headers=headers,
        json={'location_id': scope.location_id},
    ).json()
    assert cost['cost_status'] == 'CURRENCY_MISMATCH'
    assert cost['currency'] is None
    assert cost['total_theoretical_cost'] is None
    assert len(cost['components']) == 2


def test_movement_rules_idempotency_reversal_and_stock_sum(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, ('inventory.manage', 'inventory.read'))
    headers = _headers(client, scope)
    item = _item(client, headers, scope.location_id, 'STOCK')
    url = '/inventory/stock-movements'

    def movement(key: str, movement_type: str, quantity=None, **extra):
        payload = {
            'inventory_item_id': item['id'],
            'movement_type': movement_type,
            **extra,
        }
        if quantity is not None:
            payload['quantity'] = quantity
        return client.post(
            url, headers={**headers, 'Idempotency-Key': key}, json=payload
        )

    opening = movement('opening', 'OPENING_BALANCE', '10.000000')
    replay = movement('opening', 'OPENING_BALANCE', '10.000000')
    assert (opening.status_code, replay.status_code) == (201, 200)
    assert opening.json()['id'] == replay.json()['id']
    assert movement('opening', 'OPENING_BALANCE', '11.000000').status_code == 409
    assert movement('opening-2', 'OPENING_BALANCE', '1.000000').status_code == 409
    assert movement('opening-zero', 'OPENING_BALANCE', '0.000000').status_code == 422
    assert movement('wrong-in', 'MANUAL_IN', '-1.000000', reason='bad').status_code == 422
    assert movement('wrong-out', 'MANUAL_OUT', '1.000000', reason='bad').status_code == 422
    assert movement('zero', 'ADJUSTMENT', '0.000000', reason='bad').status_code == 422
    assert movement('consumption', 'CONSUMPTION', '-1.000000', reason='b2').status_code == 422

    outgoing = movement('out', 'MANUAL_OUT', '-15.000000', reason='waste')
    assert outgoing.status_code == 201, outgoing.text
    stock = client.get(
        '/inventory/stock', headers=headers,
        params={'location_id': scope.location_id, 'inventory_item_id': item['id']},
    ).json()['items'][0]
    assert stock['quantity'] == '-5.000000'

    def reverse(key: str):
        return movement(
            key, 'REVERSAL', reversal_of_movement_id=outgoing.json()['id'],
            reason='correct waste entry',
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        reversals = tuple(
            future.result() for future in (
                pool.submit(reverse, 'reverse-a'),
                pool.submit(reverse, 'reverse-b'),
            )
        )
    assert sorted(value.status_code for value in reversals) == [201, 409]
    winner = next(value for value in reversals if value.status_code == 201).json()
    assert winner['quantity'] == '15.000000'
    assert winner['reversal_of_movement_id'] == outgoing.json()['id']
    assert movement(
        'reverse-reversal', 'REVERSAL', reversal_of_movement_id=winner['id'],
        reason='not allowed',
    ).status_code == 422

    final_stock = client.get(
        '/inventory/stock', headers=headers,
        params={'location_id': scope.location_id, 'inventory_item_id': item['id']},
    ).json()['items'][0]
    assert final_stock['quantity'] == '10.000000'
    movements = client.get(
        '/inventory/stock-movements', headers=headers,
        params={'location_id': scope.location_id, 'inventory_item_id': item['id']},
    ).json()['items']
    assert [value['movement_type'] for value in movements] == [
        'OPENING_BALANCE', 'MANUAL_OUT', 'REVERSAL',
    ]
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT SUM(quantity) AS quantity FROM stock_movements '
            'WHERE inventory_item_id=%s',
            (item['id'],),
        )
        assert cursor.fetchone()['quantity'] == Decimal('10.000000')
