from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_canonical_order_commercial_acceptance import (
    Scope as OrderScope, _confirm, _open_and_join, _preview, _product,
)
from test_inventory_dedicated_loss import _loss, _opening, _policy, _post, _second_actor
from test_inventory_recipe_stock_foundation import _headers, _item, _scope
from test_restaurant_order_inventory_consumption import _recipe
from test_inventory_supplier_direct_receiving import (
    _conversion, _line, _offering, _receipt, _supplier, _warehouse,
)


PERMISSIONS = (
    'inventory.manage', 'inventory.read', 'inventory.cost.read',
    'inventory.supplier.manage', 'inventory.receipt.manage', 'inventory.receipt.accept',
    'inventory.loss.read', 'inventory.loss.manage', 'inventory.loss.approve',
    'inventory.count.read', 'inventory.count.manage', 'inventory.count.approve',
    'inventory.count.post', 'inventory.reconciliation.read',
    'inventory.reconciliation.manage',
    'restaurant_service.read', 'restaurant_service.manage',
    'order_draft.read', 'order_draft.manage', 'conversation.read',
    'conversation.manage', 'restaurant_order.read',
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _count(client, headers, warehouse_id, reference='COUNT-1', count_scope='PARTIAL'):
    response = client.post('/inventory/physical-counts', headers=headers, json={
        'warehouse_id': warehouse_id, 'reason': 'Scheduled physical observation',
        'reference': reference, 'count_scope': count_scope,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _put_line(client, headers, count, item_id, quantity, uom='UNIT', line_version=0):
    response = client.put(
        f"/inventory/physical-counts/{count['id']}/lines/{item_id}", headers=headers,
        json={
            'expected_count_version': count['version'],
            'expected_line_version': line_version,
            'source_quantity': quantity, 'source_uom': uom,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _submit_approve(client, counter_headers, approver_headers, count):
    submitted = client.post(
        f"/inventory/physical-counts/{count['id']}:submit", headers=counter_headers,
        json={'expected_version': count['version']},
    )
    assert submitted.status_code == 200, submitted.text
    approved = client.post(
        f"/inventory/physical-counts/{count['id']}:approve", headers=approver_headers,
        json={'expected_version': submitted.json()['version']},
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


def _post_count(client, headers, count, key='post-count'):
    return client.post(
        f"/inventory/physical-counts/{count['id']}:post",
        headers={**headers, 'Idempotency-Key': key},
        json={'expected_version': count['version']},
    )


def _movement(client, headers, warehouse_id, item_id, kind, quantity, key, uom='UNIT'):
    response = client.post(
        '/inventory/stock-movements', headers={**headers, 'Idempotency-Key': key},
        json={
            'inventory_item_id': item_id, 'warehouse_id': warehouse_id,
            'movement_type': kind, 'quantity': quantity, 'uom': uom,
            'reversal_of_movement_id': None, 'reason': 'Count test movement',
            'reference': key,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_count_lifecycle_partial_zero_cancel_and_immutability(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS))
    warehouse = _warehouse(client, headers, scope.location_id)
    counted = _item(client, headers, scope.location_id, 'COUNT-ZERO', uom='UNIT', cost='3')
    omitted = _item(client, headers, scope.location_id, 'COUNT-OMITTED', uom='UNIT', cost='2')
    _opening(client, headers, warehouse['id'], counted['id'], '5')
    _opening(client, headers, warehouse['id'], omitted['id'], '7')
    count = _count(client, headers, warehouse['id'])
    count = _put_line(client, headers, count, counted['id'], '0')
    line = count['lines'][0]
    assert count['status'] == 'COUNTING'
    assert line['expected_quantity_at_cursor'] == '5.000000'
    assert line['normalized_counted_quantity'] == '0.000000'
    assert line['variance_quantity'] == '-5.000000'
    assert client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
        'inventory_item_id': counted['id'],
    }).json()['items'][0]['quantity'] == '5.000000'
    submitted_response = client.post(
        f"/inventory/physical-counts/{count['id']}:submit", headers=headers,
        json={'expected_version': count['version']},
    )
    assert submitted_response.status_code == 200
    assert client.post(
        f"/inventory/physical-counts/{count['id']}:approve", headers=headers,
        json={'expected_version': submitted_response.json()['version']},
    ).status_code == 422
    approved_response = client.post(
        f"/inventory/physical-counts/{count['id']}:approve", headers=approver_headers,
        json={'expected_version': submitted_response.json()['version']},
    )
    assert approved_response.status_code == 200
    approved = approved_response.json()
    posted = _post_count(client, approver_headers, approved).json()
    assert posted['status'] == 'POSTED'
    assert posted['lines'][0]['adjustment_stock_movement_id'] is not None
    assert client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
        'inventory_item_id': omitted['id'],
    }).json()['items'][0]['quantity'] == '7.000000'
    assert client.put(
        f"/inventory/physical-counts/{count['id']}/lines/{counted['id']}", headers=headers,
        json={'expected_count_version': posted['version'], 'expected_line_version': 1,
              'source_quantity': '1', 'source_uom': 'UNIT'},
    ).status_code == 409

    cancellable = _count(client, headers, warehouse['id'], 'CANCEL')
    cancelled = client.post(
        f"/inventory/physical-counts/{cancellable['id']}:cancel", headers=headers,
        json={'expected_version': 1},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()['status'] == 'CANCELLED'


def test_full_count_requires_every_active_location_item_without_treating_omission_as_zero(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(
        client, _second_actor(connection, scope, f'{prefix}-full-approver', PERMISSIONS),
    )
    warehouse = _warehouse(client, headers, scope.location_id)
    counted = _item(client, headers, scope.location_id, 'FULL-COUNTED', uom='UNIT', cost='3')
    omitted = _item(client, headers, scope.location_id, 'FULL-OMITTED', uom='UNIT', cost='2')
    _opening(client, headers, warehouse['id'], counted['id'], '10')
    _opening(client, headers, warehouse['id'], omitted['id'], '7')

    other = _scope(connection, f'{prefix}-other-scope', PERMISSIONS)
    other_headers = _headers(client, other)
    other_item = _item(client, other_headers, other.location_id, 'OTHER-ACTIVE', uom='UNIT', cost='9')

    count = _count(client, headers, warehouse['id'], 'FULL-INCOMPLETE', 'FULL')
    assert count['count_scope'] == 'FULL'
    count = _put_line(client, headers, count, counted['id'], '9')
    assert client.put(
        f"/inventory/physical-counts/{count['id']}/lines/{other_item['id']}",
        headers=headers,
        json={
            'expected_count_version': count['version'], 'expected_line_version': 0,
            'source_quantity': '0', 'source_uom': 'UNIT',
        },
    ).status_code == 404
    approved = _submit_approve(client, headers, approver_headers, count)
    failed = _post_count(client, approver_headers, approved, 'full-incomplete')
    assert failed.status_code == 422
    assert failed.json()['error']['code'] == 'INVALID_PHYSICAL_COUNT'
    assert '1 active item(s) are not counted' in failed.json()['error']['message']
    current = client.get(
        f"/inventory/physical-counts/{count['id']}", headers=headers,
    ).json()
    assert current['status'] == 'APPROVED'
    assert {line['inventory_item_id'] for line in current['lines']} == {counted['id']}
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS movements FROM stock_movements WHERE physical_count_id=%s',
            (count['id'],),
        )
        assert cursor.fetchone()['movements'] == 0
    assert client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
        'inventory_item_id': omitted['id'],
    }).json()['items'][0]['quantity'] == '7.000000'


def test_complete_full_count_explicit_zero_no_freeze_and_exactly_once_post(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(
        client, _second_actor(connection, scope, f'{prefix}-complete-approver', PERMISSIONS),
    )
    warehouse = _warehouse(client, headers, scope.location_id)
    later_receipt_item = _item(client, headers, scope.location_id, 'FULL-LATER', uom='UNIT', cost='4')
    zero_item = _item(client, headers, scope.location_id, 'FULL-ZERO', uom='UNIT', cost='5')
    _opening(client, headers, warehouse['id'], later_receipt_item['id'], '100')
    _opening(client, headers, warehouse['id'], zero_item['id'], '5')

    count = _count(client, headers, warehouse['id'], 'FULL-COMPLETE', 'FULL')
    count = _put_line(client, headers, count, later_receipt_item['id'], '95')
    count = _put_line(client, headers, count, zero_item['id'], '0')
    zero_line = next(
        line for line in count['lines'] if line['inventory_item_id'] == zero_item['id']
    )
    assert zero_line['normalized_counted_quantity'] == '0.000000'
    assert zero_line['variance_quantity'] == '-5.000000'
    _movement(
        client, headers, warehouse['id'], later_receipt_item['id'],
        'MANUAL_IN', '20', 'full-later-receipt',
    )

    approved = _submit_approve(client, headers, approver_headers, count)
    posted_response = _post_count(client, approver_headers, approved, 'full-complete-post')
    assert posted_response.status_code == 200, posted_response.text
    posted = posted_response.json()
    assert posted['status'] == 'POSTED'
    assert all(line['adjustment_stock_movement_id'] for line in posted['lines'])
    assert client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
        'inventory_item_id': later_receipt_item['id'],
    }).json()['items'][0]['quantity'] == '115.000000'
    assert client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
        'inventory_item_id': zero_item['id'],
    }).json()['items'][0]['quantity'] == '0.000000'

    replay = _post_count(client, approver_headers, approved, 'full-complete-post')
    assert replay.status_code == 200
    assert replay.headers['Idempotent-Replay'] == 'true'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT quantity FROM stock_movements WHERE physical_count_id=%s ORDER BY id',
            (count['id'],),
        )
        assert [row['quantity'] for row in cursor.fetchall()] == [
            Decimal('-5.000000'), Decimal('-5.000000'),
        ]


def test_no_freeze_later_movements_and_exactly_once_post(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS))
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'COUNT-CURSOR', uom='UNIT', cost='4')
    _opening(client, headers, warehouse['id'], item['id'], '100')
    count = _put_line(client, headers, _count(client, headers, warehouse['id']), item['id'], '95')
    _movement(client, headers, warehouse['id'], item['id'], 'MANUAL_IN', '20', 'later-in')
    _movement(client, headers, warehouse['id'], item['id'], 'MANUAL_OUT', '-10', 'later-out')
    approved = _submit_approve(client, headers, approver_headers, count)
    response = _post_count(client, approver_headers, approved, 'cursor-post')
    assert response.status_code == 200, response.text
    posted = response.json()
    assert posted['lines'][0]['expected_quantity_at_cursor'] == '100.000000'
    assert posted['lines'][0]['variance_quantity'] == '-5.000000'
    stock = client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
        'inventory_item_id': item['id'],
    }).json()['items'][0]['quantity']
    assert stock == '105.000000'
    replay = _post_count(client, approver_headers, approved, 'cursor-post')
    assert replay.status_code == 200
    assert replay.headers['Idempotent-Replay'] == 'true'
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) count FROM stock_movements WHERE physical_count_line_id=%s',
                       (posted['lines'][0]['id'],))
        assert cursor.fetchone()['count'] == 1


def test_no_freeze_preserves_later_receipt_and_dedicated_loss(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(
        client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS)
    )
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'COUNT-LATER-AUTHORITY', uom='UNIT', cost='2')
    _opening(client, headers, warehouse['id'], item['id'], '100')
    count = _put_line(
        client, headers, _count(client, headers, warehouse['id']), item['id'], '95'
    )

    supplier = _supplier(client, headers, scope, 'COUNT-LATER-SUPPLIER')
    offering = _offering(client, headers, supplier, scope, item, uom='UNIT')
    receipt = _receipt(client, headers, supplier, scope, warehouse, [
        _line(offering, received='20', accepted='20', rejected='0', cost='2'),
    ])
    accepted = client.post(
        f"/inventory/goods-receipts/{receipt['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'count-later-receipt'},
        json={'expected_version': 1},
    )
    assert accepted.status_code == 200, accepted.text

    _policy(client, headers, warehouse['id'], threshold='1000')
    loss = _loss(client, headers, warehouse['id'], item['id'], quantity='5')
    loss_posted = _post(client, headers, loss, 'count-later-loss')
    assert loss_posted.status_code == 200, loss_posted.text

    posted_response = _post_count(
        client, approver_headers,
        _submit_approve(client, headers, approver_headers, count),
        'count-later-authorities',
    )
    assert posted_response.status_code == 200, posted_response.text
    posted = posted_response.json()
    assert posted['lines'][0]['expected_quantity_at_cursor'] == '100.000000'
    assert posted['lines'][0]['variance_quantity'] == '-5.000000'
    assert client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
        'inventory_item_id': item['id'],
    }).json()['items'][0]['quantity'] == '110.000000'


def test_movement_concurrent_with_post_is_preserved(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(
        client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS)
    )
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'COUNT-POST-RACE', uom='UNIT')
    _opening(client, headers, warehouse['id'], item['id'], '100')
    count = _put_line(
        client, headers, _count(client, headers, warehouse['id']), item['id'], '95'
    )
    approved = _submit_approve(client, headers, approver_headers, count)

    with ThreadPoolExecutor(max_workers=2) as executor:
        post_future = executor.submit(
            _post_count, client, approver_headers, approved, 'count-post-race'
        )
        movement_future = executor.submit(
            _movement, client, headers, warehouse['id'], item['id'], 'MANUAL_IN',
            '20', 'movement-post-race',
        )
        posted_response = post_future.result()
        movement = movement_future.result()

    assert posted_response.status_code == 200, posted_response.text
    assert movement['quantity'] == '20.000000'
    assert client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
        'inventory_item_id': item['id'],
    }).json()['items'][0]['quantity'] == '115.000000'


def test_zero_variance_and_concurrent_post(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS))
    warehouse = _warehouse(client, headers, scope.location_id)
    zero_item = _item(client, headers, scope.location_id, 'COUNT-EQUAL', uom='UNIT')
    changed_item = _item(client, headers, scope.location_id, 'COUNT-CONCURRENT', uom='UNIT')
    _opening(client, headers, warehouse['id'], zero_item['id'], '2')
    _opening(client, headers, warehouse['id'], changed_item['id'], '3')
    count = _count(client, headers, warehouse['id'])
    count = _put_line(client, headers, count, zero_item['id'], '2')
    count = _put_line(client, headers, count, changed_item['id'], '4')
    approved = _submit_approve(client, headers, approver_headers, count)

    def post(key):
        return _post_count(client, approver_headers, approved, key)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(post, ('count-a', 'count-b')))
    assert sorted(response.status_code for response in responses) == [200, 409]
    posted = next(response.json() for response in responses if response.status_code == 200)
    by_item = {line['inventory_item_id']: line for line in posted['lines']}
    assert by_item[zero_item['id']]['adjustment_stock_movement_id'] is None
    assert by_item[changed_item['id']]['adjustment_stock_movement_id'] is not None


def test_operational_uom_and_cost_evidence_are_frozen(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS))
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'COUNT-UOM', uom='UNIT', cost='3')
    first = _conversion(client, headers, item['id'], factor='5.000000000000')
    _opening(client, headers, warehouse['id'], item['id'], '10')
    count = _put_line(
        client, headers, _count(client, headers, warehouse['id']),
        item['id'], '2', uom='BOX',
    )
    line = count['lines'][0]
    assert line['conversion_revision_id'] == first['id']
    assert line['conversion_factor'] == '5.000000000000'
    assert line['normalized_counted_quantity'] == '10.000000'
    assert line['standard_unit_cost_evidence'] == '3.000000'
    _conversion(client, headers, item['id'], factor='7.000000000000')
    posted = _post_count(
        client, approver_headers, _submit_approve(client, headers, approver_headers, count),
        'uom-count',
    ).json()
    assert posted['lines'][0]['conversion_revision_id'] == first['id']
    assert posted['lines'][0]['conversion_factor'] == '5.000000000000'
    assert posted['lines'][0]['adjustment_stock_movement_id'] is None


def test_reconciliation_classifies_receipt_and_loss_without_double_counting(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS))
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'COUNT-RECON', uom='UNIT', cost='2')
    _opening(client, headers, warehouse['id'], item['id'], '100')
    supplier = _supplier(client, headers, scope, 'COUNT-SUPPLIER')
    offering = _offering(client, headers, supplier, scope, item, uom='UNIT')
    receipt = _receipt(client, headers, supplier, scope, warehouse, [
        _line(offering, received='20', accepted='20', rejected='0', cost='2'),
    ])
    accepted = client.post(
        f"/inventory/goods-receipts/{receipt['id']}:accept",
        headers={**headers, 'Idempotency-Key': 'count-receipt'},
        json={'expected_version': 1},
    )
    assert accepted.status_code == 200, accepted.text
    _policy(client, headers, warehouse['id'], threshold='1000')
    loss = _loss(client, headers, warehouse['id'], item['id'], quantity='5')
    assert _post(client, headers, loss, 'count-loss').json()['status'] == 'POSTED'
    _movement(client, headers, warehouse['id'], item['id'], 'ADJUSTMENT', '2', 'other-adjustment')
    count = _put_line(client, headers, _count(client, headers, warehouse['id']), item['id'], '115')
    posted = _post_count(client, approver_headers,
                         _submit_approve(client, headers, approver_headers, count), 'recon-post').json()
    line = posted['lines'][0]
    opened = client.post('/inventory/reconciliations', headers=headers, json={
        'physical_count_line_id': line['id'],
        'period_start': datetime(2000, 1, 1, tzinfo=UTC).isoformat(),
    })
    assert opened.status_code == 201, opened.text
    closed = client.post(
        f"/inventory/reconciliations/{opened.json()['id']}:close", headers=headers,
        json={'expected_version': 1},
    )
    assert closed.status_code == 200, closed.text
    value = closed.json()
    assert value['status'] == 'CLOSED'
    assert value['receiving_quantity'] == '20.000000'
    assert value['theoretical_consumption_quantity'] == '0.000000'
    assert value['dedicated_loss_quantity'] == '5.000000'
    assert value['other_adjustment_quantity'] == '102.000000'
    assert value['theoretical_closing_quantity'] == '117.000000'
    assert value['physical_count_quantity'] == '115.000000'
    assert value['variance_quantity'] == '-2.000000'
    assert value['count_adjustment_quantity'] == '-2.000000'
    assert value['closing_quantity'] == '115.000000'
    assert value['variance_value'] == '-4.000000000000'
    _movement(client, headers, warehouse['id'], item['id'], 'MANUAL_IN', '9', 'after-close')
    assert client.get(
        f"/inventory/reconciliations/{value['id']}", headers=headers,
    ).json() == value


def test_negative_block_atomicity_permissions_isolation_and_cost_mask(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS))
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'COUNT-BLOCK', uom='UNIT', cost='3')
    positive_item = _item(client, headers, scope.location_id, 'COUNT-ATOMIC', uom='UNIT', cost='3')
    _opening(client, headers, warehouse['id'], item['id'], '10')
    _opening(client, headers, warehouse['id'], positive_item['id'], '2')
    count = _put_line(client, headers, _count(client, headers, warehouse['id']), positive_item['id'], '3')
    count = _put_line(client, headers, count, item['id'], '0')
    _movement(client, headers, warehouse['id'], item['id'], 'MANUAL_OUT', '-5', 'after-cursor-out')
    updated = client.patch(
        f"/inventory/warehouses/{warehouse['id']}", headers=headers,
        json={'expected_version': warehouse['version'], 'negative_stock_policy': 'BLOCK'},
    )
    assert updated.status_code == 200
    approved = _submit_approve(client, headers, approver_headers, count)
    manage_only = _second_actor(
        connection, scope, f'{prefix}-manage-only', ('inventory.count.manage',)
    )
    denied = _post_count(client, _headers(client, manage_only), approved, 'unauthorized-post')
    assert denied.status_code == 403
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) count FROM stock_movements WHERE physical_count_id=%s',
            (count['id'],),
        )
        assert cursor.fetchone()['count'] == 0
    blocked = _post_count(client, approver_headers, approved, 'blocked-count')
    assert blocked.status_code == 409
    assert client.get(f"/inventory/physical-counts/{count['id']}", headers=headers).json()['status'] == 'APPROVED'
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) count FROM stock_movements WHERE physical_count_id=%s', (count['id'],))
        assert cursor.fetchone()['count'] == 0

    other = _scope(connection, f'{prefix}-other', PERMISSIONS)
    other_headers = _headers(client, other)
    assert client.get(f"/inventory/physical-counts/{count['id']}", headers=other_headers).status_code == 404
    reader = _second_actor(connection, scope, f'{prefix}-reader', ('inventory.count.read',))
    masked = client.get(f"/inventory/physical-counts/{count['id']}", headers=_headers(client, reader))
    assert masked.status_code == 200
    assert masked.json()['lines'][0]['cost_visible'] is False
    assert masked.json()['lines'][0]['standard_unit_cost_evidence'] is None


def test_allow_and_warn_count_adjustments_preserve_policy_evidence(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS))
    warehouse = _warehouse(client, headers, scope.location_id)
    version = warehouse['version']
    for policy in ('ALLOW', 'WARN'):
        if policy == 'WARN':
            updated = client.patch(
                f"/inventory/warehouses/{warehouse['id']}", headers=headers,
                json={'expected_version': version, 'negative_stock_policy': policy},
            )
            assert updated.status_code == 200
            version = updated.json()['version']
        item = _item(client, headers, scope.location_id, f'COUNT-{policy}', uom='UNIT')
        _opening(client, headers, warehouse['id'], item['id'], '10')
        count = _put_line(client, headers, _count(client, headers, warehouse['id']), item['id'], '0')
        _movement(client, headers, warehouse['id'], item['id'], 'MANUAL_OUT', '-5', f'later-{policy}')
        posted = _post_count(
            client, approver_headers, _submit_approve(client, headers, approver_headers, count),
            f'post-{policy}',
        )
        assert posted.status_code == 200, posted.text
        movement_id = posted.json()['lines'][0]['adjustment_stock_movement_id']
        movements = client.get('/inventory/stock-movements', headers=headers, params={
            'location_id': scope.location_id, 'inventory_item_id': item['id'],
        }).json()['items']
        movement = next(row for row in movements if row['id'] == movement_id)
        assert movement['negative_stock_policy'] == policy
        assert movement['negative_stock_warning'] is (policy == 'WARN')
        assert movement['resulting_stock_quantity'] == '-5.000000'


def test_non_derivable_variance_value_is_explicit_and_frozen(client, sql_connection):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS))
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'COUNT-NO-COST', uom='UNIT')
    with connection.cursor() as cursor:
        cursor.execute('DELETE FROM inventory_cost_revisions WHERE inventory_item_id=%s', (item['id'],))
    count = _put_line(client, headers, _count(client, headers, warehouse['id']), item['id'], '1')
    assert count['lines'][0]['evidence_status'] == 'COST_NON_DERIVABLE'
    assert count['lines'][0]['variance_value'] is None
    posted = _post_count(
        client, approver_headers, _submit_approve(client, headers, approver_headers, count),
        'no-cost-count',
    ).json()
    opened = client.post('/inventory/reconciliations', headers=headers, json={
        'physical_count_line_id': posted['lines'][0]['id'],
        'period_start': datetime(2000, 1, 1, tzinfo=UTC).isoformat(),
    }).json()
    closed = client.post(
        f"/inventory/reconciliations/{opened['id']}:close", headers=headers,
        json={'expected_version': 1},
    ).json()
    assert closed['evidence_status'] == 'COST_NON_DERIVABLE'
    assert closed['standard_unit_cost_evidence'] is None
    assert closed['cost_currency_evidence'] is None
    assert closed['variance_value'] is None


def test_consumption_before_cursor_is_classified_and_later_consumption_is_preserved(
    client, sql_connection,
):
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    approver_headers = _headers(client, _second_actor(connection, scope, f'{prefix}-approver', PERMISSIONS))
    with connection.cursor() as cursor:
        cursor.execute("UPDATE locations SET country_code='MX' WHERE id=%s", (scope.location_id,))
        cursor.execute(
            "INSERT INTO resources (tenant_id,location_id,code,name,resource_type,status) "
            "VALUES (%s,%s,'COUNT-TABLE','Count Table','TABLE','ACTIVE')",
            (scope.tenant_id, scope.location_id),
        )
        resource_id = int(cursor.lastrowid)
    order_scope = OrderScope(
        scope.tenant_id, scope.organization_id, scope.location_id,
        resource_id, scope.email,
    )
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'COUNT-CONSUMPTION', uom='G', cost='2')
    _movement(client, headers, warehouse['id'], item['id'], 'OPENING_BALANCE', '100', 'consume-opening', uom='G')
    product_id = _product(connection, order_scope, name='Count Recipe', amount='100')
    _recipe(connection, order_scope, product_id, ((item['id'], '10.000000'),))
    _, diner_headers = _open_and_join(client, order_scope)
    first = _preview(client, diner_headers, product_id)
    first_confirmed = _confirm(client, diner_headers, first, 'before-count-consumption')
    assert first_confirmed.status_code == 201, first_confirmed.text
    count = _put_line(
        client, headers, _count(client, headers, warehouse['id']),
        item['id'], '88', uom='G',
    )
    assert count['lines'][0]['expected_quantity_at_cursor'] == '90.000000'
    second = _preview(client, diner_headers, product_id)
    second_confirmed = _confirm(client, diner_headers, second, 'after-count-consumption')
    assert second_confirmed.status_code == 201, second_confirmed.text
    posted = _post_count(
        client, approver_headers, _submit_approve(client, headers, approver_headers, count),
        'consumption-count',
    ).json()
    assert client.get('/inventory/stock', headers=headers, params={
        'location_id': scope.location_id, 'warehouse_id': warehouse['id'],
        'inventory_item_id': item['id'],
    }).json()['items'][0]['quantity'] == '78.000000'
    opened = client.post('/inventory/reconciliations', headers=headers, json={
        'physical_count_line_id': posted['lines'][0]['id'],
        'period_start': datetime(2000, 1, 1, tzinfo=UTC).isoformat(),
    }).json()
    closed = client.post(
        f"/inventory/reconciliations/{opened['id']}:close", headers=headers,
        json={'expected_version': 1},
    ).json()
    assert closed['theoretical_consumption_quantity'] == '10.000000'
    assert closed['theoretical_closing_quantity'] == '90.000000'
    assert closed['physical_count_quantity'] == '88.000000'
    assert closed['count_adjustment_quantity'] == '-2.000000'
