"""add dedicated inventory loss authority

Revision ID: 0045_dedicated_inventory_loss
Revises: 0044_supplier_direct_receiving
Create Date: 2026-09-11
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0045_dedicated_inventory_loss'
down_revision: str | None = '0044_supplier_direct_receiving'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}
PERMISSIONS = {
    'inventory.loss.read': 'Read typed inventory loss evidence.',
    'inventory.loss.manage': 'Create, update, submit and cancel inventory losses.',
    'inventory.loss.approve': 'Configure policy, approve and reverse inventory losses.',
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


def _create_policies() -> None:
    if _table('inventory_loss_policies'):
        return
    op.create_table(
        'inventory_loss_policies',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
        sa.Column('approval_value_threshold', sa.Numeric(31, 12), nullable=False),
        sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['warehouse_id', 'tenant_id', 'organization_id', 'location_id'],
            ['warehouses.id', 'warehouses.tenant_id', 'warehouses.organization_id',
             'warehouses.location_id'],
            name='fk_inventory_loss_policies_warehouse_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('warehouse_id', name='uq_inventory_loss_policies_warehouse'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id',
            name='uq_inventory_loss_policies_scope',
        ),
        sa.CheckConstraint('approval_value_threshold >= 0', name='ck_inventory_loss_policies_threshold'),
        sa.CheckConstraint("currency REGEXP '^[A-Z][A-Z][A-Z]$'", name='ck_inventory_loss_policies_currency'),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_inventory_loss_policies_status'),
        sa.CheckConstraint('version >= 1', name='ck_inventory_loss_policies_version'),
        **OPTIONS,
    )


def _create_losses() -> None:
    if _table('inventory_losses'):
        return
    op.create_table(
        'inventory_losses',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
        sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
        sa.Column('category', sa.String(24), nullable=False),
        sa.Column('source_quantity', sa.Numeric(19, 6), nullable=False),
        sa.Column('source_uom', sa.String(32, collation='ascii_bin'), nullable=False),
        sa.Column('conversion_revision_id', sa.BigInteger(), nullable=True),
        sa.Column('conversion_factor', sa.Numeric(25, 12), nullable=True),
        sa.Column('base_uom_evidence', sa.String(16), nullable=True),
        sa.Column('normalized_quantity', sa.Numeric(19, 6), nullable=True),
        sa.Column('standard_cost_revision_id', sa.BigInteger(), nullable=True),
        sa.Column('standard_unit_cost_evidence', sa.Numeric(19, 6), nullable=True),
        sa.Column('cost_currency_evidence', sa.String(3, collation='ascii_bin'), nullable=True),
        sa.Column('extended_loss_cost', sa.Numeric(31, 12), nullable=True),
        sa.Column('evidence_status', sa.String(24), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_actor_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(24), server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
        sa.Column('approval_required', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('approval_reason', sa.String(32), nullable=True),
        sa.Column('approval_requested_at', sa.DateTime(), nullable=True),
        sa.Column('approval_requested_by_actor_id', sa.BigInteger(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by_actor_id', sa.BigInteger(), nullable=True),
        sa.Column('posted_at', sa.DateTime(), nullable=True),
        sa.Column('posted_by_actor_id', sa.BigInteger(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_by_actor_id', sa.BigInteger(), nullable=True),
        sa.Column('reversed_at', sa.DateTime(), nullable=True),
        sa.Column('reversed_by_actor_id', sa.BigInteger(), nullable=True),
        sa.Column('post_actor_scope', sa.String(200, collation='ascii_bin'), nullable=True),
        sa.Column('post_idempotency_key', sa.String(128, collation='ascii_bin'), nullable=True),
        sa.Column('post_fingerprint', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('approval_actor_scope', sa.String(200, collation='ascii_bin'), nullable=True),
        sa.Column('approval_idempotency_key', sa.String(128, collation='ascii_bin'), nullable=True),
        sa.Column('approval_fingerprint', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('reversal_actor_scope', sa.String(200, collation='ascii_bin'), nullable=True),
        sa.Column('reversal_idempotency_key', sa.String(128, collation='ascii_bin'), nullable=True),
        sa.Column('reversal_fingerprint', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['warehouse_id', 'tenant_id', 'organization_id', 'location_id'],
            ['warehouses.id', 'warehouses.tenant_id', 'warehouses.organization_id',
             'warehouses.location_id'],
            name='fk_inventory_losses_warehouse_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            ['inventory_items.id', 'inventory_items.tenant_id',
             'inventory_items.organization_id', 'inventory_items.location_id'],
            name='fk_inventory_losses_item_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['conversion_revision_id', 'tenant_id', 'organization_id', 'location_id',
             'inventory_item_id'],
            ['item_uom_conversions.id', 'item_uom_conversions.tenant_id',
             'item_uom_conversions.organization_id',
             'item_uom_conversions.location_id',
             'item_uom_conversions.inventory_item_id'],
            name='fk_inventory_losses_conversion_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['standard_cost_revision_id', 'tenant_id', 'organization_id',
             'location_id', 'inventory_item_id'],
            ['inventory_cost_revisions.id', 'inventory_cost_revisions.tenant_id',
             'inventory_cost_revisions.organization_id',
             'inventory_cost_revisions.location_id',
             'inventory_cost_revisions.inventory_item_id'],
            name='fk_inventory_losses_cost_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id',
            'inventory_item_id', name='uq_inventory_losses_scope',
        ),
        sa.UniqueConstraint('tenant_id', 'post_actor_scope', 'post_idempotency_key', name='uq_inventory_losses_post_idempotency'),
        sa.UniqueConstraint('tenant_id', 'approval_actor_scope', 'approval_idempotency_key', name='uq_inventory_losses_approval_idempotency'),
        sa.UniqueConstraint('tenant_id', 'reversal_actor_scope', 'reversal_idempotency_key', name='uq_inventory_losses_reversal_idempotency'),
        sa.CheckConstraint("category IN ('WASTE','SPOILAGE','BREAKAGE','EXPIRY','PREPARATION_LOSS','OTHER')", name='ck_inventory_losses_category'),
        sa.CheckConstraint("status IN ('DRAFT','PENDING_APPROVAL','POSTED','CANCELLED','REVERSED')", name='ck_inventory_losses_status'),
        sa.CheckConstraint('source_quantity > 0', name='ck_inventory_losses_quantity'),
        sa.CheckConstraint("source_uom REGEXP '^[A-Z][A-Z0-9_]{0,31}$'", name='ck_inventory_losses_source_uom'),
        sa.CheckConstraint("category<>'OTHER' OR reason IS NOT NULL", name='ck_inventory_losses_other_reason'),
        sa.CheckConstraint("evidence_status IN ('PENDING','RESOLVED','COST_NON_DERIVABLE')", name='ck_inventory_losses_evidence_status'),
        sa.CheckConstraint("(evidence_status='PENDING' AND conversion_factor IS NULL AND base_uom_evidence IS NULL AND normalized_quantity IS NULL AND standard_cost_revision_id IS NULL AND standard_unit_cost_evidence IS NULL AND cost_currency_evidence IS NULL AND extended_loss_cost IS NULL) OR (evidence_status='RESOLVED' AND conversion_factor>0 AND base_uom_evidence IS NOT NULL AND normalized_quantity>0 AND standard_cost_revision_id IS NOT NULL AND standard_unit_cost_evidence>=0 AND cost_currency_evidence IS NOT NULL AND extended_loss_cost>=0) OR (evidence_status='COST_NON_DERIVABLE' AND conversion_factor>0 AND base_uom_evidence IS NOT NULL AND normalized_quantity>0 AND standard_cost_revision_id IS NULL AND standard_unit_cost_evidence IS NULL AND cost_currency_evidence IS NULL AND extended_loss_cost IS NULL)", name='ck_inventory_losses_evidence'),
        sa.CheckConstraint('(approved_by_actor_id IS NULL OR approval_requested_by_actor_id IS NULL OR approved_by_actor_id<>approval_requested_by_actor_id)', name='ck_inventory_losses_separation'),
        sa.CheckConstraint("approval_reason IS NULL OR approval_reason IN ('BELOW_THRESHOLD','VALUE_THRESHOLD','COST_NON_DERIVABLE','CURRENCY_MISMATCH','NO_POLICY')", name='ck_inventory_losses_approval_reason'),
        sa.CheckConstraint("(status='DRAFT' AND evidence_status='PENDING' AND posted_at IS NULL AND cancelled_at IS NULL AND reversed_at IS NULL) OR (status='PENDING_APPROVAL' AND approval_required=1 AND evidence_status<>'PENDING' AND approval_requested_at IS NOT NULL AND approval_requested_by_actor_id IS NOT NULL AND post_actor_scope IS NOT NULL AND post_idempotency_key IS NOT NULL AND post_fingerprint IS NOT NULL AND posted_at IS NULL AND cancelled_at IS NULL AND reversed_at IS NULL) OR (status='POSTED' AND evidence_status<>'PENDING' AND posted_at IS NOT NULL AND posted_by_actor_id IS NOT NULL AND post_actor_scope IS NOT NULL AND post_idempotency_key IS NOT NULL AND post_fingerprint IS NOT NULL AND cancelled_at IS NULL AND reversed_at IS NULL AND (approval_required=0 OR (approved_at IS NOT NULL AND approved_by_actor_id IS NOT NULL))) OR (status='CANCELLED' AND cancelled_at IS NOT NULL AND cancelled_by_actor_id IS NOT NULL AND posted_at IS NULL AND reversed_at IS NULL) OR (status='REVERSED' AND evidence_status<>'PENDING' AND posted_at IS NOT NULL AND posted_by_actor_id IS NOT NULL AND reversed_at IS NOT NULL AND reversed_by_actor_id IS NOT NULL AND reversal_actor_scope IS NOT NULL AND reversal_idempotency_key IS NOT NULL AND reversal_fingerprint IS NOT NULL AND cancelled_at IS NULL)", name='ck_inventory_losses_lifecycle'),
        sa.CheckConstraint('version >= 1', name='ck_inventory_losses_version'),
        **OPTIONS,
    )
    op.create_index(
        'ix_inventory_losses_location_status', 'inventory_losses',
        ['tenant_id', 'location_id', 'status', 'id'],
    )


def _extend_movements() -> None:
    if not _column('stock_movements', 'inventory_loss_id'):
        op.add_column('stock_movements', sa.Column('inventory_loss_id', sa.BigInteger(), nullable=True))
    if not _column('stock_movements', 'loss_movement_role'):
        op.add_column('stock_movements', sa.Column('loss_movement_role', sa.String(16), nullable=True))
    for name in ('ck_stock_movements_type', 'ck_stock_movements_sign'):
        if _constraint('stock_movements', name, 'check'):
            op.drop_constraint(name, 'stock_movements', type_='check')
    op.create_check_constraint('ck_stock_movements_type', 'stock_movements', "movement_type IN ('OPENING_BALANCE','MANUAL_IN','MANUAL_OUT','ADJUSTMENT','REVERSAL','CONSUMPTION','GOODS_RECEIPT','WASTE')")
    op.create_check_constraint('ck_stock_movements_sign', 'stock_movements', "(movement_type IN ('OPENING_BALANCE','MANUAL_IN','GOODS_RECEIPT') AND quantity>0) OR (movement_type IN ('MANUAL_OUT','CONSUMPTION','WASTE') AND quantity<0) OR (movement_type IN ('ADJUSTMENT','REVERSAL') AND quantity<>0)")
    if not _constraint('stock_movements', 'uq_stock_movements_loss_role', 'unique'):
        op.create_unique_constraint('uq_stock_movements_loss_role', 'stock_movements', ['inventory_loss_id', 'loss_movement_role'])
    if not _constraint('stock_movements', 'fk_stock_movements_loss_scope', 'foreignkey'):
        if _index('stock_movements', 'fk_stock_movements_loss_scope'):
            op.drop_index('fk_stock_movements_loss_scope', table_name='stock_movements')
        op.create_foreign_key(
            'fk_stock_movements_loss_scope', 'stock_movements', 'inventory_losses',
            ['inventory_loss_id', 'tenant_id', 'organization_id', 'location_id',
             'warehouse_id', 'inventory_item_id'],
            ['id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id',
             'inventory_item_id'], ondelete='RESTRICT',
        )
    if not _constraint('stock_movements', 'ck_stock_movements_loss_evidence', 'check'):
        op.create_check_constraint(
            'ck_stock_movements_loss_evidence', 'stock_movements',
            "(movement_type='WASTE' AND inventory_loss_id IS NOT NULL AND loss_movement_role='ORIGINAL') OR (movement_type='REVERSAL' AND ((inventory_loss_id IS NULL AND loss_movement_role IS NULL) OR (inventory_loss_id IS NOT NULL AND loss_movement_role='REVERSAL'))) OR (movement_type NOT IN ('WASTE','REVERSAL') AND inventory_loss_id IS NULL AND loss_movement_role IS NULL)",
        )
    if not _index('stock_movements', 'ix_stock_movements_loss'):
        op.create_index(
            'ix_stock_movements_loss', 'stock_movements',
            ['tenant_id', 'inventory_loss_id', 'loss_movement_role'],
        )


def upgrade() -> None:
    _seed_permissions()
    _create_policies()
    _create_losses()
    _extend_movements()


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(sa.text(
        "SELECT COUNT(*) FROM stock_movements WHERE movement_type='WASTE'"
    )):
        raise RuntimeError('Cannot downgrade 0045: posted InventoryLoss history exists')
    if _index('stock_movements', 'ix_stock_movements_loss'):
        op.drop_index('ix_stock_movements_loss', table_name='stock_movements')
    for name, kind in (
        ('ck_stock_movements_loss_evidence', 'check'),
        ('fk_stock_movements_loss_scope', 'foreignkey'),
        ('uq_stock_movements_loss_role', 'unique'),
        ('ck_stock_movements_type', 'check'),
        ('ck_stock_movements_sign', 'check'),
    ):
        if _constraint('stock_movements', name, kind):
            op.drop_constraint(name, 'stock_movements', type_=kind)
    op.create_check_constraint('ck_stock_movements_type', 'stock_movements', "movement_type IN ('OPENING_BALANCE','MANUAL_IN','MANUAL_OUT','ADJUSTMENT','REVERSAL','CONSUMPTION','GOODS_RECEIPT')")
    op.create_check_constraint('ck_stock_movements_sign', 'stock_movements', "(movement_type IN ('OPENING_BALANCE','MANUAL_IN','GOODS_RECEIPT') AND quantity>0) OR (movement_type IN ('MANUAL_OUT','CONSUMPTION') AND quantity<0) OR (movement_type IN ('ADJUSTMENT','REVERSAL') AND quantity<>0)")
    for column in ('loss_movement_role', 'inventory_loss_id'):
        if _column('stock_movements', column):
            op.drop_column('stock_movements', column)
    for table in ('inventory_losses', 'inventory_loss_policies'):
        if _table(table):
            op.drop_table(table)
    connection.execute(sa.text(
        'DELETE rp FROM role_permissions rp JOIN permissions p '
        'ON p.id=rp.permission_id WHERE p.code IN :codes'
    ).bindparams(sa.bindparam('codes', expanding=True)), {'codes': tuple(PERMISSIONS)})
    connection.execute(sa.text(
        'DELETE FROM permissions WHERE code IN :codes'
    ).bindparams(sa.bindparam('codes', expanding=True)), {'codes': tuple(PERMISSIONS)})
