from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_inventory_recipe_stock_foundation import (
    _headers,
    _item,
    _permission,
    _product,
    _scope,
)
from test_restaurant_order_inventory_consumption import (
    _confirm,
    _grant_inventory_read,
    _inventory_item,
    _open_and_join,
    _product as _order_product,
    _projection,
    _scope as _order_scope,
    _preview,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def test_published_versions_are_immutable_effective_dated_and_concurrent_safe(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, ('inventory.manage', 'inventory.read'))
    headers = _headers(client, scope)
    flour = _item(client, headers, scope.location_id, 'VERSION-FLOUR')
    conversion = client.post(
        f"/inventory-items/{flour['id']}/uom-conversions", headers=headers,
        json={
            'operational_uom': 'BAG', 'factor_to_base': '500.000000000000',
            'effective_at': '2025-12-01T00:00:00Z',
        },
    ).json()
    product_id = _product(connection, scope, 'Versioned recipe')
    url = f'/products/{product_id}/consumption-definition'

    v1_response = client.put(
        url, headers=headers, params={'location_id': scope.location_id},
        json={
            'expected_version': 0, 'tracking_mode': 'DERIVABLE',
            'effective_from': '2026-01-01T00:00:00Z',
            'components': [{
                'inventory_item_id': flour['id'], 'quantity': '1.000000',
                'uom': 'BAG',
            }],
        },
    )
    assert v1_response.status_code == 200, v1_response.text
    v1 = v1_response.json()
    assert v1['recipe_revision'] == 1
    assert v1['components'][0]['quantity'] == '500.000000'
    assert v1['components'][0]['source_quantity'] == '1.000000'
    assert v1['components'][0]['source_uom'] == 'BAG'
    assert v1['components'][0]['conversion_revision_id'] == conversion['id']

    v2_response = client.put(
        url, headers=headers, params={'location_id': scope.location_id},
        json={
            'expected_version': 1, 'tracking_mode': 'DERIVABLE',
            'effective_from': '2026-02-01T00:00:00Z',
            'components': [{
                'inventory_item_id': flour['id'], 'quantity': '0.200000',
                'uom': 'KG',
            }],
        },
    )
    assert v2_response.status_code == 200, v2_response.text
    v2 = v2_response.json()
    assert v2['recipe_revision'] == 2
    assert v2['recipe_version_id'] != v1['recipe_version_id']

    def at(value: str):
        return client.get(
            url, headers=headers,
            params={'location_id': scope.location_id, 'as_of': value},
        )

    assert at('2025-12-31T23:59:59Z').status_code == 404
    assert at('2026-01-01T00:00:00Z').json()['recipe_version_id'] == v1[
        'recipe_version_id'
    ]
    assert at('2026-01-31T23:59:59Z').json()['recipe_version_id'] == v1[
        'recipe_version_id'
    ]
    assert at('2026-02-01T00:00:00Z').json()['recipe_version_id'] == v2[
        'recipe_version_id'
    ]

    history = client.get(
        f'{url}/versions', headers=headers,
        params={'location_id': scope.location_id},
    ).json()['items']
    assert [value['recipe_revision'] for value in history] == [1, 2]
    assert history[0]['components'][0]['quantity'] == '500.000000'
    assert history[0]['effective_to'] == '2026-02-01T00:00:00'

    payload = {
        'expected_version': 2, 'tracking_mode': 'DERIVABLE',
        'effective_from': '2026-03-01T00:00:00Z',
        'components': [{
            'inventory_item_id': flour['id'], 'quantity': '0.300000', 'uom': 'KG',
        }],
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            future.result() for future in (
                pool.submit(
                    client.put, url, headers=headers,
                    params={'location_id': scope.location_id}, json=payload,
                ),
                pool.submit(
                    client.put, url, headers=headers,
                    params={'location_id': scope.location_id}, json=payload,
                ),
            )
        )
    assert sorted(value.status_code for value in results) == [200, 409]

    other = _scope(connection, f'{prefix}-other', ('inventory.read',))
    other_headers = _headers(client, other)
    assert client.get(
        f'{url}/versions', headers=other_headers,
        params={'location_id': other.location_id},
    ).status_code == 404


def test_order_acceptance_freezes_recipe_version_and_replay(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _order_scope(connection, prefix)
    _grant_inventory_read(connection, scope)
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT id FROM roles WHERE tenant_id=%s ORDER BY id LIMIT 1',
            (scope.tenant_id,),
        )
        role_id = int(cursor.fetchone()['id'])
    _permission(connection, role_id, 'inventory.manage')
    _, diner_headers = _open_and_join(client, scope)
    staff_headers = _headers(client, scope)
    product_id = _order_product(connection, scope, name='Frozen recipe', amount='50')
    ingredient_id = _inventory_item(connection, scope, 'Frozen ingredient')
    url = f'/products/{product_id}/consumption-definition'
    v1 = client.put(
        url, headers=staff_headers, params={'location_id': scope.location_id},
        json={
            'expected_version': 0, 'tracking_mode': 'DERIVABLE',
            'effective_from': '2026-01-01T00:00:00Z',
            'components': [{
                'inventory_item_id': ingredient_id, 'quantity': '10.000000',
                'uom': 'G',
            }],
        },
    ).json()

    preview = _preview(client, diner_headers, product_id)
    accepted = _confirm(client, diner_headers, preview, 'b3-version-freeze')
    assert accepted.status_code == 201, accepted.text
    order_id = accepted.json()['id']
    frozen = _projection(client, scope, order_id)
    movement = frozen['items'][0]['movements'][0]
    assert movement['consumption_version_id'] == v1['recipe_version_id']
    assert movement['consumption_version_component_id'] is not None
    assert movement['consumption_definition_version'] == 1
    assert movement['consumed_quantity'] == '10.000000'

    v2_response = client.put(
        url, headers=staff_headers, params={'location_id': scope.location_id},
        json={
            'expected_version': 1, 'tracking_mode': 'DERIVABLE',
            'components': [{
                'inventory_item_id': ingredient_id, 'quantity': '20.000000',
                'uom': 'G',
            }],
        },
    )
    assert v2_response.status_code == 200, v2_response.text
    assert v2_response.json()['recipe_version_id'] != v1['recipe_version_id']
    assert _projection(client, scope, order_id) == frozen

    replay = _confirm(client, diner_headers, preview, 'b3-version-freeze')
    assert replay.status_code == 200
    assert _projection(client, scope, order_id) == frozen
