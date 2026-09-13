"""Guarded deterministic bootstrap for the local WS-DEMO-01 environment only."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
import os

import pymysql
from fastapi.testclient import TestClient


DEMO_DATABASE = 'pryecip_demo'
DEMO_EMAIL = 'manager@restaurant.demo'


def _guard() -> None:
    if os.environ.get('DEMO_ENV') != 'demo':
        raise SystemExit('REFUSED: DEMO_ENV must be exactly "demo"')
    if os.environ.get('MYSQL_DATABASE') != DEMO_DATABASE:
        raise SystemExit(f'REFUSED: demo bootstrap only targets {DEMO_DATABASE}')
    if os.environ.get('MYSQL_HOST') != 'mysql-demo':
        raise SystemExit('REFUSED: demo bootstrap only targets mysql-demo')
    if os.environ.get('APP_ENV') in {'production', 'staging'}:
        raise SystemExit('REFUSED: production/staging APP_ENV is never a demo target')


def _connection():
    return pymysql.connect(
        host=os.environ['MYSQL_HOST'], port=int(os.environ.get('MYSQL_PORT', '3306')),
        user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'],
        database=os.environ['MYSQL_DATABASE'], autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _api(client: TestClient, method: str, path: str, headers: dict[str, str], payload=None):
    response = client.request(method, path, headers=headers, json=payload)
    if response.status_code >= 300:
        raise RuntimeError(f'{method} {path}: {response.status_code} {response.text}')
    return response.json() if response.content else None


def _grant_every_permission(db, tenant_id: int) -> None:
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT r.id FROM roles r WHERE r.tenant_id=%s AND r.name='TENANT_ADMIN'",
            (tenant_id,),
        )
        role_id = int(cursor.fetchone()['id'])
        cursor.execute(
            'INSERT IGNORE INTO role_permissions (role_id,permission_id) '
            'SELECT %s,id FROM permissions', (role_id,),
        )


def _ensure_warehouses(db, tenant_id: int, organization_id: int, location_id: int) -> None:
    with db.cursor() as cursor:
        for code, name in (('COCINA', 'Cocina'), ('BARRA', 'Barra')):
            cursor.execute(
                'INSERT IGNORE INTO warehouses '
                '(tenant_id,organization_id,location_id,code,name,status,default_slot,'
                'negative_stock_policy,version) VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,1)',
                (tenant_id, organization_id, location_id, code, name, 'ACTIVE', 'BLOCK'),
            )


def _seed_operational_data(result) -> dict[str, object]:
    from app.main import create_app

    password = os.environ['DEMO_ADMIN_PASSWORD']
    with TestClient(create_app()) as client:
        login = client.post('/auth/login', json={'email': DEMO_EMAIL, 'password': password})
        if login.status_code != 200:
            raise RuntimeError(f'demo login failed: {login.status_code} {login.text}')
        headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
        approver_login = client.post('/auth/login', json={
            'email': 'inventory@restaurant.demo',
            'password': os.environ['DEMO_STAFF_PASSWORD'],
        })
        if approver_login.status_code != 200:
            raise RuntimeError(
                f'demo inventory approver login failed: '
                f'{approver_login.status_code} {approver_login.text}'
            )
        approver_headers = {
            'Authorization': f"Bearer {approver_login.json()['access_token']}"
        }

        item_specs = (
            ('DEMO-CERDO', 'Cerdo ficticio', 'KG', '78.50', 'REQUIRED', 'BOTH'),
            ('DEMO-ACEITE', 'Aceite vegetal', 'L', '42.00', 'OPTIONAL', 'BEST_BEFORE'),
            ('DEMO-SAL', 'Sal fina', 'KG', '18.00', 'OPTIONAL', 'NONE'),
            ('DEMO-TORTILLA', 'Tortilla de maíz', 'UNIT', '1.35', 'REQUIRED', 'BEST_BEFORE'),
            ('DEMO-REFRESCO', 'Refresco artesanal', 'UNIT', '16.00', 'REQUIRED', 'BEST_BEFORE'),
            ('DEMO-SALSA', 'Salsa preparada', 'PORTION', '8.00', 'REQUIRED', 'BOTH'),
            ('DEMO-CARNITAS', 'Carnitas preparadas', 'PORTION', '24.00', 'REQUIRED', 'BOTH'),
            ('DEMO-SERVILLETA', 'Servilleta', 'UNIT', '0.40', 'OPTIONAL', 'NONE'),
        )
        items = {}
        for code, name, uom, cost, lot_policy, date_policy in item_specs:
            items[code] = _api(client, 'POST', '/inventory-items', headers, {
                'location_id': result.location_id, 'code': code, 'name': name,
                'base_uom': uom, 'standard_unit_cost': cost, 'currency': 'MXN',
                'lot_tracking_policy': lot_policy, 'date_tracking_policy': date_policy,
            })

        db = _connection()
        try:
            _ensure_warehouses(db, result.tenant_id, result.organization_id, result.location_id)
            with db.cursor() as cursor:
                cursor.execute(
                    "UPDATE inventory_cost_revisions SET effective_at='2026-01-01 00:00:00' "
                    'WHERE tenant_id=%s', (result.tenant_id,),
                )
        finally:
            db.close()

        warehouses = _api(
            client, 'GET', f'/inventory/warehouses?location_id={result.location_id}', headers,
        )['items']
        by_code = {value['code']: value for value in warehouses}
        principal = next(value for value in warehouses if value['is_default'])
        cocina, barra = by_code['COCINA'], by_code['BARRA']

        supplier = _api(client, 'POST', '/inventory/suppliers', headers, {
            'organization_id': result.organization_id, 'code': 'PROV-DEMO-01',
            'name': 'Abastos La Estrella (Ficticio)',
            'contact_reference': 'compras@example.invalid',
            'location_ids': [result.location_id],
        })
        offerings = {}
        for code, item in items.items():
            offerings[code] = _api(
                client, 'POST', f"/inventory/suppliers/{supplier['id']}/offerings", headers,
                {'location_id': result.location_id, 'inventory_item_id': item['id'],
                 'supplier_item_code': f'FICT-{code}', 'purchase_uom': item['base_uom']},
            )

        dates = {'manufacture_date': '2026-09-01', 'expiry_date': '2027-09-01',
                 'best_before_date': '2027-08-15'}
        quantities = {
            'DEMO-CERDO': ('60', '77.00'), 'DEMO-ACEITE': ('30', '40.00'),
            'DEMO-SAL': ('20', '17.50'), 'DEMO-TORTILLA': ('360', '1.25'),
            'DEMO-REFRESCO': ('120', '15.50'), 'DEMO-SERVILLETA': ('500', '0.35'),
        }
        receipt_lines = []
        for number, (code, (quantity, cost)) in enumerate(quantities.items(), 1):
            item = items[code]
            line = {
                'supplier_offering_id': offerings[code]['id'],
                'received_quantity': quantity, 'accepted_quantity': quantity,
                'rejected_quantity': '0', 'unit_cost': cost, 'currency': 'MXN',
                'lot_code': f'DEMO-LOT-{number:02d}',
            }
            if item['date_tracking_policy'] != 'NONE':
                line.update({key: value for key, value in dates.items()
                             if not (item['date_tracking_policy'] == 'BEST_BEFORE' and key == 'expiry_date')})
            receipt_lines.append(line)
        receipt = _api(client, 'POST', '/inventory/goods-receipts', headers, {
            'supplier_id': supplier['id'], 'location_id': result.location_id,
            'warehouse_id': principal['id'], 'external_reference': 'DEMO-GR-001',
            'lines': receipt_lines,
        })
        receipt = _api(
            client, 'POST', f"/inventory/goods-receipts/{receipt['id']}:accept",
            {**headers, 'Idempotency-Key': 'demo-receipt-accept-001'},
            {'expected_version': receipt['version']},
        )

        # A purchase order intentionally remains approved/pending for a useful planning state.
        purchase_order = _api(client, 'POST', '/inventory/purchase-orders', headers, {
            'location_id': result.location_id, 'warehouse_id': principal['id'],
            'supplier_id': supplier['id'], 'currency': 'MXN',
            'expected_delivery_at': '2026-09-18T16:00:00Z',
            'external_reference': 'DEMO-PO-002',
            'notes': 'Reposición semanal ficticia para el recorrido.',
            'lines': [
                {'supplier_offering_id': offerings['DEMO-CERDO']['id'],
                 'ordered_quantity': '25', 'agreed_unit_price': '79.00'},
                {'supplier_offering_id': offerings['DEMO-TORTILLA']['id'],
                 'ordered_quantity': '180', 'agreed_unit_price': '1.30'},
            ],
        })
        for action in ('submit', 'approve'):
            purchase_order = _api(
                client, 'POST', f"/inventory/purchase-orders/{purchase_order['id']}:{action}",
                {**headers, 'Idempotency-Key': f'demo-po-{action}-002'},
                {'expected_version': purchase_order['version']},
            )

        _api(client, 'PUT', f"/inventory/loss-policies/{principal['id']}", headers, {
            'expected_version': 0, 'approval_value_threshold': '500',
            'currency': 'MXN', 'status': 'ACTIVE',
        })
        loss = _api(client, 'POST', '/inventory/losses', headers, {
            'warehouse_id': principal['id'], 'inventory_item_id': items['DEMO-CERDO']['id'],
            'category': 'PREPARATION_LOSS', 'source_quantity': '1.5', 'source_uom': 'KG',
            'reason': 'Recorte controlado del lote ficticio', 'occurred_at': '2026-09-12T10:15:00Z',
        })
        loss = _api(
            client, 'POST', f"/inventory/losses/{loss['id']}:post",
            {**headers, 'Idempotency-Key': 'demo-loss-post-001'},
            {'expected_version': loss['version']},
        )

        recipe = _api(client, 'POST', '/inventory/preparation-recipes', headers, {
            'location_id': result.location_id,
            'output_inventory_item_id': items['DEMO-CARNITAS']['id'],
            'expected_output_quantity': '12', 'output_uom': 'PORTION',
            'status': 'ACTIVE', 'expected_revision': 0,
            'components': [
                {'inventory_item_id': items['DEMO-CERDO']['id'], 'expected_quantity': '8',
                 'source_uom': 'KG', 'yield_basis': True},
                {'inventory_item_id': items['DEMO-SAL']['id'], 'expected_quantity': '0.25',
                 'source_uom': 'KG', 'yield_basis': False},
                {'inventory_item_id': items['DEMO-ACEITE']['id'], 'expected_quantity': '0.5',
                 'source_uom': 'L', 'yield_basis': False},
            ],
        })
        batch = _api(client, 'POST', '/inventory/preparation-batches', headers, {
            'recipe_version_id': recipe['id'], 'warehouse_id': principal['id'],
            'reference': 'DEMO-PREP-001',
            'inputs': [{'recipe_component_id': line['id'],
                        'source_quantity': line['expected_quantity'],
                        'source_uom': line['source_uom']} for line in recipe['components']],
            'output_quantity': '11.5', 'output_uom': 'PORTION',
            'output_lot_code': 'DEMO-PREP-LOT-01', 'manufacture_date': '2026-09-12',
            'expiry_date': '2026-09-15', 'best_before_date': '2026-09-14',
        })
        batch = _api(client, 'POST', f"/inventory/preparation-batches/{batch['id']}:start",
                     headers, {'expected_version': batch['version']})
        batch = _api(
            client, 'POST', f"/inventory/preparation-batches/{batch['id']}:complete",
            {**headers, 'Idempotency-Key': 'demo-prep-complete-001'},
            {'expected_version': batch['version']},
        )

        for code, minimum, target in (
            ('DEMO-CERDO', '55', '90'), ('DEMO-TORTILLA', '300', '500'),
            ('DEMO-REFRESCO', '100', '180'),
        ):
            _api(client, 'PUT',
                 f"/inventory/replenishment-policies/{principal['id']}/{items[code]['id']}",
                 headers, {'expected_version': 0, 'status': 'ACTIVE',
                           'minimum_quantity': minimum, 'target_quantity': target,
                           'source_uom': items[code]['base_uom']})

        transfer = _api(client, 'POST', '/inventory/transfers', headers, {
            'source_warehouse_id': principal['id'], 'destination_warehouse_id': cocina['id'],
            'reference': 'DEMO-TRANSFER-001',
            'lines': [{'inventory_item_id': items['DEMO-TORTILLA']['id'], 'quantity': '48'}],
        })
        for action in ('submit', 'ship'):
            transfer = _api(
                client, 'POST', f"/inventory/transfers/{transfer['id']}:{action}",
                {**headers, 'Idempotency-Key': f'demo-transfer-{action}-001'},
                {'expected_version': transfer['version']},
            )
        transfer = _api(
            client, 'POST', f"/inventory/transfers/{transfer['id']}:receive",
            {**headers, 'Idempotency-Key': 'demo-transfer-receive-001'},
            {'expected_version': transfer['version'],
             'receipts': [{'line_id': transfer['lines'][0]['id'], 'quantity': '48'}]},
        )

        count = _api(client, 'POST', '/inventory/physical-counts', headers, {
            'warehouse_id': principal['id'], 'count_scope': 'PARTIAL',
            'reason': 'Conteo de control DEMO', 'reference': 'DEMO-COUNT-001',
        })
        count = _api(client, 'PUT',
                     f"/inventory/physical-counts/{count['id']}/lines/{items['DEMO-CERDO']['id']}",
                     headers, {'expected_count_version': count['version'], 'expected_line_version': 0,
                               'source_quantity': '49.5', 'source_uom': 'KG'})
        for action in ('submit', 'approve', 'post'):
            action_headers = headers if action == 'submit' else approver_headers
            if action == 'post':
                action_headers = {
                    **approver_headers, 'Idempotency-Key': 'demo-count-post-001',
                }
            count = _api(client, 'POST', f"/inventory/physical-counts/{count['id']}:{action}",
                         action_headers, {'expected_version': count['version']})
        reconciliation = _api(client, 'POST', '/inventory/reconciliations', headers, {
            'physical_count_line_id': count['lines'][0]['id'],
            'period_start': '2026-09-01T00:00:00Z',
        })
        reconciliation = _api(
            client, 'POST', f"/inventory/reconciliations/{reconciliation['id']}:close",
            headers, {'expected_version': reconciliation['version']},
        )

        as_of = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
        snapshots = []
        for method in ('FIFO', 'STANDARD_COST'):
            snapshots.append(_api(
                client, 'POST', '/inventory/valuation-snapshots',
                {**headers, 'Idempotency-Key': f'demo-valuation-{method.lower()}-001'},
                {'warehouse_id': principal['id'], 'as_of': as_of,
                 'currency': 'MXN', 'valuation_method': method},
            ))

        # Active service and cash contexts populate Host, Gerencia and Caja without providers.
        table_ids = [result.table_resource_id]
        resources = _api(
            client, 'GET', f'/resources?location_id={result.location_id}&limit=100&offset=0', headers,
        )['items']
        table_ids = [value['id'] for value in resources if value['resource_type'] == 'TABLE'][:3]
        sessions = [_api(client, 'POST', f'/resources/{table_id}/service-sessions', headers,
                         {'party_size': index + 2})
                    for index, table_id in enumerate(table_ids)]
        cash = _api(
            client, 'POST',
            f"/resources/{result.cash_register_resource_id}/cash-sessions?location_id={result.location_id}",
            {**headers, 'Idempotency-Key': 'demo-cash-open-001'}, {'currency': 'MXN'},
        )
        _api(client, 'POST', f"/cash-sessions/{cash['id']}/movements?location_id={result.location_id}",
             {**headers, 'Idempotency-Key': 'demo-cash-float-001'},
             {'movement_type': 'OPENING_FLOAT', 'amount': '1500.00', 'currency': 'MXN',
              'reason': 'Fondo inicial ficticio', 'reference': 'DEMO-CASH-001'})

        return {
            'inventory_items': len(items), 'warehouses': len(warehouses),
            'suppliers': 1, 'goods_receipts': 1, 'losses': 1,
            'purchase_orders': 1, 'preparation_batches': 1,
            'replenishment_policies': 3, 'transfers': 1,
            'physical_counts': 1, 'reconciliations': 1,
            'valuation_snapshots': len(snapshots), 'active_service_sessions': len(sessions),
            'active_cash_sessions': 1, 'bar_warehouse_id': barra['id'],
        }


async def _bootstrap_core():
    # Import after the guard so this module can never silently select pilot constants.
    from app.bootstrap_pilot_minimum import bootstrap_pilot_minimum
    return await bootstrap_pilot_minimum()


def main() -> None:
    _guard()
    result = asyncio.run(_bootstrap_core())
    db = _connection()
    try:
        _grant_every_permission(db, result.tenant_id)
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS n FROM inventory_items WHERE tenant_id=%s AND code='DEMO-CERDO'",
                (result.tenant_id,),
            )
            already_seeded = int(cursor.fetchone()['n']) == 1
    finally:
        db.close()
    summary = {'tenant_id': result.tenant_id, 'location_id': result.location_id,
               'login': DEMO_EMAIL, 'status': 'already_seeded' if already_seeded else 'seeded'}
    if not already_seeded:
        summary.update(_seed_operational_data(result))
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
