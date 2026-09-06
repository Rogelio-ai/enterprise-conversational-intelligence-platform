from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.restaurant.inventory import order_consumption
from test_canonical_order_commercial_acceptance import (
    _confirm,
    _execute,
    _open_and_join,
    _preview,
    _product,
    _scope,
    _staff_headers,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _grant_inventory_read(connection, scope) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT r.id FROM roles r WHERE r.tenant_id=%s ORDER BY r.id LIMIT 1',
            (scope.tenant_id,),
        )
        role_id = int(cursor.fetchone()['id'])
        cursor.execute("SELECT id FROM permissions WHERE code='inventory.read'")
        permission_id = int(cursor.fetchone()['id'])
    _execute(
        connection,
        'INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',
        (role_id, permission_id),
    )


def _inventory_item(
    connection, scope, name: str, *, cost: str = '2.000000',
    currency: str = 'MXN', uom: str = 'G',
) -> int:
    return _execute(
        connection,
        'INSERT INTO inventory_items '
        '(tenant_id,organization_id,location_id,code,name,base_uom,'
        'standard_unit_cost,currency,status,version) '
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE',1)",
        (
            scope.tenant_id, scope.organization_id, scope.location_id,
            name.upper().replace(' ', '-'), name, uom, cost, currency,
        ),
    )


def _recipe(
    connection, scope, product_id: int, components=(), *,
    tracking_mode: str = 'DERIVABLE',
) -> tuple[int, list[int]]:
    definition_id = _execute(
        connection,
        'INSERT INTO product_consumption_definitions '
        '(tenant_id,organization_id,location_id,product_id,version,status,tracking_mode) '
        "VALUES (%s,%s,%s,%s,1,'ACTIVE',%s)",
        (
            scope.tenant_id, scope.organization_id, scope.location_id,
            product_id, tracking_mode,
        ),
    )
    component_ids = [
        _execute(
            connection,
            'INSERT INTO product_consumption_components '
            '(tenant_id,organization_id,location_id,definition_id,'
            'inventory_item_id,quantity) VALUES (%s,%s,%s,%s,%s,%s)',
            (
                scope.tenant_id, scope.organization_id, scope.location_id,
                definition_id, inventory_item_id, quantity,
            ),
        )
        for inventory_item_id, quantity in components
    ]
    return definition_id, component_ids


def _projection(client, scope, order_id: int):
    response = client.get(
        f'/restaurant-orders/{order_id}/theoretical-consumption',
        headers=_staff_headers(client, scope),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_simple_acceptance_consumes_once_freezes_cost_and_allows_negative_stock(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_inventory_read(connection, scope)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope, name='Coffee', amount='150')
    beans_id = _inventory_item(connection, scope, 'Beans', cost='2.000000')
    definition_id, component_ids = _recipe(
        connection, scope, product_id, ((beans_id, '10.000000'),)
    )

    preview = _preview(client, diner_headers, product_id)
    accepted = _confirm(client, diner_headers, preview, 'inventory-simple')
    assert accepted.status_code == 201, accepted.text
    order_id = accepted.json()['id']
    projected = _projection(client, scope, order_id)
    assert projected['coverage_status'] == 'COMPLETE'
    assert projected['historical_theoretical_cost'] == '20.000000000000'
    assert projected['theoretical_gross_margin'] == '130.000000000000'
    assert projected['theoretical_margin_percent'] == '86.6667'
    movement = projected['items'][0]['movements'][0]
    assert movement['consumed_quantity'] == '10.000000'
    assert movement['unit_cost'] == '2.000000'
    assert movement['extended_cost'] == '20.000000000000'

    replay = _confirm(client, diner_headers, preview, 'inventory-simple')
    assert replay.status_code == 200
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_order_consumptions '
            'WHERE restaurant_order_id=%s', (order_id,),
        )
        assert cursor.fetchone()['count'] == 1
        cursor.execute(
            "SELECT COUNT(*) AS count,SUM(quantity) AS quantity FROM stock_movements "
            "WHERE restaurant_order_id=%s AND movement_type='CONSUMPTION'", (order_id,),
        )
        row = cursor.fetchone()
        assert row['count'] == 1
        assert str(row['quantity']) == '-10.000000'

    connection.cursor().execute(
        'UPDATE inventory_items SET standard_unit_cost=9 WHERE id=%s', (beans_id,)
    )
    connection.cursor().execute(
        'UPDATE product_consumption_definitions SET version=2 WHERE id=%s',
        (definition_id,),
    )
    connection.cursor().execute(
        'UPDATE product_consumption_components SET quantity=99 WHERE id=%s',
        (component_ids[0],),
    )
    assert _projection(client, scope, order_id) == projected


def test_accepted_configuration_and_empty_combo_parent_drive_consumption(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_inventory_read(connection, scope)
    _, diner_headers = _open_and_join(client, scope)
    parent_id = _product(connection, scope, name='Combo', amount='100')
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT tax_classification_code FROM products WHERE id=%s', (parent_id,)
        )
        classification = cursor.fetchone()['tax_classification_code']
    fixed_id = _execute(
        connection,
        'INSERT INTO products '
        '(tenant_id,organization_id,name,tax_classification_code,status,source) '
        "VALUES (%s,%s,'Fries',%s,'ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id, classification),
    )
    choice_id = _execute(
        connection,
        'INSERT INTO products '
        '(tenant_id,organization_id,name,tax_classification_code,status,source) '
        "VALUES (%s,%s,'Cola',%s,'ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id, classification),
    )
    composition_id = _execute(
        connection,
        'INSERT INTO product_compositions '
        '(tenant_id,organization_id,product_id,status) VALUES (%s,%s,%s,\'ACTIVE\')',
        (scope.tenant_id, scope.organization_id, parent_id),
    )
    _execute(
        connection,
        'INSERT INTO product_components '
        '(tenant_id,organization_id,composition_id,component_product_id,'
        'quantity,display_order,status) VALUES (%s,%s,%s,%s,2,0,\'ACTIVE\')',
        (scope.tenant_id, scope.organization_id, composition_id, fixed_id),
    )
    group_id = _execute(
        connection,
        'INSERT INTO product_choice_groups '
        '(tenant_id,organization_id,composition_id,name,min_selections,'
        'max_selections,display_order,status) '
        "VALUES (%s,%s,%s,'Drink',1,1,0,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, composition_id),
    )
    option_id = _execute(
        connection,
        'INSERT INTO product_choice_options '
        '(tenant_id,organization_id,group_id,option_product_id,quantity,'
        'display_order,status) VALUES (%s,%s,%s,%s,1,0,\'ACTIVE\')',
        (scope.tenant_id, scope.organization_id, group_id, choice_id),
    )
    potato_id = _inventory_item(connection, scope, 'Potato', cost='1.000000')
    syrup_id = _inventory_item(connection, scope, 'Syrup', cost='1.000000')
    _recipe(connection, scope, parent_id, ())
    _recipe(connection, scope, fixed_id, ((potato_id, '3.000000'),))
    _recipe(connection, scope, choice_id, ((syrup_id, '5.000000'),))

    draft = client.post('/diner/order-draft', headers=diner_headers).json()
    item = client.post(
        '/diner/order-draft/items', headers=diner_headers,
        json={
            'product_id': parent_id, 'quantity': '1',
            'expected_version': draft['version'],
        },
    ).json()
    selected = client.put(
        f"/diner/order-draft/items/{item['items'][0]['item_id']}/choice-groups/{group_id}",
        headers=diner_headers,
        json={'option_ids': [option_id], 'expected_version': item['version']},
    )
    assert selected.status_code == 200, selected.text
    preview = client.get('/diner/checkout-preview', headers=diner_headers).json()
    accepted = _confirm(client, diner_headers, preview, 'inventory-combo')
    assert accepted.status_code == 201, accepted.text
    projected = _projection(client, scope, accepted.json()['id'])
    assert projected['coverage_status'] == 'COMPLETE'
    movements = projected['items'][0]['movements']
    assert [(value['source_product_id'], value['consumed_quantity']) for value in movements] == [
        (fixed_id, '6.000000'), (choice_id, '5.000000'),
    ]
    assert all(value['restaurant_order_item_component_id'] for value in movements)


@pytest.mark.parametrize(
    ('mode', 'currency', 'expected_reason', 'expected_movements'),
    (
        ('MISSING', 'MXN', 'MISSING_DEFINITION', 0),
        ('NON_DERIVABLE', 'MXN', 'NON_DERIVABLE', 0),
        ('DERIVABLE', 'USD', 'CURRENCY_MISMATCH', 1),
    ),
)
def test_incomplete_coverage_never_fabricates_cost_or_rejects_order(
    client, sql_connection, mode, currency, expected_reason, expected_movements,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_inventory_read(connection, scope)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope, name=f'Coverage {mode}', amount='50')
    if mode != 'MISSING':
        ingredient_id = _inventory_item(
            connection, scope, f'Ingredient {mode}', currency=currency
        )
        _recipe(
            connection, scope, product_id,
            ((ingredient_id, '1.000000'),) if mode == 'DERIVABLE' else (),
            tracking_mode=mode,
        )
    preview = _preview(client, diner_headers, product_id)
    accepted = _confirm(client, diner_headers, preview, f'coverage-{mode}')
    assert accepted.status_code == 201, accepted.text
    projected = _projection(client, scope, accepted.json()['id'])
    assert projected['coverage_status'] == 'PARTIAL'
    assert projected['historical_theoretical_cost'] is None
    assert projected['theoretical_gross_margin'] is None
    assert projected['theoretical_margin_percent'] is None
    assert projected['unresolved_evidence'][0]['reason'] == expected_reason
    assert len(projected['items'][0]['movements']) == expected_movements


def test_complete_zero_sale_has_null_margin_percent(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _grant_inventory_read(connection, scope)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope, name='Complimentary', amount='0')
    ingredient_id = _inventory_item(connection, scope, 'Gift ingredient')
    _recipe(connection, scope, product_id, ((ingredient_id, '1.000000'),))
    preview = _preview(client, diner_headers, product_id)
    accepted = _confirm(client, diner_headers, preview, 'zero-sale')
    assert accepted.status_code == 201, accepted.text
    projected = _projection(client, scope, accepted.json()['id'])
    assert projected['coverage_status'] == 'COMPLETE'
    assert projected['commercial_amount'] == '0.0000'
    assert projected['theoretical_gross_margin'] == '-2.000000000000'
    assert projected['theoretical_margin_percent'] is None


def test_materialization_failure_rolls_back_the_acceptance_transaction(
    client, sql_connection, monkeypatch,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _, diner_headers = _open_and_join(client, scope)
    product_id = _product(connection, scope, name='Rollback', amount='25')
    preview = _preview(client, diner_headers, product_id)
    monkeypatch.setattr(
        order_consumption,
        'materialize_accepted_order',
        AsyncMock(side_effect=RuntimeError('forced inventory persistence failure')),
    )
    response = _confirm(client, diner_headers, preview, 'rollback-inventory')
    assert response.status_code == 500
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_orders WHERE tenant_id=%s',
            (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            'SELECT COUNT(*) AS count FROM restaurant_order_consumptions '
            'WHERE tenant_id=%s', (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute(
            "SELECT COUNT(*) AS count FROM stock_movements "
            "WHERE tenant_id=%s AND movement_type='CONSUMPTION'", (scope.tenant_id,),
        )
        assert cursor.fetchone()['count'] == 0
