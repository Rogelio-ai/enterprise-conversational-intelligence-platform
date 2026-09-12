"""add supplier and direct goods receiving authority

Revision ID: 0044_supplier_direct_receiving
Revises: 0043_immutable_recipe_versions
Create Date: 2026-09-11
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0044_supplier_direct_receiving'
down_revision: str | None = '0043_immutable_recipe_versions'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}
PERMISSIONS = {
    'inventory.supplier.manage': 'Manage inventory suppliers and offerings.',
    'inventory.receipt.manage': 'Create and cancel direct goods receipts.',
    'inventory.receipt.accept': 'Accept direct goods receipts into stock.',
    'inventory.cost.read': 'Read inventory standard and receipt cost evidence.',
}


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _column(table: str, name: str) -> bool:
    return any(row['name'] == name for row in _inspector().get_columns(table))


def _constraint(table: str, name: str, kind: str) -> bool:
    getter = {
        'foreignkey': _inspector().get_foreign_keys,
        'unique': _inspector().get_unique_constraints,
        'check': _inspector().get_check_constraints,
    }[kind]
    return any(row['name'] == name for row in getter(table))


def _index(table: str, name: str) -> bool:
    return any(row['name'] == name for row in _inspector().get_indexes(table))


def _seed_permissions() -> None:
    connection = op.get_bind()
    for code, description in PERMISSIONS.items():
        connection.execute(sa.text(
            'INSERT INTO permissions (code,description) '
            'SELECT :code,:description WHERE NOT EXISTS '
            '(SELECT 1 FROM permissions WHERE code=:code)'
        ), {'code': code, 'description': description})
        connection.execute(sa.text(
            'INSERT INTO role_permissions (role_id,permission_id) '
            'SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code=:code '
            "WHERE r.name='TENANT_ADMIN' AND r.status='ACTIVE' AND NOT EXISTS "
            '(SELECT 1 FROM role_permissions rp WHERE rp.role_id=r.id '
            'AND rp.permission_id=p.id)'
        ), {'code': code})


def _create_suppliers() -> None:
    if not _table('suppliers'):
        op.create_table(
            'suppliers',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('code', sa.String(64, collation='utf8mb4_bin'), nullable=False),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
            sa.Column('contact_reference', sa.String(200), nullable=True),
            sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_suppliers_tenant', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['organization_id', 'tenant_id'], ['organizations.id', 'organizations.tenant_id'], name='fk_suppliers_organization_scope', ondelete='RESTRICT'),
            sa.UniqueConstraint('id', 'tenant_id', 'organization_id', name='uq_suppliers_scope'),
            sa.UniqueConstraint('tenant_id', 'organization_id', 'code', name='uq_suppliers_organization_code'),
            sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_suppliers_status'),
            sa.CheckConstraint('version >= 1', name='ck_suppliers_version'),
            **OPTIONS,
        )
        op.create_index('ix_suppliers_organization_status', 'suppliers', ['tenant_id', 'organization_id', 'status', 'name', 'id'])


def _create_supplier_locations() -> None:
    if not _table('supplier_locations'):
        op.create_table(
            'supplier_locations',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('supplier_id', sa.BigInteger(), nullable=False),
            sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['supplier_id', 'tenant_id', 'organization_id'], ['suppliers.id', 'suppliers.tenant_id', 'suppliers.organization_id'], name='fk_supplier_locations_supplier_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_supplier_locations_location_scope', ondelete='RESTRICT'),
            sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', name='uq_supplier_locations_scope'),
            sa.UniqueConstraint('supplier_id', 'tenant_id', 'organization_id', 'location_id', name='uq_supplier_locations_supplier_location'),
            sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_supplier_locations_status'),
            **OPTIONS,
        )


def _create_offerings() -> None:
    if not _table('supplier_offerings'):
        op.create_table(
            'supplier_offerings',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('supplier_id', sa.BigInteger(), nullable=False),
            sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
            sa.Column('supplier_item_code', sa.String(100, collation='utf8mb4_bin'), nullable=True),
            sa.Column('purchase_uom', sa.String(32, collation='ascii_bin'), nullable=False),
            sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
            sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['supplier_id', 'tenant_id', 'organization_id'], ['suppliers.id', 'suppliers.tenant_id', 'suppliers.organization_id'], name='fk_supplier_offerings_supplier_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['supplier_id', 'tenant_id', 'organization_id', 'location_id'], ['supplier_locations.supplier_id', 'supplier_locations.tenant_id', 'supplier_locations.organization_id', 'supplier_locations.location_id'], name='fk_supplier_offerings_availability_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'], ['inventory_items.id', 'inventory_items.tenant_id', 'inventory_items.organization_id', 'inventory_items.location_id'], name='fk_supplier_offerings_item_scope', ondelete='RESTRICT'),
            sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'inventory_item_id', name='uq_supplier_offerings_scope'),
            sa.UniqueConstraint('supplier_id', 'location_id', 'inventory_item_id', name='uq_supplier_offerings_supplier_item'),
            sa.CheckConstraint("purchase_uom REGEXP '^[A-Z][A-Z0-9_]{0,31}$'", name='ck_supplier_offerings_purchase_uom'),
            sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_supplier_offerings_status'),
            sa.CheckConstraint('version >= 1', name='ck_supplier_offerings_version'),
            **OPTIONS,
        )
        op.create_index('ix_supplier_offerings_location_status', 'supplier_offerings', ['tenant_id', 'location_id', 'supplier_id', 'status', 'id'])


def _create_receipts() -> None:
    if not _table('goods_receipts'):
        op.create_table(
            'goods_receipts',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
            sa.Column('supplier_id', sa.BigInteger(), nullable=False),
            sa.Column('external_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
            sa.Column('status', sa.String(16), server_default=sa.text("'DRAFT'"), nullable=False),
            sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
            sa.Column('created_by_actor_id', sa.BigInteger(), nullable=False),
            sa.Column('accepted_at', sa.DateTime(), nullable=True),
            sa.Column('accepted_by_actor_id', sa.BigInteger(), nullable=True),
            sa.Column('cancelled_at', sa.DateTime(), nullable=True),
            sa.Column('cancelled_by_actor_id', sa.BigInteger(), nullable=True),
            sa.Column('acceptance_actor_scope', sa.String(200, collation='ascii_bin'), nullable=True),
            sa.Column('acceptance_idempotency_key', sa.String(128, collation='ascii_bin'), nullable=True),
            sa.Column('acceptance_fingerprint', sa.String(64, collation='ascii_bin'), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['supplier_id', 'tenant_id', 'organization_id'], ['suppliers.id', 'suppliers.tenant_id', 'suppliers.organization_id'], name='fk_goods_receipts_supplier_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['supplier_id', 'tenant_id', 'organization_id', 'location_id'], ['supplier_locations.supplier_id', 'supplier_locations.tenant_id', 'supplier_locations.organization_id', 'supplier_locations.location_id'], name='fk_goods_receipts_availability_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['warehouse_id', 'tenant_id', 'organization_id', 'location_id'], ['warehouses.id', 'warehouses.tenant_id', 'warehouses.organization_id', 'warehouses.location_id'], name='fk_goods_receipts_warehouse_scope', ondelete='RESTRICT'),
            sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'warehouse_id', name='uq_goods_receipts_scope'),
            sa.UniqueConstraint('tenant_id', 'acceptance_actor_scope', 'acceptance_idempotency_key', name='uq_goods_receipts_acceptance_idempotency'),
            sa.UniqueConstraint('supplier_id', 'location_id', 'external_reference', name='uq_goods_receipts_external_reference'),
            sa.CheckConstraint("status IN ('DRAFT','ACCEPTED','CANCELLED')", name='ck_goods_receipts_status'),
            sa.CheckConstraint('version >= 1', name='ck_goods_receipts_version'),
            sa.CheckConstraint("(status='DRAFT' AND accepted_at IS NULL AND cancelled_at IS NULL) OR (status='ACCEPTED' AND accepted_at IS NOT NULL AND accepted_by_actor_id IS NOT NULL AND acceptance_actor_scope IS NOT NULL AND acceptance_idempotency_key IS NOT NULL AND acceptance_fingerprint IS NOT NULL AND cancelled_at IS NULL) OR (status='CANCELLED' AND cancelled_at IS NOT NULL AND accepted_at IS NULL)", name='ck_goods_receipts_lifecycle_evidence'),
            **OPTIONS,
        )
        op.create_index('ix_goods_receipts_location_status', 'goods_receipts', ['tenant_id', 'location_id', 'status', 'id'])


def _create_receipt_lines() -> None:
    if not _table('goods_receipt_lines'):
        op.create_table(
            'goods_receipt_lines',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
            sa.Column('supplier_id', sa.BigInteger(), nullable=False),
            sa.Column('goods_receipt_id', sa.BigInteger(), nullable=False),
            sa.Column('supplier_offering_id', sa.BigInteger(), nullable=False),
            sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
            sa.Column('line_number', sa.Integer(), nullable=False),
            sa.Column('received_quantity', sa.Numeric(19, 6), nullable=False),
            sa.Column('accepted_quantity', sa.Numeric(19, 6), nullable=False),
            sa.Column('rejected_quantity', sa.Numeric(19, 6), nullable=False),
            sa.Column('source_uom', sa.String(32, collation='ascii_bin'), nullable=False),
            sa.Column('unit_cost', sa.Numeric(19, 6), nullable=False),
            sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
            sa.Column('conversion_revision_id', sa.BigInteger(), nullable=True),
            sa.Column('conversion_factor', sa.Numeric(25, 12), nullable=True),
            sa.Column('base_uom_evidence', sa.String(16), nullable=True),
            sa.Column('normalized_quantity', sa.Numeric(19, 6), nullable=True),
            sa.Column('extended_cost', sa.Numeric(31, 12), nullable=True),
            sa.Column('evidence_status', sa.String(16), server_default=sa.text("'PENDING'"), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['goods_receipt_id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'warehouse_id'], ['goods_receipts.id', 'goods_receipts.tenant_id', 'goods_receipts.organization_id', 'goods_receipts.location_id', 'goods_receipts.supplier_id', 'goods_receipts.warehouse_id'], name='fk_goods_receipt_lines_receipt_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['supplier_offering_id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id', 'inventory_item_id'], ['supplier_offerings.id', 'supplier_offerings.tenant_id', 'supplier_offerings.organization_id', 'supplier_offerings.location_id', 'supplier_offerings.supplier_id', 'supplier_offerings.inventory_item_id'], name='fk_goods_receipt_lines_offering_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['conversion_revision_id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'], ['item_uom_conversions.id', 'item_uom_conversions.tenant_id', 'item_uom_conversions.organization_id', 'item_uom_conversions.location_id', 'item_uom_conversions.inventory_item_id'], name='fk_goods_receipt_lines_conversion_scope', ondelete='RESTRICT'),
            sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'goods_receipt_id', 'inventory_item_id', name='uq_goods_receipt_lines_scope'),
            sa.UniqueConstraint('goods_receipt_id', 'line_number', name='uq_goods_receipt_lines_number'),
            sa.UniqueConstraint('goods_receipt_id', 'supplier_offering_id', name='uq_goods_receipt_lines_offering'),
            sa.CheckConstraint('line_number >= 1', name='ck_goods_receipt_lines_number'),
            sa.CheckConstraint('received_quantity > 0 AND accepted_quantity >= 0 AND rejected_quantity >= 0 AND accepted_quantity + rejected_quantity = received_quantity', name='ck_goods_receipt_lines_quantities'),
            sa.CheckConstraint('unit_cost >= 0', name='ck_goods_receipt_lines_cost'),
            sa.CheckConstraint("currency REGEXP '^[A-Z][A-Z][A-Z]$'", name='ck_goods_receipt_lines_currency'),
            sa.CheckConstraint("source_uom REGEXP '^[A-Z][A-Z0-9_]{0,31}$'", name='ck_goods_receipt_lines_source_uom'),
            sa.CheckConstraint("evidence_status IN ('PENDING','RESOLVED','REJECTED_ONLY')", name='ck_goods_receipt_lines_evidence_status'),
            sa.CheckConstraint("(evidence_status='PENDING' AND normalized_quantity IS NULL AND conversion_factor IS NULL AND base_uom_evidence IS NULL AND extended_cost IS NULL) OR (evidence_status='RESOLVED' AND accepted_quantity > 0 AND normalized_quantity > 0 AND conversion_factor > 0 AND base_uom_evidence IS NOT NULL AND extended_cost IS NOT NULL) OR (evidence_status='REJECTED_ONLY' AND accepted_quantity=0 AND normalized_quantity=0 AND conversion_factor > 0 AND base_uom_evidence IS NOT NULL AND extended_cost=0)", name='ck_goods_receipt_lines_evidence'),
            **OPTIONS,
        )


def _extend_movements() -> None:
    if not _column('stock_movements', 'goods_receipt_id'):
        op.add_column('stock_movements', sa.Column('goods_receipt_id', sa.BigInteger(), nullable=True))
    if not _column('stock_movements', 'goods_receipt_line_id'):
        op.add_column('stock_movements', sa.Column('goods_receipt_line_id', sa.BigInteger(), nullable=True))
    for name in ('ck_stock_movements_type', 'ck_stock_movements_sign'):
        if _constraint('stock_movements', name, 'check'):
            op.drop_constraint(name, 'stock_movements', type_='check')
    op.create_check_constraint('ck_stock_movements_type', 'stock_movements', "movement_type IN ('OPENING_BALANCE','MANUAL_IN','MANUAL_OUT','ADJUSTMENT','REVERSAL','CONSUMPTION','GOODS_RECEIPT')")
    op.create_check_constraint('ck_stock_movements_sign', 'stock_movements', "(movement_type IN ('OPENING_BALANCE','MANUAL_IN','GOODS_RECEIPT') AND quantity>0) OR (movement_type IN ('MANUAL_OUT','CONSUMPTION') AND quantity<0) OR (movement_type IN ('ADJUSTMENT','REVERSAL') AND quantity<>0)")
    if not _constraint('stock_movements', 'uq_stock_movements_receipt_line', 'unique'):
        op.create_unique_constraint('uq_stock_movements_receipt_line', 'stock_movements', ['goods_receipt_line_id'])
    if not _constraint('stock_movements', 'fk_stock_movements_receipt_line_scope', 'foreignkey'):
        if _index('stock_movements', 'fk_stock_movements_receipt_line_scope'):
            op.drop_index('fk_stock_movements_receipt_line_scope', table_name='stock_movements')
        op.create_foreign_key('fk_stock_movements_receipt_line_scope', 'stock_movements', 'goods_receipt_lines', ['goods_receipt_line_id', 'tenant_id', 'organization_id', 'location_id', 'goods_receipt_id', 'inventory_item_id'], ['id', 'tenant_id', 'organization_id', 'location_id', 'goods_receipt_id', 'inventory_item_id'], ondelete='RESTRICT')
    if not _constraint('stock_movements', 'ck_stock_movements_receipt_evidence', 'check'):
        op.create_check_constraint('ck_stock_movements_receipt_evidence', 'stock_movements', "(movement_type='GOODS_RECEIPT' AND goods_receipt_id IS NOT NULL AND goods_receipt_line_id IS NOT NULL) OR (movement_type<>'GOODS_RECEIPT' AND goods_receipt_id IS NULL AND goods_receipt_line_id IS NULL)")
    if not _index('stock_movements', 'ix_stock_movements_receipt'):
        op.create_index('ix_stock_movements_receipt', 'stock_movements', ['tenant_id', 'goods_receipt_id', 'goods_receipt_line_id'])


def upgrade() -> None:
    _seed_permissions()
    _create_suppliers()
    _create_supplier_locations()
    _create_offerings()
    _create_receipts()
    _create_receipt_lines()
    _extend_movements()


def downgrade() -> None:
    connection = op.get_bind()
    accepted_receipt_movements = connection.scalar(sa.text(
        "SELECT COUNT(*) FROM stock_movements WHERE movement_type='GOODS_RECEIPT'"
    ))
    if accepted_receipt_movements:
        raise RuntimeError(
            'Cannot downgrade 0044: accepted GoodsReceipt stock history exists'
        )
    if _index('stock_movements', 'ix_stock_movements_receipt'):
        op.drop_index('ix_stock_movements_receipt', table_name='stock_movements')
    for name, kind in (
        ('ck_stock_movements_receipt_evidence', 'check'),
        ('fk_stock_movements_receipt_line_scope', 'foreignkey'),
        ('uq_stock_movements_receipt_line', 'unique'),
        ('ck_stock_movements_type', 'check'),
        ('ck_stock_movements_sign', 'check'),
    ):
        if _constraint('stock_movements', name, kind):
            op.drop_constraint(name, 'stock_movements', type_=kind)
    op.create_check_constraint('ck_stock_movements_type', 'stock_movements', "movement_type IN ('OPENING_BALANCE','MANUAL_IN','MANUAL_OUT','ADJUSTMENT','REVERSAL','CONSUMPTION')")
    op.create_check_constraint('ck_stock_movements_sign', 'stock_movements', "(movement_type IN ('OPENING_BALANCE','MANUAL_IN') AND quantity>0) OR (movement_type IN ('MANUAL_OUT','CONSUMPTION') AND quantity<0) OR (movement_type IN ('ADJUSTMENT','REVERSAL') AND quantity<>0)")
    for column in ('goods_receipt_line_id', 'goods_receipt_id'):
        if _column('stock_movements', column):
            op.drop_column('stock_movements', column)
    for table in ('goods_receipt_lines', 'goods_receipts', 'supplier_offerings', 'supplier_locations', 'suppliers'):
        if _table(table):
            op.drop_table(table)
    connection.execute(sa.text('DELETE rp FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id WHERE p.code IN :codes').bindparams(sa.bindparam('codes', expanding=True)), {'codes': tuple(PERMISSIONS)})
    connection.execute(sa.text('DELETE FROM permissions WHERE code IN :codes').bindparams(sa.bindparam('codes', expanding=True)), {'codes': tuple(PERMISSIONS)})
