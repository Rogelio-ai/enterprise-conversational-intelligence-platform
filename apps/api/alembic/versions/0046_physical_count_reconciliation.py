"""add physical count and reconciliation authority

Revision ID: 0046_physical_count_reconciliation
Revises: 0045_dedicated_inventory_loss
Create Date: 2026-09-12
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0046_physical_count_reconciliation'
down_revision: str | None = '0045_dedicated_inventory_loss'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
OPTIONS = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
PERMISSIONS = {
    'inventory.count.read': 'Read physical count evidence.',
    'inventory.count.manage': 'Open, count, submit and cancel physical counts.',
    'inventory.count.approve': 'Approve submitted physical counts.',
    'inventory.count.post': 'Post approved physical count adjustments.',
    'inventory.reconciliation.read': 'Read inventory reconciliation evidence.',
    'inventory.reconciliation.manage': 'Create and close inventory reconciliations.',
}


def _inspector():
    return sa.inspect(op.get_bind())


def _table(name):
    return name in _inspector().get_table_names()


def _column(table, name):
    return any(row['name'] == name for row in _inspector().get_columns(table))


def _constraint(table, name, kind):
    getter = {'foreignkey': _inspector().get_foreign_keys,
              'unique': _inspector().get_unique_constraints,
              'check': _inspector().get_check_constraints}[kind]
    return any(row['name'] == name for row in getter(table))


def _index(table, name):
    return any(row['name'] == name for row in _inspector().get_indexes(table))


def _seed_permissions():
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


def _create_counts():
    if not _table('physical_counts'):
        op.create_table(
            'physical_counts',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
            sa.Column('count_scope', sa.String(16), server_default=sa.text("'PARTIAL'"), nullable=False),
            sa.Column('status', sa.String(16), server_default=sa.text("'DRAFT'"), nullable=False),
            sa.Column('opened_at', sa.DateTime(), nullable=False),
            sa.Column('cursor_at', sa.DateTime(), nullable=False),
            sa.Column('cursor_movement_id', sa.BigInteger(), nullable=False),
            sa.Column('opened_by_actor_id', sa.BigInteger(), nullable=False),
            sa.Column('submitted_at', sa.DateTime()), sa.Column('submitted_by_actor_id', sa.BigInteger()),
            sa.Column('approved_at', sa.DateTime()), sa.Column('approved_by_actor_id', sa.BigInteger()),
            sa.Column('posted_at', sa.DateTime()), sa.Column('posted_by_actor_id', sa.BigInteger()),
            sa.Column('cancelled_at', sa.DateTime()), sa.Column('cancelled_by_actor_id', sa.BigInteger()),
            sa.Column('reason', sa.String(500)),
            sa.Column('reference', sa.String(200, collation='utf8mb4_bin')),
            sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
            sa.Column('post_actor_scope', sa.String(200, collation='ascii_bin')),
            sa.Column('post_idempotency_key', sa.String(128, collation='ascii_bin')),
            sa.Column('post_fingerprint', sa.String(64, collation='ascii_bin')),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.ForeignKeyConstraint(
                ['warehouse_id', 'tenant_id', 'organization_id', 'location_id'],
                ['warehouses.id', 'warehouses.tenant_id', 'warehouses.organization_id', 'warehouses.location_id'],
                name='fk_physical_counts_warehouse_scope', ondelete='RESTRICT'),
            sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id', name='uq_physical_counts_scope'),
            sa.UniqueConstraint('tenant_id', 'post_actor_scope', 'post_idempotency_key', name='uq_physical_counts_post_idempotency'),
            sa.CheckConstraint("count_scope='PARTIAL'", name='ck_physical_counts_scope'),
            sa.CheckConstraint("status IN ('DRAFT','COUNTING','SUBMITTED','APPROVED','POSTED','CANCELLED')", name='ck_physical_counts_status'),
            sa.CheckConstraint('version >= 1', name='ck_physical_counts_version'), **OPTIONS,
        )
        op.create_index('ix_physical_counts_location_status', 'physical_counts', ['tenant_id', 'location_id', 'status', 'id'])
    if not _table('physical_count_lines'):
        op.create_table(
            'physical_count_lines',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
            sa.Column('physical_count_id', sa.BigInteger(), nullable=False),
            sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
            sa.Column('expected_quantity_at_cursor', sa.Numeric(19, 6), nullable=False),
            sa.Column('source_quantity', sa.Numeric(19, 6), nullable=False),
            sa.Column('source_uom', sa.String(32, collation='ascii_bin'), nullable=False),
            sa.Column('conversion_revision_id', sa.BigInteger()),
            sa.Column('conversion_factor', sa.Numeric(25, 12), nullable=False),
            sa.Column('base_uom_evidence', sa.String(16), nullable=False),
            sa.Column('normalized_counted_quantity', sa.Numeric(19, 6), nullable=False),
            sa.Column('variance_quantity', sa.Numeric(19, 6), nullable=False),
            sa.Column('standard_cost_revision_id', sa.BigInteger()),
            sa.Column('standard_unit_cost_evidence', sa.Numeric(19, 6)),
            sa.Column('cost_currency_evidence', sa.String(3, collation='ascii_bin')),
            sa.Column('variance_value', sa.Numeric(31, 12)),
            sa.Column('evidence_status', sa.String(24), nullable=False),
            sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
            sa.Column('counted_by_actor_id', sa.BigInteger(), nullable=False),
            sa.Column('counted_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.ForeignKeyConstraint(
                ['physical_count_id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id'],
                ['physical_counts.id', 'physical_counts.tenant_id', 'physical_counts.organization_id', 'physical_counts.location_id', 'physical_counts.warehouse_id'],
                name='fk_physical_count_lines_count_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(
                ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
                ['inventory_items.id', 'inventory_items.tenant_id', 'inventory_items.organization_id', 'inventory_items.location_id'],
                name='fk_physical_count_lines_item_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(
                ['conversion_revision_id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'],
                ['item_uom_conversions.id', 'item_uom_conversions.tenant_id', 'item_uom_conversions.organization_id', 'item_uom_conversions.location_id', 'item_uom_conversions.inventory_item_id'],
                name='fk_physical_count_lines_conversion_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(
                ['standard_cost_revision_id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'],
                ['inventory_cost_revisions.id', 'inventory_cost_revisions.tenant_id', 'inventory_cost_revisions.organization_id', 'inventory_cost_revisions.location_id', 'inventory_cost_revisions.inventory_item_id'],
                name='fk_physical_count_lines_cost_scope', ondelete='RESTRICT'),
            sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id', 'physical_count_id', 'inventory_item_id', name='uq_physical_count_lines_scope'),
            sa.UniqueConstraint('physical_count_id', 'inventory_item_id', name='uq_physical_count_lines_item'),
            sa.CheckConstraint('source_quantity >= 0', name='ck_physical_count_lines_source'),
            sa.CheckConstraint('conversion_factor > 0', name='ck_physical_count_lines_factor'),
            sa.CheckConstraint("evidence_status IN ('RESOLVED','COST_NON_DERIVABLE')", name='ck_physical_count_lines_evidence_status'),
            sa.CheckConstraint('version >= 1', name='ck_physical_count_lines_version'), **OPTIONS,
        )


def _create_reconciliations():
    if _table('inventory_reconciliations'):
        return
    op.create_table(
        'inventory_reconciliations',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
        sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
        sa.Column('physical_count_id', sa.BigInteger(), nullable=False),
        sa.Column('physical_count_line_id', sa.BigInteger(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'OPEN'"), nullable=False),
        *[sa.Column(name, sa.Numeric(19, 6)) for name in (
            'opening_quantity', 'receiving_quantity', 'theoretical_consumption_quantity',
            'dedicated_loss_quantity', 'other_adjustment_quantity', 'physical_count_quantity',
            'count_adjustment_quantity', 'theoretical_closing_quantity', 'closing_quantity',
            'variance_quantity', 'variance_percentage')],
        sa.Column('standard_cost_revision_id', sa.BigInteger()),
        sa.Column('standard_unit_cost_evidence', sa.Numeric(19, 6)),
        sa.Column('cost_currency_evidence', sa.String(3, collation='ascii_bin')),
        sa.Column('variance_value', sa.Numeric(31, 12)),
        sa.Column('evidence_status', sa.String(24)),
        sa.Column('created_by_actor_id', sa.BigInteger(), nullable=False),
        sa.Column('closed_at', sa.DateTime()), sa.Column('closed_by_actor_id', sa.BigInteger()),
        sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(
            ['physical_count_line_id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id', 'physical_count_id', 'inventory_item_id'],
            ['physical_count_lines.id', 'physical_count_lines.tenant_id', 'physical_count_lines.organization_id', 'physical_count_lines.location_id', 'physical_count_lines.warehouse_id', 'physical_count_lines.physical_count_id', 'physical_count_lines.inventory_item_id'],
            name='fk_inventory_reconciliations_line_scope', ondelete='RESTRICT'),
        sa.UniqueConstraint('physical_count_line_id', name='uq_inventory_reconciliations_count_line'),
        sa.CheckConstraint("status IN ('OPEN','CLOSED')", name='ck_inventory_reconciliations_status'),
        sa.CheckConstraint('period_start < period_end', name='ck_inventory_reconciliations_period'),
        sa.CheckConstraint('version >= 1', name='ck_inventory_reconciliations_version'), **OPTIONS,
    )
    op.create_index('ix_inventory_reconciliations_location_status', 'inventory_reconciliations', ['tenant_id', 'location_id', 'status', 'id'])


def _extend_movements():
    if not _column('stock_movements', 'physical_count_id'):
        op.add_column('stock_movements', sa.Column('physical_count_id', sa.BigInteger()))
    if not _column('stock_movements', 'physical_count_line_id'):
        op.add_column('stock_movements', sa.Column('physical_count_line_id', sa.BigInteger()))
    if not _constraint('stock_movements', 'uq_stock_movements_count_line', 'unique'):
        op.create_unique_constraint('uq_stock_movements_count_line', 'stock_movements', ['physical_count_line_id'])
    if not _constraint('stock_movements', 'fk_stock_movements_count_line_scope', 'foreignkey'):
        if _index('stock_movements', 'fk_stock_movements_count_line_scope'):
            op.drop_index('fk_stock_movements_count_line_scope', table_name='stock_movements')
        op.create_foreign_key(
            'fk_stock_movements_count_line_scope', 'stock_movements', 'physical_count_lines',
            ['physical_count_line_id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id', 'physical_count_id', 'inventory_item_id'],
            ['id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id', 'physical_count_id', 'inventory_item_id'],
            ondelete='RESTRICT')
    if not _constraint('stock_movements', 'ck_stock_movements_count_evidence', 'check'):
        op.create_check_constraint(
            'ck_stock_movements_count_evidence', 'stock_movements',
            "(movement_type='ADJUSTMENT' AND ((physical_count_id IS NULL AND physical_count_line_id IS NULL) OR (physical_count_id IS NOT NULL AND physical_count_line_id IS NOT NULL))) OR (movement_type<>'ADJUSTMENT' AND physical_count_id IS NULL AND physical_count_line_id IS NULL)")
    if not _index('stock_movements', 'ix_stock_movements_count'):
        op.create_index('ix_stock_movements_count', 'stock_movements', ['tenant_id', 'physical_count_id', 'physical_count_line_id'])


def upgrade():
    _seed_permissions()
    _create_counts()
    _create_reconciliations()
    _extend_movements()


def downgrade():
    connection = op.get_bind()
    if _table('physical_counts') and connection.scalar(sa.text('SELECT COUNT(*) FROM physical_counts')):
        raise RuntimeError('Cannot downgrade 0046: physical count evidence exists')
    if _index('stock_movements', 'ix_stock_movements_count'):
        op.drop_index('ix_stock_movements_count', table_name='stock_movements')
    for name, kind in (
        ('ck_stock_movements_count_evidence', 'check'),
        ('fk_stock_movements_count_line_scope', 'foreignkey'),
        ('uq_stock_movements_count_line', 'unique'),
    ):
        if _constraint('stock_movements', name, kind):
            op.drop_constraint(name, 'stock_movements', type_=kind)
    for name in ('physical_count_line_id', 'physical_count_id'):
        if _column('stock_movements', name):
            op.drop_column('stock_movements', name)
    for table in ('inventory_reconciliations', 'physical_count_lines', 'physical_counts'):
        if _table(table):
            op.drop_table(table)
    connection.execute(sa.text(
        'DELETE rp FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id '
        'WHERE p.code IN :codes').bindparams(sa.bindparam('codes', expanding=True)),
        {'codes': tuple(PERMISSIONS)})
    connection.execute(sa.text('DELETE FROM permissions WHERE code IN :codes').bindparams(
        sa.bindparam('codes', expanding=True)), {'codes': tuple(PERMISSIONS)})
