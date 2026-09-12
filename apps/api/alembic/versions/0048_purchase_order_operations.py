"""add purchase order operations

Revision ID: 0048_purchase_order_operations
Revises: 0047_physical_count_full_scope
Create Date: 2026-09-12
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0048_purchase_order_operations'
down_revision: str | None = '0047_physical_count_full_scope'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
OPTIONS = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
PERMISSIONS = {
    'inventory.purchase_order.read': 'Read purchase orders.',
    'inventory.purchase_order.manage': 'Manage purchase orders.',
    'inventory.purchase_order.approve': 'Approve purchase orders.',
}


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _column(table: str, name: str) -> bool:
    return any(row['name'] == name for row in _inspector().get_columns(table))


def _constraint(table: str, name: str, kind: str) -> bool:
    getter = {'foreignkey': _inspector().get_foreign_keys,
              'unique': _inspector().get_unique_constraints,
              'check': _inspector().get_check_constraints}[kind]
    return any(row['name'] == name for row in getter(table))


def _index(table: str, name: str) -> bool:
    return any(row['name'] == name for row in _inspector().get_indexes(table))


def _seed_permissions() -> None:
    connection = op.get_bind()
    for code, description in PERMISSIONS.items():
        connection.execute(sa.text(
            'INSERT INTO permissions (code,description) SELECT :code,:description '
            'WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code=:code)'
        ), {'code': code, 'description': description})
        connection.execute(sa.text(
            'INSERT INTO role_permissions (role_id,permission_id) '
            'SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code=:code '
            "WHERE r.name='TENANT_ADMIN' AND r.status='ACTIVE' AND NOT EXISTS "
            '(SELECT 1 FROM role_permissions rp WHERE rp.role_id=r.id AND rp.permission_id=p.id)'
        ), {'code': code})


def _create_orders() -> None:
    if not _table('purchase_orders'):
        op.create_table(
            'purchase_orders',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
            sa.Column('supplier_id', sa.BigInteger(), nullable=False),
            sa.Column('status', sa.String(24), server_default=sa.text("'DRAFT'"), nullable=False),
            sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
            sa.Column('expected_delivery_at', sa.DateTime()),
            sa.Column('external_reference', sa.String(200)),
            sa.Column('notes', sa.String(1000)),
            sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
            sa.Column('created_by_actor_id', sa.BigInteger(), nullable=False),
            sa.Column('submitted_at', sa.DateTime()),
            sa.Column('submitted_by_actor_id', sa.BigInteger()),
            sa.Column('approved_at', sa.DateTime()),
            sa.Column('approved_by_actor_id', sa.BigInteger()),
            sa.Column('terminated_at', sa.DateTime()),
            sa.Column('terminated_by_actor_id', sa.BigInteger()),
            sa.Column('submitted_command_key', sa.String(128, collation='ascii_bin')),
            sa.Column('approved_command_key', sa.String(128, collation='ascii_bin')),
            sa.Column('terminated_command_key', sa.String(128, collation='ascii_bin')),
            sa.Column('terminated_action', sa.String(16, collation='ascii_bin')),
            sa.Column('last_command_key', sa.String(128, collation='ascii_bin')),
            sa.Column('last_command_action', sa.String(16, collation='ascii_bin')),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.ForeignKeyConstraint(['supplier_id', 'tenant_id', 'organization_id'], ['suppliers.id', 'suppliers.tenant_id', 'suppliers.organization_id'], name='fk_purchase_orders_supplier_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['supplier_id', 'tenant_id', 'organization_id', 'location_id'], ['supplier_locations.supplier_id', 'supplier_locations.tenant_id', 'supplier_locations.organization_id', 'supplier_locations.location_id'], name='fk_purchase_orders_availability_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['warehouse_id', 'tenant_id', 'organization_id', 'location_id'], ['warehouses.id', 'warehouses.tenant_id', 'warehouses.organization_id', 'warehouses.location_id'], name='fk_purchase_orders_warehouse_scope', ondelete='RESTRICT'),
            sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'warehouse_id', name='uq_purchase_orders_scope'),
            sa.CheckConstraint("status IN ('DRAFT','SUBMITTED','APPROVED','PARTIALLY_RECEIVED','RECEIVED','CLOSED','CANCELLED')", name='ck_purchase_orders_status'),
            sa.CheckConstraint('version >= 1', name='ck_purchase_orders_version'),
            sa.CheckConstraint("currency REGEXP '^[A-Z][A-Z][A-Z]$'", name='ck_purchase_orders_currency'),
            sa.CheckConstraint(
                "(status='DRAFT' AND submitted_at IS NULL AND approved_at IS NULL AND terminated_at IS NULL) OR "
                "(status='SUBMITTED' AND submitted_at IS NOT NULL AND submitted_by_actor_id IS NOT NULL AND approved_at IS NULL AND terminated_at IS NULL) OR "
                "(status IN ('APPROVED','PARTIALLY_RECEIVED','RECEIVED') AND submitted_at IS NOT NULL AND submitted_by_actor_id IS NOT NULL AND approved_at IS NOT NULL AND approved_by_actor_id IS NOT NULL AND terminated_at IS NULL) OR "
                "(status='CLOSED' AND submitted_at IS NOT NULL AND approved_at IS NOT NULL AND terminated_at IS NOT NULL AND terminated_by_actor_id IS NOT NULL) OR "
                "(status='CANCELLED' AND terminated_at IS NOT NULL AND terminated_by_actor_id IS NOT NULL)",
                name='ck_purchase_orders_lifecycle_evidence'),
            **OPTIONS)
    else:
        for name in ('submitted_command_key', 'approved_command_key', 'terminated_command_key', 'terminated_action'):
            if not _column('purchase_orders', name):
                op.add_column('purchase_orders', sa.Column(name, sa.String(16 if name == 'terminated_action' else 128, collation='ascii_bin')))
        availability_orphans = op.get_bind().scalar(sa.text(
            'SELECT COUNT(*) FROM purchase_orders po LEFT JOIN supplier_locations sl '
            'ON sl.supplier_id=po.supplier_id AND sl.tenant_id=po.tenant_id '
            'AND sl.organization_id=po.organization_id AND sl.location_id=po.location_id '
            'WHERE sl.id IS NULL'))
        if (
            not availability_orphans
            and not _constraint('purchase_orders', 'fk_purchase_orders_availability_scope', 'foreignkey')
        ):
            op.create_foreign_key('fk_purchase_orders_availability_scope', 'purchase_orders', 'supplier_locations', ['supplier_id', 'tenant_id', 'organization_id', 'location_id'], ['supplier_id', 'tenant_id', 'organization_id', 'location_id'], ondelete='RESTRICT')
    if not _index('purchase_orders', 'ix_purchase_orders_location_status'):
        op.create_index('ix_purchase_orders_location_status', 'purchase_orders', ['tenant_id', 'location_id', 'status', 'id'])


def _create_lines() -> None:
    if _table('purchase_order_lines'):
        if not _constraint('purchase_order_lines', 'uq_purchase_order_lines_receipt_scope', 'unique'):
            op.create_unique_constraint('uq_purchase_order_lines_receipt_scope', 'purchase_order_lines', ['id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'warehouse_id', 'supplier_offering_id', 'inventory_item_id'])
        if not _constraint('purchase_order_lines', 'uq_purchase_order_lines_number', 'unique'):
            op.create_unique_constraint('uq_purchase_order_lines_number', 'purchase_order_lines', ['purchase_order_id', 'line_number'])
        if not _constraint('purchase_order_lines', 'fk_purchase_order_lines_conversion_scope', 'foreignkey'):
            op.create_foreign_key('fk_purchase_order_lines_conversion_scope', 'purchase_order_lines', 'item_uom_conversions', ['conversion_revision_id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'], ['id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'], ondelete='RESTRICT')
        return
    op.create_table(
        'purchase_order_lines',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
        sa.Column('supplier_id', sa.BigInteger(), nullable=False),
        sa.Column('purchase_order_id', sa.BigInteger(), nullable=False),
        sa.Column('supplier_offering_id', sa.BigInteger(), nullable=False),
        sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('ordered_quantity', sa.Numeric(19, 6), nullable=False),
        sa.Column('source_uom', sa.String(32, collation='ascii_bin'), nullable=False),
        sa.Column('conversion_revision_id', sa.BigInteger()),
        sa.Column('conversion_factor', sa.Numeric(25, 12), nullable=False),
        sa.Column('base_uom_evidence', sa.String(16), nullable=False),
        sa.Column('normalized_ordered_quantity', sa.Numeric(19, 6), nullable=False),
        sa.Column('agreed_unit_price', sa.Numeric(19, 6), nullable=False),
        sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(['purchase_order_id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'warehouse_id'], ['purchase_orders.id', 'purchase_orders.tenant_id', 'purchase_orders.organization_id', 'purchase_orders.location_id', 'purchase_orders.supplier_id', 'purchase_orders.warehouse_id'], name='fk_purchase_order_lines_order_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['supplier_offering_id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'inventory_item_id'], ['supplier_offerings.id', 'supplier_offerings.tenant_id', 'supplier_offerings.organization_id', 'supplier_offerings.location_id', 'supplier_offerings.supplier_id', 'supplier_offerings.inventory_item_id'], name='fk_purchase_order_lines_offering_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['conversion_revision_id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'], ['item_uom_conversions.id', 'item_uom_conversions.tenant_id', 'item_uom_conversions.organization_id', 'item_uom_conversions.location_id', 'item_uom_conversions.inventory_item_id'], name='fk_purchase_order_lines_conversion_scope', ondelete='RESTRICT'),
        sa.UniqueConstraint('id', 'purchase_order_id', name='uq_purchase_order_lines_order'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'warehouse_id', 'supplier_offering_id', 'inventory_item_id', name='uq_purchase_order_lines_receipt_scope'),
        sa.UniqueConstraint('purchase_order_id', 'supplier_offering_id', name='uq_purchase_order_lines_offering'),
        sa.UniqueConstraint('purchase_order_id', 'line_number', name='uq_purchase_order_lines_number'),
        sa.CheckConstraint('line_number >= 1', name='ck_purchase_order_lines_number'),
        sa.CheckConstraint('ordered_quantity > 0 AND conversion_factor > 0 AND normalized_ordered_quantity > 0 AND agreed_unit_price >= 0', name='ck_purchase_order_lines_values'),
        sa.CheckConstraint("currency REGEXP '^[A-Z][A-Z][A-Z]$'", name='ck_purchase_order_lines_currency'),
        sa.CheckConstraint("source_uom REGEXP '^[A-Z][A-Z0-9_]{0,31}$'", name='ck_purchase_order_lines_source_uom'),
        **OPTIONS)


def _extend_receiving() -> None:
    if not _column('goods_receipts', 'purchase_order_id'):
        op.add_column('goods_receipts', sa.Column('purchase_order_id', sa.BigInteger()))
    if not _column('goods_receipt_lines', 'purchase_order_line_id'):
        op.add_column('goods_receipt_lines', sa.Column('purchase_order_line_id', sa.BigInteger()))
    if not _constraint('goods_receipts', 'fk_goods_receipts_purchase_order_scope', 'foreignkey'):
        op.create_foreign_key('fk_goods_receipts_purchase_order_scope', 'goods_receipts', 'purchase_orders', ['purchase_order_id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'warehouse_id'], ['id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'warehouse_id'], ondelete='RESTRICT')
    if not _constraint('goods_receipt_lines', 'fk_goods_receipt_lines_purchase_order_scope', 'foreignkey'):
        op.create_foreign_key('fk_goods_receipt_lines_purchase_order_scope', 'goods_receipt_lines', 'purchase_order_lines', ['purchase_order_line_id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'warehouse_id', 'supplier_offering_id', 'inventory_item_id'], ['id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'warehouse_id', 'supplier_offering_id', 'inventory_item_id'], ondelete='RESTRICT')
    if not _index('goods_receipts', 'ix_goods_receipts_purchase_order'):
        op.create_index('ix_goods_receipts_purchase_order', 'goods_receipts', ['tenant_id', 'purchase_order_id', 'status', 'id'])
    if not _index('goods_receipt_lines', 'ix_goods_receipt_lines_purchase_order_line'):
        op.create_index('ix_goods_receipt_lines_purchase_order_line', 'goods_receipt_lines', ['tenant_id', 'purchase_order_line_id', 'goods_receipt_id'])


def upgrade() -> None:
    _seed_permissions()
    _create_orders()
    _create_lines()
    _extend_receiving()


def downgrade() -> None:
    connection = op.get_bind()
    if _table('purchase_orders') and connection.scalar(sa.text('SELECT COUNT(*) FROM purchase_orders')):
        raise RuntimeError('Cannot downgrade 0048: PurchaseOrder evidence exists')
    for table, name in (('goods_receipt_lines', 'fk_goods_receipt_lines_purchase_order_scope'), ('goods_receipt_lines', 'fk_goods_receipt_lines_purchase_order_line'), ('goods_receipts', 'fk_goods_receipts_purchase_order_scope'), ('goods_receipts', 'fk_goods_receipts_purchase_order')):
        if _table(table) and _constraint(table, name, 'foreignkey'):
            op.drop_constraint(name, table, type_='foreignkey')
    for table, name in (
        ('goods_receipt_lines', 'ix_goods_receipt_lines_purchase_order_line'),
        ('goods_receipts', 'ix_goods_receipts_purchase_order'),
        ('goods_receipt_lines', 'fk_goods_receipt_lines_purchase_order_scope'),
        ('goods_receipts', 'fk_goods_receipts_purchase_order_scope'),
    ):
        if _table(table) and _index(table, name):
            op.drop_index(name, table_name=table)
    if _table('goods_receipt_lines') and _column('goods_receipt_lines', 'purchase_order_line_id'):
        op.drop_column('goods_receipt_lines', 'purchase_order_line_id')
    if _table('goods_receipts') and _column('goods_receipts', 'purchase_order_id'):
        op.drop_column('goods_receipts', 'purchase_order_id')
    if _table('purchase_order_lines'):
        op.drop_table('purchase_order_lines')
    if _table('purchase_orders'):
        if _index('purchase_orders', 'ix_purchase_orders_location_status'):
            op.drop_index('ix_purchase_orders_location_status', table_name='purchase_orders')
        op.drop_table('purchase_orders')
    connection.execute(sa.text('DELETE rp FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id WHERE p.code IN :codes').bindparams(sa.bindparam('codes', expanding=True)), {'codes': tuple(PERMISSIONS)})
    connection.execute(sa.text('DELETE FROM permissions WHERE code IN :codes').bindparams(sa.bindparam('codes', expanding=True)), {'codes': tuple(PERMISSIONS)})
