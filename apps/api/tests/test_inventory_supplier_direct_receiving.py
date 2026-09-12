from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_inventory_recipe_stock_foundation import _headers, _item, _scope


PERMISSIONS = (
    'inventory.manage', 'inventory.read', 'inventory.supplier.manage',
    'inventory.receipt.manage', 'inventory.receipt.accept', 'inventory.cost.read',
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _warehouse(client, headers, location_id):
    response = client.get(
        '/inventory/warehouses', headers=headers, params={'location_id': location_id},
    )
    assert response.status_code == 200, response.text
    return response.json()['items'][0]


def _supplier(client, headers, scope, code='SUPPLIER-1'):
    response = client.post('/inventory/suppliers', headers=headers, json={
        'organization_id': scope.organization_id, 'code': code,
        'name': f'{code} Name', 'contact_reference': 'operator@example.test',
        'location_ids': [scope.location_id],
    })
    assert response.status_code == 201, response.text
    return response.json()


def _offering(client, headers, supplier, scope, item, uom='BOX'):
    response = client.post(
        f"/inventory/suppliers/{supplier['id']}/offerings", headers=headers,
        json={
            'location_id': scope.location_id, 'inventory_item_id': item['id'],
            'supplier_item_code': f"SKU-{item['id']}", 'purchase_uom': uom,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _conversion(client, headers, item_id, factor='50.000000000000'):
    response = client.post(
        f'/inventory-items/{item_id}/uom-conversions', headers=headers,
        json={'operational_uom': 'BOX', 'factor_to_base': factor},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _receipt(client, headers, supplier, scope, warehouse, lines, reference=None):
    response = client.post('/inventory/goods-receipts', headers=headers, json={
        'supplier_id': supplier['id'], 'location_id': scope.location_id,
        'warehouse_id': warehouse['id'], 'external_reference': reference,
        'lines': lines,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _line(offering, received='2.000000', accepted='1.500000', rejected='0.500000',
          cost='100.000000', currency='MXN'):
    return {
        'supplier_offering_id': offering['id'],
        'received_quantity': received, 'accepted_quantity': accepted,
        'rejected_quantity': rejected, 'unit_cost': cost, 'currency': currency,
    }


def test_supplier_offering_authority_lifecycle_and_isolation(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    supplier = _supplier(client, headers, scope)
    assert supplier['status'] == 'ACTIVE'
    assert supplier['location_ids'] == [scope.location_id]

    duplicate = client.post('/inventory/suppliers', headers=headers, json={
        'organization_id': scope.organization_id, 'code': supplier['code'],
        'name': 'Duplicate', 'location_ids': [scope.location_id],
    })
    assert duplicate.status_code == 409

    item = _item(client, headers, scope.location_id, 'RECEIVE-UNIT', cost='4.000000')
    assert client.post(
        f"/inventory/suppliers/{supplier['id']}/offerings", headers=headers,
        json={
            'location_id': scope.location_id, 'inventory_item_id': item['id'],
            'purchase_uom': 'BOX',
        },
    ).status_code == 422
    _conversion(client, headers, item['id'])
    offering = _offering(client, headers, supplier, scope, item)
    assert offering['purchase_uom'] == 'BOX'
    assert client.get(
        f"/inventory/suppliers/{supplier['id']}/offerings", headers=headers,
        params={'location_id': scope.location_id},
    ).json()['items'][0]['id'] == offering['id']

    inactive = client.patch(
        f"/inventory/supplier-offerings/{offering['id']}", headers=headers,
        json={'expected_version': 1, 'status': 'INACTIVE'},
    )
    assert inactive.status_code == 200
    assert inactive.json()['version'] == 2
    assert client.patch(
        f"/inventory/supplier-offerings/{offering['id']}", headers=headers,
        json={'expected_version': 1, 'status': 'ACTIVE'},
    ).status_code == 409

    other = _scope(connection, f'{prefix}-other', PERMISSIONS)
    other_headers = _headers(client, other)
    assert client.get(
        f"/inventory/suppliers/{supplier['id']}", headers=other_headers,
        params={'location_id': other.location_id},
    ).status_code == 404
    assert client.patch(
        f"/inventory/supplier-offerings/{offering['id']}", headers=other_headers,
        json={'expected_version': 2, 'status': 'ACTIVE'},
    ).status_code == 404
    assert client.patch(
        f"/inventory/suppliers/{supplier['id']}", headers=other_headers,
        json={'expected_version': 1, 'status': 'INACTIVE'},
    ).status_code == 404


def test_supplier_location_availability_is_active_and_not_duplicate_identity(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    supplier = _supplier(client, headers, scope)
    with connection.cursor() as cursor:
        cursor.execute(
            'INSERT INTO locations '
            '(tenant_id,organization_id,code,name,timezone,status) '
            "VALUES (%s,%s,'LOC-2','Location 2','America/Mexico_City','ACTIVE')",
            (scope.tenant_id, scope.organization_id),
        )
        second_location_id = int(cursor.lastrowid)
        cursor.execute(
            'INSERT INTO membership_location_grants '
            '(tenant_id,membership_id,location_id) VALUES (%s,%s,%s)',
            (scope.tenant_id, scope.membership_id, second_location_id),
        )

    response = client.patch(
        f"/inventory/suppliers/{supplier['id']}", headers=headers,
        json={
            'expected_version': 1,
            'location_ids': [scope.location_id, second_location_id],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()['id'] == supplier['id']
    assert set(response.json()['location_ids']) == {
        scope.location_id, second_location_id,
    }

    response = client.patch(
        f"/inventory/suppliers/{supplier['id']}", headers=headers,
        json={'expected_version': 2, 'location_ids': [second_location_id]},
    )
    assert response.status_code == 200, response.text
    assert response.json()['location_ids'] == [second_location_id]
    assert client.get(
        f"/inventory/suppliers/{supplier['id']}", headers=headers,
        params={'location_id': scope.location_id},
    ).status_code == 404
    assert client.get(
        f"/inventory/suppliers/{supplier['id']}/offerings", headers=headers,
        params={'location_id': scope.location_id},
    ).status_code == 404
    listed = client.get(
        '/inventory/suppliers', headers=headers,
        params={'location_id': scope.location_id},
    )
    assert listed.status_code == 200
    assert listed.json()['items'] == []


def test_receipt_draft_acceptance_freezes_uom_cost_and_rejected_quantity(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(
        client, headers, scope.location_id, 'RECEIPT-BOX',
        uom='UNIT', cost='4.000000',
    )
    first_conversion = _conversion(client, headers, item['id'])
    supplier = _supplier(client, headers, scope)
    offering = _offering(client, headers, supplier, scope, item)
    receipt = _receipt(
        client, headers, supplier, scope, warehouse, [_line(offering)], 'DELIVERY-1',
    )
    assert receipt['status'] == 'DRAFT'
    assert receipt['lines'][0]['normalized_quantity'] is None
    stock_before = client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'inventory_item_id': item['id'],
        'warehouse_id': warehouse['id'],
    }).json()['items'][0]['quantity']
    assert stock_before == '0.000000'

    accepted_response = client.post(
        f"/inventory/goods-receipts/{receipt['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'accept-delivery-1'},
        json={'expected_version': 1},
    )
    assert accepted_response.status_code == 200, accepted_response.text
    accepted = accepted_response.json()
    assert accepted['status'] == 'ACCEPTED'
    line = accepted['lines'][0]
    assert line['received_quantity'] == '2.000000'
    assert line['accepted_quantity'] == '1.500000'
    assert line['rejected_quantity'] == '0.500000'
    assert line['source_uom'] == 'BOX'
    assert line['conversion_revision_id'] == first_conversion['id']
    assert line['conversion_factor'] == '50.000000000000'
    assert line['base_uom_evidence'] == 'UNIT'
    assert line['normalized_quantity'] == '75.000000'
    assert line['unit_cost'] == '100.000000'
    assert line['extended_cost'] == '150.000000000000'
    assert line['stock_movement_id'] is not None

    movement = next(row for row in client.get(
        '/inventory/stock-movements', headers=headers, params={
            'location_id': scope.location_id, 'inventory_item_id': item['id'],
        },
    ).json()['items'] if row['id'] == line['stock_movement_id'])
    assert movement['movement_type'] == 'GOODS_RECEIPT'
    assert movement['warehouse_id'] == warehouse['id']
    assert movement['quantity'] == '75.000000'
    assert movement['source_quantity'] == '1.500000'
    assert movement['goods_receipt_id'] == receipt['id']
    assert movement['goods_receipt_line_id'] == line['id']
    assert movement['standard_unit_cost_evidence'] == '4.000000'
    assert movement['extended_standard_cost'] == '300.000000000000'

    replay = client.post(
        f"/inventory/goods-receipts/{receipt['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'accept-delivery-1'},
        json={'expected_version': 1},
    )
    assert replay.status_code == 200
    assert replay.headers['Idempotent-Replay'] == 'true'
    assert replay.json() == accepted

    _conversion(client, headers, item['id'], factor='40.000000000000')
    frozen = client.get(
        f"/inventory/goods-receipts/{receipt['id']}", headers=headers,
    ).json()['lines'][0]
    assert frozen['conversion_revision_id'] == first_conversion['id']
    assert frozen['normalized_quantity'] == '75.000000'
    assert frozen['extended_cost'] == '150.000000000000'
    assert client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'inventory_item_id': item['id'],
        'warehouse_id': warehouse['id'],
    }).json()['items'][0]['quantity'] == '75.000000'


def test_cancel_concurrency_and_failed_acceptance_are_stock_safe(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    supplier = _supplier(client, headers, scope)
    item_a = _item(
        client, headers, scope.location_id, 'ATOMIC-A', uom='UNIT', cost='1.000000',
    )
    item_b = _item(
        client, headers, scope.location_id, 'ATOMIC-B', uom='UNIT', cost='2.000000',
    )
    offering_a = _offering(client, headers, supplier, scope, item_a, uom='UNIT')
    offering_b = _offering(client, headers, supplier, scope, item_b, uom='UNIT')

    cancelled = _receipt(
        client, headers, supplier, scope, warehouse,
        [_line(offering_a, received='1', accepted='1', rejected='0')], 'CANCEL-1',
    )
    cancelled_response = client.post(
        f"/inventory/goods-receipts/{cancelled['id']}:cancel", headers=headers,
        json={'expected_version': 1},
    )
    assert cancelled_response.status_code == 200
    assert cancelled_response.json()['status'] == 'CANCELLED'
    assert client.post(
        f"/inventory/goods-receipts/{cancelled['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'cancelled-accept'},
        json={'expected_version': 2},
    ).status_code == 409

    invalid = _receipt(
        client, headers, supplier, scope, warehouse,
        [
            _line(offering_a, received='1', accepted='1', rejected='0'),
            _line(offering_b, received='1', accepted='1', rejected='0'),
        ], 'ATOMIC-FAIL',
    )
    assert client.patch(
        f"/inventory/supplier-offerings/{offering_b['id']}", headers=headers,
        json={'expected_version': 1, 'status': 'INACTIVE'},
    ).status_code == 200
    failed = client.post(
        f"/inventory/goods-receipts/{invalid['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'atomic-fail'},
        json={'expected_version': 1},
    )
    assert failed.status_code == 422
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM stock_movements WHERE goods_receipt_id=%s',
            (invalid['id'],),
        )
        assert cursor.fetchone()['count'] == 0
        cursor.execute('SELECT status FROM goods_receipts WHERE id=%s', (invalid['id'],))
        assert cursor.fetchone()['status'] == 'DRAFT'

    assert client.patch(
        f"/inventory/supplier-offerings/{offering_b['id']}", headers=headers,
        json={'expected_version': 2, 'status': 'ACTIVE'},
    ).status_code == 200
    concurrent = _receipt(
        client, headers, supplier, scope, warehouse,
        [_line(offering_a, received='3', accepted='3', rejected='0')], 'CONCURRENT-1',
    )

    def accept(key):
        return client.post(
            f"/inventory/goods-receipts/{concurrent['id']}:accept",
            headers={**headers, 'Idempotency-Key': key},
            json={'expected_version': 1},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(accept, ('concurrent-a', 'concurrent-b')))
    assert sorted(response.status_code for response in responses) == [200, 409]
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM stock_movements WHERE goods_receipt_id=%s',
            (concurrent['id'],),
        )
        assert cursor.fetchone()['count'] == 1


def test_rejected_only_currency_scope_lifecycle_and_disclosure_are_stock_safe(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    supplier = _supplier(client, headers, scope)
    item = _item(
        client, headers, scope.location_id, 'REJECTED-ONLY',
        uom='UNIT', cost='3.000000',
    )
    offering = _offering(client, headers, supplier, scope, item, uom='UNIT')

    currency_mismatch = client.post('/inventory/goods-receipts', headers=headers, json={
        'supplier_id': supplier['id'], 'location_id': scope.location_id,
        'warehouse_id': warehouse['id'],
        'lines': [_line(
            offering, received='1', accepted='1', rejected='0', currency='USD',
        )],
    })
    assert currency_mismatch.status_code == 422

    other = _scope(connection, f'{prefix}-warehouse-scope', PERMISSIONS)
    other_headers = _headers(client, other)
    other_warehouse = _warehouse(client, other_headers, other.location_id)
    wrong_warehouse = client.post('/inventory/goods-receipts', headers=headers, json={
        'supplier_id': supplier['id'], 'location_id': scope.location_id,
        'warehouse_id': other_warehouse['id'],
        'lines': [_line(offering, received='1', accepted='1', rejected='0')],
    })
    assert wrong_warehouse.status_code == 404

    rejected = _receipt(
        client, headers, supplier, scope, warehouse,
        [_line(offering, received='4', accepted='0', rejected='4', cost='7')],
        'REJECTED-ONLY',
    )
    accepted = client.post(
        f"/inventory/goods-receipts/{rejected['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'rejected-only'},
        json={'expected_version': 1},
    )
    assert accepted.status_code == 200, accepted.text
    rejected_line = accepted.json()['lines'][0]
    assert rejected_line['evidence_status'] == 'REJECTED_ONLY'
    assert rejected_line['normalized_quantity'] == '0.000000'
    assert rejected_line['extended_cost'] == '0E-12'
    assert rejected_line['stock_movement_id'] is None
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM stock_movements WHERE goods_receipt_id=%s',
            (rejected['id'],),
        )
        assert cursor.fetchone()['count'] == 0

    inactive_supplier_receipt = _receipt(
        client, headers, supplier, scope, warehouse,
        [_line(offering, received='1', accepted='1', rejected='0')],
        'INACTIVE-SUPPLIER',
    )
    inactive_item_receipt = _receipt(
        client, headers, supplier, scope, warehouse,
        [_line(offering, received='1', accepted='1', rejected='0')],
        'INACTIVE-ITEM',
    )
    disabled_item = client.patch(
        f"/inventory-items/{item['id']}", headers=headers,
        json={'expected_version': 1, 'status': 'INACTIVE'},
    )
    assert disabled_item.status_code == 200, disabled_item.text
    failed_item = client.post(
        f"/inventory/goods-receipts/{inactive_item_receipt['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'inactive-item'},
        json={'expected_version': 1},
    )
    assert failed_item.status_code == 422
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM stock_movements WHERE goods_receipt_id=%s',
            (inactive_item_receipt['id'],),
        )
        assert cursor.fetchone()['count'] == 0
    enabled_item = client.patch(
        f"/inventory-items/{item['id']}", headers=headers,
        json={'expected_version': 2, 'status': 'ACTIVE'},
    )
    assert enabled_item.status_code == 200, enabled_item.text

    disabled = client.patch(
        f"/inventory/suppliers/{supplier['id']}", headers=headers,
        json={'expected_version': 1, 'status': 'INACTIVE'},
    )
    assert disabled.status_code == 200, disabled.text
    failed = client.post(
        f"/inventory/goods-receipts/{inactive_supplier_receipt['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'inactive-supplier'},
        json={'expected_version': 1},
    )
    assert failed.status_code == 422
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT status FROM goods_receipts WHERE id=%s',
            (inactive_supplier_receipt['id'],),
        )
        assert cursor.fetchone()['status'] == 'DRAFT'
        cursor.execute(
            'SELECT COUNT(*) AS count FROM stock_movements WHERE goods_receipt_id=%s',
            (inactive_supplier_receipt['id'],),
        )
        assert cursor.fetchone()['count'] == 0

    no_permissions = _scope(connection, f'{prefix}-no-permissions')
    no_permission_headers = _headers(client, no_permissions)
    assert client.get(
        f"/inventory/goods-receipts/{inactive_supplier_receipt['id']}",
        headers=no_permission_headers,
    ).status_code == 403
    assert client.post(
        f"/inventory/goods-receipts/{inactive_supplier_receipt['id']}:accept",
        headers={**no_permission_headers, 'Idempotency-Key': 'not-authorized'},
        json={'expected_version': 1},
    ).status_code == 403
    read_without_cost = _scope(
        connection, f'{prefix}-read-without-cost', ('inventory.read',),
    )
    read_without_cost_headers = _headers(client, read_without_cost)
    assert client.get(
        f"/inventory/goods-receipts/{inactive_supplier_receipt['id']}",
        headers=read_without_cost_headers,
    ).status_code == 403
    assert client.get(
        f"/inventory/goods-receipts/{inactive_supplier_receipt['id']}",
        headers=other_headers,
    ).status_code == 404
