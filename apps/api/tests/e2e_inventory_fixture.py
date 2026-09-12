"""Deterministic local fixture for the WS-34-B7 real-browser certification."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pymysql
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password
from app.main import create_app


SLUG = 'ws34-b7-browser-e2e'
PASSWORD = 'WS34 Browser Test 123!'
OPERATOR_EMAIL = 'ws34-b7-e2e-operator@example.test'
APPROVER_EMAIL = 'ws34-b7-e2e-approver@example.test'
PERMISSIONS = (
    'tenant.read', 'organization.read', 'location.read',
    'inventory.manage', 'inventory.read', 'inventory.cost.read',
    'inventory.supplier.manage', 'inventory.receipt.manage', 'inventory.receipt.accept',
    'inventory.loss.read', 'inventory.loss.manage', 'inventory.loss.approve',
    'inventory.count.read', 'inventory.count.manage', 'inventory.count.approve',
    'inventory.count.post', 'inventory.reconciliation.read',
    'inventory.reconciliation.manage',
    'inventory.purchase_order.read', 'inventory.purchase_order.manage',
    'inventory.purchase_order.approve',
)


def connection():
    return pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'mysql'), port=int(os.getenv('MYSQL_PORT', '3306')),
        user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'],
        database=os.environ['MYSQL_DATABASE'], autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def execute(db, statement: str, parameters=()) -> int:
    with db.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


def cleanup(db) -> None:
    with db.cursor() as cursor:
        cursor.execute('SELECT id FROM tenants WHERE slug=%s', (SLUG,))
        row = cursor.fetchone()
        if row:
            tenant_id = int(row['id'])
            cursor.execute(
                'SELECT DISTINCT TABLE_NAME FROM information_schema.COLUMNS '
                "WHERE TABLE_SCHEMA=DATABASE() AND COLUMN_NAME='tenant_id'"
            )
            tables = [value['TABLE_NAME'] for value in cursor.fetchall()]
            cursor.execute('SET FOREIGN_KEY_CHECKS=0')
            try:
                for table in tables:
                    cursor.execute(f'DELETE FROM `{table}` WHERE tenant_id=%s', (tenant_id,))
                cursor.execute('DELETE FROM tenants WHERE id=%s', (tenant_id,))
                cursor.execute('DELETE FROM users WHERE email IN (%s,%s)', (OPERATOR_EMAIL, APPROVER_EMAIL))
            finally:
                cursor.execute('SET FOREIGN_KEY_CHECKS=1')


def add_actor(db, tenant_id: int, location_id: int, email: str, name: str) -> None:
    user_id = execute(
        db, 'INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,%s,%s)',
        (email, hash_password(PASSWORD), name, 'ACTIVE'),
    )
    membership_id = execute(
        db, 'INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,%s)',
        (tenant_id, user_id, 'ACTIVE'),
    )
    role_id = execute(
        db, 'INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,%s,%s,%s)',
        (tenant_id, f'B7_E2E_{name.upper()}', 'WS-34-B7 browser certification', 'ACTIVE'),
    )
    execute(db, 'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)', (tenant_id, membership_id, role_id))
    execute(db, 'INSERT INTO membership_location_grants (tenant_id,membership_id,location_id) VALUES (%s,%s,%s)', (tenant_id, membership_id, location_id))
    for code in PERMISSIONS:
        execute(db, 'INSERT IGNORE INTO permissions (code,description) VALUES (%s,%s)', (code, f'Permission {code}'))
        with db.cursor() as cursor:
            cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,))
            permission_id = int(cursor.fetchone()['id'])
        execute(db, 'INSERT IGNORE INTO role_permissions (role_id,permission_id) VALUES (%s,%s)', (role_id, permission_id))


def api(client: TestClient, method: str, path: str, headers: dict[str, str], payload: dict):
    response = client.request(method, path, headers=headers, json=payload)
    if response.status_code >= 300:
        raise RuntimeError(f'{method} {path}: {response.status_code} {response.text}')
    return response.json()


def seed(db) -> None:
    cleanup(db)
    tenant_id = execute(db, 'INSERT INTO tenants (name,slug,status) VALUES (%s,%s,%s)', ('WS-34 B7 Browser Tenant', SLUG, 'ACTIVE'))
    organization_id = execute(db, 'INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,%s,%s,%s)', (tenant_id, 'B7', 'WS-34 B7 Organization', 'ACTIVE'))
    location_id = execute(db, 'INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,%s,%s,%s,%s)', (tenant_id, organization_id, 'E2E', 'WS-34 B7 Isolated Location', 'America/Mexico_City', 'ACTIVE'))
    execute(db, 'INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,%s,%s,%s,%s)', (tenant_id, organization_id, 'HIDDEN', 'Unauthorized Location', 'America/Mexico_City', 'ACTIVE'))
    add_actor(db, tenant_id, location_id, OPERATOR_EMAIL, 'Operator')
    add_actor(db, tenant_id, location_id, APPROVER_EMAIL, 'Approver')

    with TestClient(create_app()) as client:
        login = client.post('/auth/login', json={'email': OPERATOR_EMAIL, 'password': PASSWORD})
        if login.status_code != 200:
            raise RuntimeError(f'fixture login failed: {login.text}')
        headers = {'Authorization': f"Bearer {login.json()['access_token']}"}
        items = [
            api(client, 'POST', '/inventory-items', headers, {'location_id': location_id, 'code': 'B7-TOM', 'name': 'Tomate E2E', 'base_uom': 'UNIT', 'standard_unit_cost': '10', 'currency': 'MXN'}),
            api(client, 'POST', '/inventory-items', headers, {'location_id': location_id, 'code': 'B7-SAL', 'name': 'Sal E2E', 'base_uom': 'UNIT', 'standard_unit_cost': '5', 'currency': 'MXN'}),
        ]
        with db.cursor() as cursor:
            cursor.execute(
                "UPDATE inventory_cost_revisions SET effective_at='2026-01-01 00:00:00' "
                'WHERE tenant_id=%s', (tenant_id,),
            )
        warehouse_response = client.get(
            '/inventory/warehouses', headers=headers, params={'location_id': location_id},
        )
        if warehouse_response.status_code != 200:
            raise RuntimeError(f'warehouse lookup failed: {warehouse_response.text}')
        warehouse = warehouse_response.json()['items'][0]
        supplier = api(client, 'POST', '/inventory/suppliers', headers, {'organization_id': organization_id, 'code': 'B7-SUP', 'name': 'Proveedor E2E', 'contact_reference': None, 'location_ids': [location_id]})
        for item in items:
            api(client, 'POST', f"/inventory/suppliers/{supplier['id']}/offerings", headers, {'location_id': location_id, 'inventory_item_id': item['id'], 'supplier_item_code': item['code'], 'purchase_uom': 'UNIT'})
            api(client, 'POST', '/inventory/stock-movements', {**headers, 'Idempotency-Key': f"b7-opening-{item['id']}"}, {'inventory_item_id': item['id'], 'warehouse_id': warehouse['id'], 'movement_type': 'OPENING_BALANCE', 'quantity': '10', 'uom': 'UNIT', 'reversal_of_movement_id': None, 'reason': 'WS-34-B7 deterministic baseline', 'reference': 'B7-E2E'})
        api(client, 'PUT', f"/inventory/loss-policies/{warehouse['id']}", headers, {'expected_version': 0, 'approval_value_threshold': '1', 'currency': 'MXN', 'status': 'ACTIVE'})
    print(json.dumps({'tenant_id': tenant_id, 'location_id': location_id, 'operator': OPERATOR_EMAIL, 'approver': APPROVER_EMAIL}))


def verify(db) -> None:
    with db.cursor() as cursor:
        cursor.execute('SELECT id FROM tenants WHERE slug=%s', (SLUG,))
        tenant_id = int(cursor.fetchone()['id'])
        checks = {}
        for name, sql in {
            'accepted_receipts': "SELECT COUNT(*) AS n FROM goods_receipts WHERE tenant_id=%s AND status='ACCEPTED'",
            'receipt_lines': 'SELECT COUNT(*) AS n FROM goods_receipt_lines WHERE tenant_id=%s',
            'receipt_movements': "SELECT COUNT(*) AS n FROM stock_movements WHERE tenant_id=%s AND movement_type='GOODS_RECEIPT'",
            'posted_losses': "SELECT COUNT(*) AS n FROM inventory_losses l WHERE tenant_id=%s AND status='POSTED' AND standard_cost_revision_id IS NOT NULL AND extended_loss_cost IS NOT NULL AND EXISTS (SELECT 1 FROM stock_movements m WHERE m.inventory_loss_id=l.id)",
            'posted_partial_counts': "SELECT COUNT(*) AS n FROM physical_counts WHERE tenant_id=%s AND count_scope='PARTIAL' AND status='POSTED'",
            'posted_full_counts': "SELECT COUNT(*) AS n FROM physical_counts WHERE tenant_id=%s AND count_scope='FULL' AND status='POSTED'",
            'incomplete_full_counts': "SELECT COUNT(*) AS n FROM physical_counts WHERE tenant_id=%s AND count_scope='FULL' AND status='APPROVED'",
            'closed_reconciliations': "SELECT COUNT(*) AS n FROM inventory_reconciliations WHERE tenant_id=%s AND status='CLOSED'",
            'closed_purchase_orders': "SELECT COUNT(*) AS n FROM purchase_orders WHERE tenant_id=%s AND status='CLOSED'",
        }.items():
            cursor.execute(sql, (tenant_id,))
            checks[name] = int(cursor.fetchone()['n'])
    expected = {
        'accepted_receipts': 3, 'receipt_lines': 5, 'receipt_movements': 5,
        'posted_losses': 1, 'posted_partial_counts': 1, 'posted_full_counts': 1,
        'incomplete_full_counts': 1, 'closed_reconciliations': 1,
        'closed_purchase_orders': 1,
    }
    if checks != expected:
        raise RuntimeError(f'authoritative E2E evidence mismatch: {checks} != {expected}')
    print(json.dumps(checks, sort_keys=True))


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else 'seed'
    db = connection()
    try:
        if action == 'seed': seed(db)
        elif action == 'verify': verify(db)
        elif action == 'cleanup': cleanup(db)
        else: raise SystemExit(f'unknown action: {action}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
