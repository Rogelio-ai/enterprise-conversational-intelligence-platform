from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_inventory_preparations import act, batch, opening, recipe
from test_inventory_recipe_stock_foundation import _headers, _item, _scope
from test_inventory_supplier_direct_receiving import _offering, _receipt, _supplier, _warehouse


PERMISSIONS = (
    'inventory.manage', 'inventory.read', 'inventory.cost.read',
    'inventory.supplier.manage', 'inventory.receipt.manage', 'inventory.receipt.accept',
    'inventory.purchase_order.read', 'inventory.purchase_order.manage',
    'inventory.purchase_order.approve', 'inventory.preparation.read',
    'inventory.preparation.manage', 'inventory.preparation.complete',
    'inventory.replenishment.read', 'inventory.replenishment.manage',
    'inventory.lot.read', 'inventory.valuation.read', 'inventory.valuation.create',
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _tracked_item(client, headers, location_id, code, cost='2', currency='MXN'):
    item = _item(client, headers, location_id, code, uom='UNIT', cost=cost, currency=currency)
    response = client.patch(f"/inventory-items/{item['id']}", headers=headers, json={
        'expected_version': item['version'], 'lot_tracking_policy': 'REQUIRED',
        'date_tracking_policy': 'BOTH',
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_replenishment_is_exact_advisory_and_keeps_on_order_distinct(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS); headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'B10-PAR', uom='UNIT', cost='2')
    opening(client, headers, item['id'], warehouse['id'], '3', 'b10-par-opening')
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) count FROM purchase_orders WHERE tenant_id=%s', (scope.tenant_id,))
        before = cursor.fetchone()['count']
    policy = client.put(
        f"/inventory/replenishment-policies/{warehouse['id']}/{item['id']}", headers=headers,
        json={'expected_version': 0, 'status': 'ACTIVE', 'minimum_quantity': '4',
              'target_quantity': '10', 'source_uom': 'UNIT'},
    )
    assert policy.status_code == 200, policy.text
    assert (policy.json()['on_hand'], policy.json()['on_order'], policy.json()['suggested_quantity']) == ('3.000000', '0.000000', '7.000000')
    assert client.put(
        f"/inventory/replenishment-policies/{warehouse['id']}/{item['id']}", headers=headers,
        json={'expected_version': 0, 'target_quantity': '11', 'source_uom': 'UNIT'},
    ).status_code == 409
    supplier = _supplier(client, headers, scope); offering = _offering(client, headers, supplier, scope, item, 'UNIT')
    po = client.post('/inventory/purchase-orders', headers=headers, json={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
        'supplier_id': supplier['id'], 'currency': 'MXN',
        'lines': [{'supplier_offering_id': offering['id'], 'ordered_quantity': '4', 'agreed_unit_price': '2'}],
    }).json()
    for action_name in ('submit', 'approve'):
        response = client.post(f"/inventory/purchase-orders/{po['id']}:{action_name}",
            headers={**headers, 'Idempotency-Key': f'b10-po-{action_name}'},
            json={'expected_version': po['version']})
        assert response.status_code == 200, response.text; po = response.json()
    projected = client.get('/inventory/replenishment-policies', headers=headers, params={'location_id': scope.location_id}).json()['items'][0]
    assert (projected['on_hand'], projected['on_order'], projected['suggested_quantity']) == ('3.000000', '4.000000', '7.000000')
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) count FROM purchase_orders WHERE tenant_id=%s', (scope.tenant_id,))
        assert cursor.fetchone()['count'] == before + 1


def test_received_and_prepared_lots_reconcile_without_expiry_writeoff(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS); headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    supplier = _supplier(client, headers, scope)
    date_tracked = _item(client, headers, scope.location_id, 'B10-DATE-REQUIRED', uom='UNIT', cost='2')
    date_tracked = client.patch(f"/inventory-items/{date_tracked['id']}", headers=headers, json={
        'expected_version': date_tracked['version'], 'date_tracking_policy': 'EXPIRY',
    }).json()
    date_offering = _offering(client, headers, supplier, scope, date_tracked, 'UNIT')
    missing_date = _receipt(client, headers, supplier, scope, warehouse, [{
        'supplier_offering_id': date_offering['id'], 'received_quantity': '1',
        'accepted_quantity': '1', 'rejected_quantity': '0', 'unit_cost': '2',
        'currency': 'MXN',
    }])
    rejected = client.post(f"/inventory/goods-receipts/{missing_date['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'b10-missing-required-date'},
        json={'expected_version': missing_date['version']})
    assert rejected.status_code == 409 and 'Expiry date is required' in rejected.text
    received = _tracked_item(client, headers, scope.location_id, 'B10-RECEIVED')
    offering = _offering(client, headers, supplier, scope, received, 'UNIT')
    receipt = _receipt(client, headers, supplier, scope, warehouse, [{
        'supplier_offering_id': offering['id'], 'received_quantity': '5',
        'accepted_quantity': '5', 'rejected_quantity': '0', 'unit_cost': '3',
        'currency': 'MXN', 'lot_code': 'LOT-R-001', 'manufacture_date': '2026-01-01',
        'expiry_date': '2026-02-01', 'best_before_date': '2026-01-20',
    }])
    accepted = client.post(f"/inventory/goods-receipts/{receipt['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'b10-receipt'}, json={'expected_version': receipt['version']})
    assert accepted.status_code == 200, accepted.text
    raw = _item(client, headers, scope.location_id, 'B10-RAW', uom='UNIT', cost='4')
    prepared = _tracked_item(client, headers, scope.location_id, 'B10-PREPARED', cost='1')
    opening(client, headers, raw['id'], warehouse['id'], '2', 'b10-prep-opening')
    version = recipe(client, headers, scope, prepared, [{
        'inventory_item_id': raw['id'], 'expected_quantity': '2', 'source_uom': 'UNIT', 'yield_basis': True,
    }], expected='1')
    value_response = client.post('/inventory/preparation-batches', headers=headers, json={
        'recipe_version_id': version['id'], 'warehouse_id': warehouse['id'], 'reference': 'B10-PREP-LOT',
        'inputs': [{'recipe_component_id': version['components'][0]['id'], 'source_quantity': '2', 'source_uom': 'UNIT'}],
        'output_quantity': '1', 'output_uom': 'UNIT', 'output_lot_code': 'LOT-P-001',
        'manufacture_date': '2026-09-01', 'expiry_date': '2027-09-01',
        'best_before_date': '2027-08-01',
    })
    assert value_response.status_code == 201, value_response.text
    value = act(client, headers, value_response.json(), 'start').json()
    completed = act(client, headers, value, 'complete', 'b10-prep-complete')
    assert completed.status_code == 200, completed.text
    lots = client.get('/inventory/lots', headers=headers, params={'location_id': scope.location_id}).json()['items']
    assert {row['origin_type'] for row in lots} == {'GOODS_RECEIPT', 'PREPARATION_BATCH'}
    receipt_lot = next(row for row in lots if row['lot_code'] == 'LOT-R-001')
    prepared_lot = next(row for row in lots if row['lot_code'] == 'LOT-P-001')
    assert receipt_lot['date_state'] == 'EXPIRED' and receipt_lot['balance'] == '5.000000'
    assert prepared_lot['balance'] == '1.000000'
    with connection.cursor() as cursor:
        for row in (receipt_lot, prepared_lot):
            cursor.execute('SELECT COALESCE(SUM(quantity),0) quantity FROM stock_movements WHERE inventory_lot_id=%s', (row['id'],))
            assert cursor.fetchone()['quantity'] == Decimal(row['balance'])
        cursor.execute('SELECT COUNT(*) count FROM inventory_losses WHERE tenant_id=%s', (scope.tenant_id,))
        assert cursor.fetchone()['count'] == 0
        cursor.execute("SELECT permission_id FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id WHERE rp.role_id=%s AND p.code='inventory.cost.read'", (scope.role_id,))
        permission_id = cursor.fetchone()['permission_id']; cursor.execute('DELETE FROM role_permissions WHERE role_id=%s AND permission_id=%s', (scope.role_id, permission_id))
    hidden = client.get('/inventory/lots', headers=headers, params={'location_id': scope.location_id}).json()['items']
    assert all(row['cost_visible'] is False and row['unit_cost_evidence'] is None for row in hidden)


def test_standard_cost_snapshot_is_as_of_immutable_idempotent_and_private(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS); headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    mxn = _item(client, headers, scope.location_id, 'B10-VALUE', uom='UNIT', cost='2')
    usd = _item(client, headers, scope.location_id, 'B10-USD', uom='UNIT', cost='3', currency='USD')
    opening(client, headers, mxn['id'], warehouse['id'], '4', 'b10-value-opening')
    opening(client, headers, usd['id'], warehouse['id'], '1', 'b10-usd-opening')
    with connection.cursor() as cursor:
        cursor.execute('SELECT CURRENT_TIMESTAMP as now'); as_of = cursor.fetchone()['now'].isoformat()
    payload = {'warehouse_id': warehouse['id'], 'as_of': as_of, 'currency': 'MXN', 'valuation_method': 'STANDARD_COST'}
    first = client.post('/inventory/valuation-snapshots', headers={**headers, 'Idempotency-Key': 'b10-value'}, json=payload)
    assert first.status_code == 201, first.text
    frozen = first.json(); assert frozen['valuation_method'] == 'STANDARD_COST'
    assert frozen['derivable_total_value'] == '8.000000000000' and frozen['non_derivable_line_count'] == 1
    assert {row['evidence_status'] for row in frozen['lines']} == {'RESOLVED', 'CURRENCY_MISMATCH'}
    equivalent_offset = datetime.fromisoformat(as_of).replace(tzinfo=timezone.utc).astimezone(
        timezone(timedelta(hours=-6))
    ).isoformat()
    offset_snapshot = client.post('/inventory/valuation-snapshots', headers={**headers, 'Idempotency-Key': 'b10-value-offset'}, json={**payload, 'as_of': equivalent_offset})
    assert offset_snapshot.status_code == 201, offset_snapshot.text
    offset_value = offset_snapshot.json()
    assert offset_value['as_of'] == frozen['as_of']
    assert [(row['inventory_item_id'], row['quantity_as_of'], row['evidence_status'], row['unit_cost_evidence']) for row in offset_value['lines']] == [(row['inventory_item_id'], row['quantity_as_of'], row['evidence_status'], row['unit_cost_evidence']) for row in frozen['lines']]
    replay = client.post('/inventory/valuation-snapshots', headers={**headers, 'Idempotency-Key': 'b10-value'}, json=payload)
    assert replay.status_code == 201 and replay.headers['Idempotent-Replay'] == 'true' and replay.json() == frozen
    updated = client.patch(f"/inventory-items/{mxn['id']}", headers=headers, json={
        'expected_version': mxn['version'], 'standard_unit_cost': '9', 'currency': 'MXN',
    })
    assert updated.status_code == 200, updated.text
    later = client.post('/inventory/stock-movements', headers={**headers, 'Idempotency-Key': 'b10-later-movement'}, json={
        'inventory_item_id': mxn['id'], 'warehouse_id': warehouse['id'],
        'movement_type': 'MANUAL_IN', 'quantity': '1', 'uom': 'UNIT',
        'reversal_of_movement_id': None, 'reason': 'Later evidence', 'reference': 'B10-LATER',
    })
    assert later.status_code == 201, later.text
    listed = next(row for row in client.get('/inventory/valuation-snapshots', headers=headers, params={'location_id': scope.location_id}).json()['items'] if row['id'] == frozen['id'])
    assert listed == frozen
    with connection.cursor() as cursor:
        cursor.execute("SELECT permission_id FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id WHERE rp.role_id=%s AND p.code='inventory.cost.read'", (scope.role_id,))
        permission_id = cursor.fetchone()['permission_id']; cursor.execute('DELETE FROM role_permissions WHERE role_id=%s AND permission_id=%s', (scope.role_id, permission_id))
    hidden = client.get('/inventory/valuation-snapshots', headers=headers, params={'location_id': scope.location_id}).json()['items'][0]
    assert hidden['cost_visible'] is False and hidden['currency'] is None and hidden['derivable_total_value'] is None
    assert all(row['unit_cost_evidence'] is None and row['line_value'] is None for row in hidden['lines'])
