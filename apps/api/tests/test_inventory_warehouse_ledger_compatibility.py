from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_inventory_recipe_stock_foundation import (
    _execute,
    _headers,
    _item,
    _scope,
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _movement(client, headers, key: str, item_id: int, movement_type: str, **values):
    return client.post(
        '/inventory/stock-movements',
        headers={**headers, 'Idempotency-Key': key},
        json={
            'inventory_item_id': item_id,
            'movement_type': movement_type,
            **values,
        },
    )


def _set_policy(client, headers, warehouse: dict, policy: str) -> dict:
    response = client.patch(
        f"/inventory/warehouses/{warehouse['id']}",
        headers=headers,
        json={
            'expected_version': warehouse['version'],
            'negative_stock_policy': policy,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_default_warehouse_scope_policy_reversal_and_idempotency(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, ('inventory.manage', 'inventory.read'))
    headers = _headers(client, scope)

    warehouses = client.get(
        '/inventory/warehouses', headers=headers,
        params={'location_id': scope.location_id},
    )
    assert warehouses.status_code == 200, warehouses.text
    warehouse = warehouses.json()['items'][0]
    assert (
        warehouse['code'], warehouse['is_default'],
        warehouse['negative_stock_policy'], warehouse['version'],
    ) == ('DEFAULT', True, 'ALLOW', 1)

    legacy_item = _item(client, headers, scope.location_id, 'LEGACY-REPLAY')
    legacy_payload = {
        'schema_version': 1,
        'inventory_item_id': legacy_item['id'],
        'movement_type': 'MANUAL_IN',
        'quantity': '2.000000',
        'reversal_of_movement_id': None,
        'reason': 'legacy replay',
        'reference': None,
    }
    legacy_fingerprint = hashlib.sha256(
        json.dumps(
            legacy_payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
        ).encode('utf-8')
    ).hexdigest()
    legacy_movement_id = _execute(
        connection,
        'INSERT INTO stock_movements '
        '(tenant_id,organization_id,location_id,warehouse_id,inventory_item_id,'
        'movement_type,quantity,reversal_of_movement_id,reason,reference,recorded_at,'
        'actor_type,actor_id,actor_reference,opening_balance_slot,'
        'idempotency_actor_scope,idempotency_key,request_schema_version,'
        'request_fingerprint,negative_stock_policy,negative_stock_warning,'
        'resulting_stock_quantity) '
        "VALUES (%s,%s,%s,%s,%s,'MANUAL_IN',2.000000,NULL,'legacy replay',NULL,"
        "CURRENT_TIMESTAMP,'EMPLOYEE',%s,NULL,NULL,%s,'legacy-replay',1,%s,"
        "'ALLOW',0,2.000000)",
        (
            scope.tenant_id, scope.organization_id, scope.location_id,
            warehouse['id'], legacy_item['id'], scope.membership_id,
            f'EMPLOYEE:{scope.membership_id}', legacy_fingerprint,
        ),
    )
    legacy_replay = _movement(
        client, headers, 'legacy-replay', legacy_item['id'], 'MANUAL_IN',
        quantity='2.000000', reason='legacy replay',
    )
    assert legacy_replay.status_code == 200, legacy_replay.text
    assert legacy_replay.json()['id'] == legacy_movement_id
    assert legacy_replay.json()['warehouse_id'] == warehouse['id']

    item = _item(client, headers, scope.location_id, 'WAREHOUSE-STOCK')
    opening = _movement(
        client, headers, 'b1-opening', item['id'], 'OPENING_BALANCE',
        quantity='10.000000',
    )
    assert opening.status_code == 201, opening.text
    assert opening.json()['warehouse_id'] == warehouse['id']
    assert opening.json()['negative_stock_policy'] == 'ALLOW'
    assert opening.json()['negative_stock_warning'] is False
    assert opening.json()['resulting_stock_quantity'] == '10.000000'
    replay = _movement(
        client, headers, 'b1-opening', item['id'], 'OPENING_BALANCE',
        quantity='10.000000',
    )
    assert replay.status_code == 200
    assert replay.json()['id'] == opening.json()['id']
    conflict = _movement(
        client, headers, 'b1-opening', item['id'], 'OPENING_BALANCE',
        warehouse_id=warehouse['id'], quantity='10.000000',
    )
    assert conflict.status_code == 409

    warehouse = _set_policy(client, headers, warehouse, 'WARN')
    warning = _movement(
        client, headers, 'b1-warn', item['id'], 'MANUAL_OUT',
        warehouse_id=warehouse['id'], quantity='-15.000000', reason='warning test',
    )
    assert warning.status_code == 201, warning.text
    assert warning.json()['negative_stock_policy'] == 'WARN'
    assert warning.json()['negative_stock_warning'] is True
    assert warning.json()['resulting_stock_quantity'] == '-5.000000'

    warehouse = _set_policy(client, headers, warehouse, 'BLOCK')
    blocked = _movement(
        client, headers, 'b1-blocked', item['id'], 'MANUAL_OUT',
        warehouse_id=warehouse['id'], quantity='-1.000000', reason='blocked test',
    )
    assert blocked.status_code == 409
    assert blocked.json()['error']['code'] == 'NEGATIVE_STOCK_BLOCKED'

    reversal = _movement(
        client, headers, 'b1-reversal', item['id'], 'REVERSAL',
        warehouse_id=warehouse['id'], reversal_of_movement_id=warning.json()['id'],
        reason='correct warning movement',
    )
    assert reversal.status_code == 201, reversal.text
    assert reversal.json()['warehouse_id'] == warehouse['id']
    assert reversal.json()['resulting_stock_quantity'] == '10.000000'
    assert _movement(
        client, headers, 'b1-reversal-2', item['id'], 'REVERSAL',
        warehouse_id=warehouse['id'], reversal_of_movement_id=warning.json()['id'],
        reason='duplicate correction',
    ).status_code == 409

    stock = client.get(
        '/inventory/stock', headers=headers,
        params={
            'location_id': scope.location_id,
            'warehouse_id': warehouse['id'],
            'inventory_item_id': item['id'],
        },
    )
    assert stock.status_code == 200, stock.text
    assert stock.json()['items'][0]['quantity'] == '10.000000'
    assert stock.json()['items'][0]['warehouse_id'] == warehouse['id']

    other_location_id = _execute(
        connection,
        'INSERT INTO locations '
        '(tenant_id,organization_id,code,name,timezone,status) '
        "VALUES (%s,%s,'OTHER','Other','America/Mexico_City','ACTIVE')",
        (scope.tenant_id, scope.organization_id),
    )
    other_warehouse_id = _execute(
        connection,
        'INSERT INTO warehouses '
        '(tenant_id,organization_id,location_id,code,name,status,default_slot,'
        'negative_stock_policy,version) '
        "VALUES (%s,%s,%s,'DEFAULT','Other Default','ACTIVE',1,'ALLOW',1)",
        (scope.tenant_id, scope.organization_id, other_location_id),
    )
    cross_location = _movement(
        client, headers, 'b1-cross-location', item['id'], 'MANUAL_IN',
        warehouse_id=other_warehouse_id, quantity='1.000000', reason='wrong scope',
    )
    assert cross_location.status_code == 404
    assert client.get(
        '/inventory/stock', headers=headers,
        params={
            'location_id': scope.location_id,
            'warehouse_id': other_warehouse_id,
        },
    ).status_code == 404

    other_organization_id = _execute(
        connection,
        'INSERT INTO organizations (tenant_id,code,name,status) '
        "VALUES (%s,'OTHER-ORG','Other Organization','ACTIVE')",
        (scope.tenant_id,),
    )
    other_organization_location_id = _execute(
        connection,
        'INSERT INTO locations '
        '(tenant_id,organization_id,code,name,timezone,status) '
        "VALUES (%s,%s,'OTHER-ORG-LOC','Other Org Location',"
        "'America/Mexico_City','ACTIVE')",
        (scope.tenant_id, other_organization_id),
    )
    other_organization_warehouse_id = _execute(
        connection,
        'INSERT INTO warehouses '
        '(tenant_id,organization_id,location_id,code,name,status,default_slot,'
        'negative_stock_policy,version) '
        "VALUES (%s,%s,%s,'DEFAULT','Other Org Default','ACTIVE',1,'ALLOW',1)",
        (
            scope.tenant_id, other_organization_id,
            other_organization_location_id,
        ),
    )
    assert _movement(
        client, headers, 'b1-cross-organization', item['id'], 'MANUAL_IN',
        warehouse_id=other_organization_warehouse_id,
        quantity='1.000000', reason='wrong organization',
    ).status_code == 404

    other_tenant = _scope(
        connection, f'{prefix}-other-tenant', ('inventory.manage', 'inventory.read')
    )
    other_headers = _headers(client, other_tenant)
    assert _movement(
        client, other_headers, 'b1-cross-tenant', item['id'], 'MANUAL_IN',
        warehouse_id=warehouse['id'], quantity='1.000000', reason='wrong tenant',
    ).status_code == 404

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT SUM(quantity) AS quantity FROM stock_movements '
            'WHERE warehouse_id=%s AND inventory_item_id=%s',
            (warehouse['id'], item['id']),
        )
        assert cursor.fetchone()['quantity'] == Decimal('10.000000')


def test_block_policy_serializes_concurrent_outbound_movements(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, ('inventory.manage', 'inventory.read'))
    headers = _headers(client, scope)
    item = _item(client, headers, scope.location_id, 'BLOCK-RACE')
    warehouse = client.get(
        '/inventory/warehouses', headers=headers,
        params={'location_id': scope.location_id},
    ).json()['items'][0]
    assert _movement(
        client, headers, 'race-opening', item['id'], 'OPENING_BALANCE',
        warehouse_id=warehouse['id'], quantity='10.000000',
    ).status_code == 201
    warehouse = _set_policy(client, headers, warehouse, 'BLOCK')

    def outbound(key: str):
        return _movement(
            client, headers, key, item['id'], 'MANUAL_OUT',
            warehouse_id=warehouse['id'], quantity='-7.000000', reason='race test',
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = tuple(
            future.result() for future in (
                pool.submit(outbound, 'race-a'),
                pool.submit(outbound, 'race-b'),
            )
        )
    assert sorted(value.status_code for value in responses) == [201, 409]
    loser = next(value for value in responses if value.status_code == 409)
    assert loser.json()['error']['code'] == 'NEGATIVE_STOCK_BLOCKED'
    stock = client.get(
        '/inventory/stock', headers=headers,
        params={
            'location_id': scope.location_id,
            'warehouse_id': warehouse['id'],
            'inventory_item_id': item['id'],
        },
    ).json()['items'][0]
    assert stock['quantity'] == '3.000000'
