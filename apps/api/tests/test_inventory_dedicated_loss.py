from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import create_app
from test_inventory_recipe_stock_foundation import (
    PASSWORD, Scope, _execute, _headers, _item, _permission, _scope,
)
from test_inventory_supplier_direct_receiving import _conversion, _warehouse


PERMISSIONS = (
    'inventory.manage', 'inventory.read', 'inventory.cost.read',
    'inventory.loss.read', 'inventory.loss.manage', 'inventory.loss.approve',
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def _second_actor(connection, scope: Scope, slug: str, permissions=PERMISSIONS) -> Scope:
    email = f'{slug}@example.test'
    user_id = _execute(
        connection,
        'INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,%s,%s)',
        (email, hash_password(PASSWORD), 'Loss Approver', 'ACTIVE'),
    )
    membership_id = _execute(
        connection,
        'INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,%s)',
        (scope.tenant_id, user_id, 'ACTIVE'),
    )
    role_id = _execute(
        connection,
        'INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,%s)',
        (scope.tenant_id, f'LOSS_{slug}', 'Loss role', 'ACTIVE'),
    )
    _execute(
        connection,
        'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',
        (scope.tenant_id, membership_id, role_id),
    )
    _execute(
        connection,
        'INSERT INTO membership_location_grants '
        '(tenant_id,membership_id,location_id) VALUES (%s,%s,%s)',
        (scope.tenant_id, membership_id, scope.location_id),
    )
    for permission in permissions:
        _permission(connection, role_id, permission)
    return Scope(
        scope.tenant_id, scope.organization_id, scope.location_id,
        membership_id, role_id, email,
    )


def _policy(client, headers, warehouse_id, threshold='100.000000000000', currency='MXN'):
    response = client.put(
        f'/inventory/loss-policies/{warehouse_id}', headers=headers,
        json={
            'expected_version': 0, 'approval_value_threshold': threshold,
            'currency': currency, 'status': 'ACTIVE',
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _loss(
    client, headers, warehouse_id, item_id, *, category='WASTE', quantity='2.000000',
    uom='UNIT', reason='Observed material loss', occurred_at=None,
):
    payload = {
        'warehouse_id': warehouse_id, 'inventory_item_id': item_id,
        'category': category, 'source_quantity': quantity,
        'source_uom': uom, 'reason': reason,
    }
    if occurred_at is not None:
        payload['occurred_at'] = occurred_at
    response = client.post('/inventory/losses', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _post(client, headers, loss, key='post-loss'):
    return client.post(
        f"/inventory/losses/{loss['id']}:post",
        headers={**headers, 'Idempotency-Key': key},
        json={'expected_version': loss['version']},
    )


def _opening(client, headers, warehouse_id, item_id, quantity='10.000000'):
    response = client.post(
        '/inventory/stock-movements',
        headers={**headers, 'Idempotency-Key': f'opening-{item_id}'},
        json={
            'inventory_item_id': item_id, 'warehouse_id': warehouse_id,
            'movement_type': 'OPENING_BALANCE', 'quantity': quantity,
            'uom': 'UNIT', 'reversal_of_movement_id': None,
            'reason': None, 'reference': 'loss-test-opening',
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_loss_categories_draft_update_cancel_and_no_stock(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'LOSS-DRAFT', uom='UNIT')
    for category in (
        'WASTE', 'SPOILAGE', 'BREAKAGE', 'EXPIRY', 'PREPARATION_LOSS', 'OTHER',
    ):
        loss = _loss(
            client, headers, warehouse['id'], item['id'], category=category,
            reason='Required exceptional reason' if category == 'OTHER' else None,
        )
        assert loss['status'] == 'DRAFT'
        assert loss['normalized_quantity'] is None
        assert loss['stock_movement_id'] is None

    invalid = client.post('/inventory/losses', headers=headers, json={
        'warehouse_id': warehouse['id'], 'inventory_item_id': item['id'],
        'category': 'THEFT', 'source_quantity': '1', 'source_uom': 'UNIT',
    })
    assert invalid.status_code == 422
    other_without_reason = client.post('/inventory/losses', headers=headers, json={
        'warehouse_id': warehouse['id'], 'inventory_item_id': item['id'],
        'category': 'OTHER', 'source_quantity': '1', 'source_uom': 'UNIT',
    })
    assert other_without_reason.status_code == 422

    editable = _loss(client, headers, warehouse['id'], item['id'])
    updated = client.patch(
        f"/inventory/losses/{editable['id']}", headers=headers,
        json={
            'expected_version': 1, 'category': 'SPOILAGE',
            'source_quantity': '3.000000', 'reason': 'Deteriorated',
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()['version'] == 2
    cancelled = client.post(
        f"/inventory/losses/{editable['id']}:cancel", headers=headers,
        json={'expected_version': 2},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()['status'] == 'CANCELLED'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM stock_movements WHERE inventory_loss_id IS NOT NULL'
        )
        assert cursor.fetchone()['count'] == 0


def test_below_threshold_posts_uom_cost_once_and_freezes_evidence(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(
        client, headers, scope.location_id, 'LOSS-UOM', uom='UNIT', cost='4.000000',
    )
    first_conversion = _conversion(client, headers, item['id'], factor='5.000000000000')
    _policy(client, headers, warehouse['id'], threshold='100')
    _opening(client, headers, warehouse['id'], item['id'], '20')
    loss = _loss(
        client, headers, warehouse['id'], item['id'], category='BREAKAGE',
        quantity='2', uom='BOX', reason='Two packages broke',
    )
    response = _post(client, headers, loss, 'post-uom-loss')
    assert response.status_code == 200, response.text
    posted = response.json()
    assert posted['status'] == 'POSTED'
    assert posted['approval_required'] is False
    assert posted['approval_reason'] == 'BELOW_THRESHOLD'
    assert posted['conversion_revision_id'] == first_conversion['id']
    assert posted['conversion_factor'] == '5.000000000000'
    assert posted['normalized_quantity'] == '10.000000'
    assert posted['standard_unit_cost_evidence'] == '4.000000'
    assert posted['cost_currency_evidence'] == 'MXN'
    assert posted['extended_loss_cost'] == '40.000000000000'
    assert posted['stock_movement_id'] is not None

    movements = client.get(
        '/inventory/stock-movements', headers=headers,
        params={'location_id': scope.location_id, 'inventory_item_id': item['id']},
    ).json()['items']
    movement = next(row for row in movements if row['id'] == posted['stock_movement_id'])
    assert movement['movement_type'] == 'WASTE'
    assert movement['quantity'] == '-10.000000'
    assert movement['warehouse_id'] == warehouse['id']
    assert movement['inventory_loss_id'] == loss['id']
    assert movement['loss_movement_role'] == 'ORIGINAL'

    replay = _post(client, headers, loss, 'post-uom-loss')
    assert replay.status_code == 200
    assert replay.headers['Idempotent-Replay'] == 'true'
    assert replay.json() == posted
    _conversion(client, headers, item['id'], factor='7.000000000000')
    frozen = client.get(
        f"/inventory/losses/{loss['id']}", headers=headers,
    ).json()
    assert frozen['conversion_revision_id'] == first_conversion['id']
    assert frozen['normalized_quantity'] == '10.000000'
    assert frozen['extended_loss_cost'] == '40.000000000000'


def test_threshold_unknown_cost_currency_and_second_approver(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    requester_headers = _headers(client, scope)
    approver = _second_actor(connection, scope, f'{prefix}-approver')
    approver_headers = _headers(client, approver)
    warehouse = _warehouse(client, requester_headers, scope.location_id)
    item = _item(
        client, requester_headers, scope.location_id, 'LOSS-APPROVAL',
        uom='UNIT', cost='5.000000',
    )
    _opening(client, requester_headers, warehouse['id'], item['id'], '20')

    no_policy = _loss(
        client, requester_headers, warehouse['id'], item['id'], quantity='1',
    )
    no_policy_pending = _post(
        client, requester_headers, no_policy, 'no-policy',
    ).json()
    assert no_policy_pending['status'] == 'PENDING_APPROVAL'
    assert no_policy_pending['approval_reason'] == 'NO_POLICY'
    assert client.post(
        f"/inventory/losses/{no_policy['id']}:cancel", headers=requester_headers,
        json={'expected_version': 2},
    ).status_code == 200

    _policy(client, requester_headers, warehouse['id'], threshold='10')
    loss = _loss(
        client, requester_headers, warehouse['id'], item['id'], quantity='3',
    )
    pending_response = _post(client, requester_headers, loss, 'threshold-post')
    assert pending_response.status_code == 200, pending_response.text
    pending = pending_response.json()
    assert pending['status'] == 'PENDING_APPROVAL'
    assert pending['approval_reason'] == 'VALUE_THRESHOLD'
    assert pending['stock_movement_id'] is None
    self_approval = client.post(
        f"/inventory/losses/{loss['id']}:approve",
        headers={**requester_headers, 'Idempotency-Key': 'self-approval'},
        json={'expected_version': 2},
    )
    assert self_approval.status_code == 422

    approved_response = client.post(
        f"/inventory/losses/{loss['id']}:approve",
        headers={**approver_headers, 'Idempotency-Key': 'second-approval'},
        json={'expected_version': 2},
    )
    assert approved_response.status_code == 200, approved_response.text
    approved = approved_response.json()
    assert approved['status'] == 'POSTED'
    assert approved['approved_by_actor_id'] == approver.membership_id
    replay = client.post(
        f"/inventory/losses/{loss['id']}:approve",
        headers={**approver_headers, 'Idempotency-Key': 'second-approval'},
        json={'expected_version': 2},
    )
    assert replay.status_code == 200
    assert replay.headers['Idempotent-Replay'] == 'true'

    conflicting = _loss(
        client, requester_headers, warehouse['id'], item['id'], quantity='1',
    )
    assert _post(
        client, requester_headers, conflicting, 'threshold-post',
    ).status_code == 409

    concurrent = _loss(
        client, requester_headers, warehouse['id'], item['id'], quantity='3',
    )
    concurrent_pending = _post(
        client, requester_headers, concurrent, 'concurrent-submit',
    ).json()

    def approve(key):
        return client.post(
            f"/inventory/losses/{concurrent['id']}:approve",
            headers={**approver_headers, 'Idempotency-Key': key},
            json={'expected_version': concurrent_pending['version']},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        approvals = list(executor.map(approve, ('approval-a', 'approval-b')))
    assert sorted(response.status_code for response in approvals) == [200, 409]
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM stock_movements '
            "WHERE inventory_loss_id=%s AND movement_type='WASTE'",
            (concurrent['id'],),
        )
        assert cursor.fetchone()['count'] == 1

    manager_only = _second_actor(
        connection, scope, f'{prefix}-manager-only',
        ('inventory.loss.manage', 'inventory.loss.read'),
    )
    manager_only_headers = _headers(client, manager_only)
    unauthorized = _loss(
        client, requester_headers, warehouse['id'], item['id'], quantity='3',
    )
    unauthorized_pending = _post(
        client, requester_headers, unauthorized, 'unauthorized-submit',
    ).json()
    assert client.post(
        f"/inventory/losses/{unauthorized['id']}:approve",
        headers={**manager_only_headers, 'Idempotency-Key': 'not-approver'},
        json={'expected_version': unauthorized_pending['version']},
    ).status_code == 403

    unknown = _loss(
        client, requester_headers, warehouse['id'], item['id'], quantity='1',
        occurred_at=datetime(2000, 1, 1, tzinfo=UTC).isoformat(),
    )
    unknown_pending = _post(client, requester_headers, unknown, 'unknown-cost').json()
    assert unknown_pending['status'] == 'PENDING_APPROVAL'
    assert unknown_pending['evidence_status'] == 'COST_NON_DERIVABLE'
    assert unknown_pending['approval_reason'] == 'COST_NON_DERIVABLE'

    policy = client.put(
        f"/inventory/loss-policies/{warehouse['id']}", headers=requester_headers,
        json={
            'expected_version': 1, 'approval_value_threshold': '999',
            'currency': 'USD', 'status': 'ACTIVE',
        },
    )
    assert policy.status_code == 200, policy.text
    mismatch = _loss(
        client, requester_headers, warehouse['id'], item['id'], quantity='1',
    )
    mismatch_pending = _post(client, requester_headers, mismatch, 'currency-mismatch').json()
    assert mismatch_pending['status'] == 'PENDING_APPROVAL'
    assert mismatch_pending['approval_reason'] == 'CURRENCY_MISMATCH'


def test_negative_policies_block_race_and_atomicity(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    _policy(client, headers, warehouse['id'], threshold='1000')

    allow_item = _item(client, headers, scope.location_id, 'LOSS-ALLOW', uom='UNIT')
    allow_loss = _loss(client, headers, warehouse['id'], allow_item['id'], quantity='1')
    allowed = _post(client, headers, allow_loss, 'allow-loss')
    assert allowed.status_code == 200
    allowed_movement = client.get(
        '/inventory/stock-movements', headers=headers,
        params={'location_id': scope.location_id, 'inventory_item_id': allow_item['id']},
    ).json()['items'][0]
    assert allowed_movement['negative_stock_policy'] == 'ALLOW'
    assert allowed_movement['negative_stock_warning'] is False

    policy_update = client.patch(
        f"/inventory/warehouses/{warehouse['id']}", headers=headers,
        json={'expected_version': warehouse['version'], 'negative_stock_policy': 'WARN'},
    )
    assert policy_update.status_code == 200, policy_update.text
    warn_item = _item(client, headers, scope.location_id, 'LOSS-WARN', uom='UNIT')
    warned = _post(
        client, headers,
        _loss(client, headers, warehouse['id'], warn_item['id'], quantity='1'),
        'warn-loss',
    )
    assert warned.status_code == 200
    warning_movement = client.get(
        '/inventory/stock-movements', headers=headers,
        params={'location_id': scope.location_id, 'inventory_item_id': warn_item['id']},
    ).json()['items'][0]
    assert warning_movement['negative_stock_policy'] == 'WARN'
    assert warning_movement['negative_stock_warning'] is True

    blocked_policy = client.patch(
        f"/inventory/warehouses/{warehouse['id']}", headers=headers,
        json={
            'expected_version': policy_update.json()['version'],
            'negative_stock_policy': 'BLOCK',
        },
    )
    assert blocked_policy.status_code == 200, blocked_policy.text
    blocked_item = _item(client, headers, scope.location_id, 'LOSS-BLOCK', uom='UNIT')
    blocked_loss = _loss(client, headers, warehouse['id'], blocked_item['id'])
    blocked = _post(client, headers, blocked_loss, 'blocked-loss')
    assert blocked.status_code == 409
    assert client.get(
        f"/inventory/losses/{blocked_loss['id']}", headers=headers,
    ).json()['status'] == 'DRAFT'

    race_item = _item(client, headers, scope.location_id, 'LOSS-RACE', uom='UNIT')
    _opening(client, headers, warehouse['id'], race_item['id'], '1')
    losses = [
        _loss(client, headers, warehouse['id'], race_item['id'], quantity='1')
        for _ in range(2)
    ]

    def post_one(index):
        return _post(client, headers, losses[index], f'race-loss-{index}')

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(post_one, (0, 1)))
    assert sorted(response.status_code for response in responses) == [200, 409]
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS count FROM stock_movements '
            "WHERE inventory_loss_id IN (%s,%s) AND movement_type='WASTE'",
            (losses[0]['id'], losses[1]['id']),
        )
        assert cursor.fetchone()['count'] == 1


def test_reversal_is_once_opposite_and_preserves_original_evidence(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'LOSS-REVERSE', uom='UNIT', cost='3')
    _policy(client, headers, warehouse['id'], threshold='100')
    _opening(client, headers, warehouse['id'], item['id'], '10')
    loss = _loss(client, headers, warehouse['id'], item['id'], quantity='4')
    posted = _post(client, headers, loss, 'reverse-source').json()
    response = client.post(
        f"/inventory/losses/{loss['id']}:reverse",
        headers={**headers, 'Idempotency-Key': 'reverse-loss'},
        json={'expected_version': 2, 'reason': 'Correct duplicate observation'},
    )
    assert response.status_code == 200, response.text
    reversed_loss = response.json()
    assert reversed_loss['status'] == 'REVERSED'
    assert reversed_loss['reversal_stock_movement_id'] is not None
    movements = client.get(
        '/inventory/stock-movements', headers=headers,
        params={'location_id': scope.location_id, 'inventory_item_id': item['id']},
    ).json()['items']
    original = next(row for row in movements if row['id'] == posted['stock_movement_id'])
    reversal = next(
        row for row in movements if row['id'] == reversed_loss['reversal_stock_movement_id']
    )
    assert reversal['movement_type'] == 'REVERSAL'
    assert reversal['reversal_of_movement_id'] == original['id']
    assert reversal['warehouse_id'] == original['warehouse_id']
    assert reversal['quantity'] == '4.000000'
    assert reversal['source_quantity'] == '4.000000'
    assert reversal['conversion_factor'] == original['conversion_factor']
    assert reversal['standard_unit_cost_evidence'] == original['standard_unit_cost_evidence']
    assert reversal['extended_standard_cost'] == '12.000000000000'
    replay = client.post(
        f"/inventory/losses/{loss['id']}:reverse",
        headers={**headers, 'Idempotency-Key': 'reverse-loss'},
        json={'expected_version': 2, 'reason': 'Correct duplicate observation'},
    )
    assert replay.status_code == 200
    assert replay.headers['Idempotent-Replay'] == 'true'
    conflict = client.post(
        f"/inventory/losses/{loss['id']}:reverse",
        headers={**headers, 'Idempotency-Key': 'another-reversal'},
        json={'expected_version': 3, 'reason': 'Try twice'},
    )
    assert conflict.status_code == 409


def test_inactive_scope_permissions_cost_mask_and_legacy_manual_out(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, PERMISSIONS)
    headers = _headers(client, scope)
    warehouse = _warehouse(client, headers, scope.location_id)
    item = _item(client, headers, scope.location_id, 'LOSS-SCOPE', uom='UNIT', cost='2')
    _policy(client, headers, warehouse['id'], threshold='100')
    _opening(client, headers, warehouse['id'], item['id'], '10')
    loss = _loss(client, headers, warehouse['id'], item['id'], quantity='1')

    inactive = client.patch(
        f"/inventory-items/{item['id']}", headers=headers,
        json={'expected_version': 1, 'status': 'INACTIVE'},
    )
    assert inactive.status_code == 200
    assert _post(client, headers, loss, 'inactive-item').status_code == 422
    assert client.patch(
        f"/inventory-items/{item['id']}", headers=headers,
        json={'expected_version': 2, 'status': 'ACTIVE'},
    ).status_code == 200
    with connection.cursor() as cursor:
        cursor.execute('UPDATE warehouses SET status=\'INACTIVE\' WHERE id=%s', (warehouse['id'],))
    assert _post(client, headers, loss, 'inactive-warehouse').status_code == 422
    with connection.cursor() as cursor:
        cursor.execute('UPDATE warehouses SET status=\'ACTIVE\' WHERE id=%s', (warehouse['id'],))

    other = _scope(connection, f'{prefix}-other', PERMISSIONS)
    other_headers = _headers(client, other)
    assert client.get(
        f"/inventory/losses/{loss['id']}", headers=other_headers,
    ).status_code == 404
    assert client.post('/inventory/losses', headers=headers, json={
        'warehouse_id': _warehouse(client, other_headers, other.location_id)['id'],
        'inventory_item_id': item['id'], 'category': 'WASTE',
        'source_quantity': '1', 'source_uom': 'UNIT',
    }).status_code == 404

    no_permission = _scope(connection, f'{prefix}-no-permission')
    no_permission_headers = _headers(client, no_permission)
    assert client.get(
        f"/inventory/losses/{loss['id']}", headers=no_permission_headers,
    ).status_code == 403
    reader = _second_actor(
        connection, scope, f'{prefix}-reader', ('inventory.loss.read',),
    )
    masked = client.get(
        f"/inventory/losses/{loss['id']}", headers=_headers(client, reader),
    )
    assert masked.status_code == 200
    assert masked.json()['cost_visible'] is False
    assert masked.json()['standard_unit_cost_evidence'] is None

    manual = client.post(
        '/inventory/stock-movements',
        headers={**headers, 'Idempotency-Key': 'legacy-manual-out'},
        json={
            'inventory_item_id': item['id'], 'warehouse_id': warehouse['id'],
            'movement_type': 'MANUAL_OUT', 'quantity': '-1', 'uom': 'UNIT',
            'reversal_of_movement_id': None, 'reason': 'Legacy operational issue',
            'reference': 'legacy-compatible',
        },
    )
    assert manual.status_code == 201, manual.text
    assert manual.json()['movement_type'] == 'MANUAL_OUT'
    assert manual.json()['inventory_loss_id'] is None
