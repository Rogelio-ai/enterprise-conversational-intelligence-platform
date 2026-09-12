from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_inventory_dedicated_loss import _second_actor
from test_inventory_recipe_stock_foundation import _headers, _item, _scope
from test_inventory_supplier_direct_receiving import (
    _conversion, _line, _offering, _receipt, _supplier, _warehouse,
)


PERMISSIONS = (
    'inventory.manage', 'inventory.read', 'inventory.cost.read',
    'inventory.supplier.manage', 'inventory.receipt.manage', 'inventory.receipt.accept',
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def test_inventory_intelligence_uses_authorities_weighted_cost_and_server_masking(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'B7-ITEM', uom='UNIT', cost='8')
    _conversion(client, headers, item['id'], factor='10')
    supplier = _supplier(client, headers, scope, code='B7-SUPPLIER')
    offering = _offering(client, headers, supplier, scope, item)

    for index, cost in enumerate(('100', '120', '140'), start=1):
        receipt = _receipt(
            client, headers, supplier, scope, warehouse,
            [_line(offering, received='1', accepted='1', rejected='0', cost=cost)],
            reference=f'B7-R-{index}',
        )
        accepted = client.post(
            f"/inventory/goods-receipts/{receipt['id']}:accept",
            headers={**headers, 'Idempotency-Key': f'b7-accept-{index}'},
            json={'expected_version': receipt['version']},
        )
        assert accepted.status_code == 200, accepted.text

    response = client.get('/inventory/intelligence', headers=headers, params={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    row = body['stock'][0]
    assert body['cost_visible'] is True
    assert row['quantity'] == '30.000000'
    assert row['standard_unit_cost'] == '8.000000'
    assert row['inventory_value_at_standard_cost'] == '240.000000'
    assert row['purchase_cost']['last_purchase_cost'] == '14.000000'
    assert row['purchase_cost']['recent_weighted_purchase_cost'] == '12.000000'
    assert row['purchase_cost']['selected_window_days'] == 30
    assert row['purchase_cost']['accepted_receipt_events'] == 3
    assert row['purchase_cost']['weighted_vs_standard_absolute'] == '4.000000'
    assert row['stock_source'] == 'SUM_STOCK_MOVEMENT_QUANTITY'
    assert body['recent_receipts'][0]['source'] == 'GOODS_RECEIPT_ACCEPTED'

    reader = _second_actor(connection, scope, f'{prefix}-quantity-reader', ('inventory.read',))
    masked = client.get('/inventory/intelligence', headers=_headers(client, reader), params={
        'location_id': scope.location_id,
    })
    assert masked.status_code == 200, masked.text
    masked_body = masked.json()
    assert masked_body['cost_visible'] is False
    assert masked_body['stock'][0]['standard_unit_cost'] is None
    assert masked_body['stock'][0]['inventory_value_at_standard_cost'] is None
    assert masked_body['stock'][0]['purchase_cost'] is None
    assert masked_body['stock'][0]['quantity'] == '30.000000'

    other = _scope(connection, f'{prefix}-other', ('inventory.read',))
    denied = client.get('/inventory/intelligence', headers=_headers(client, other), params={
        'location_id': scope.location_id,
    })
    assert denied.status_code == 404
