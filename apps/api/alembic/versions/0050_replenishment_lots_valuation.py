"""add replenishment policy, lot provenance, and valuation snapshots

Revision ID: 0050_replenishment_lots_valuation
Revises: 0049_prepared_components_yield
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0050_replenishment_lots_valuation'
down_revision: str | None = '0049_prepared_components_yield'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
OPTIONS = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
PERMISSIONS = {
    'inventory.replenishment.read': 'Read replenishment policy and suggestions.',
    'inventory.replenishment.manage': 'Manage replenishment policy.',
    'inventory.lot.read': 'Read inventory lot traceability.',
    'inventory.valuation.read': 'Read inventory valuation snapshots.',
    'inventory.valuation.create': 'Create immutable inventory valuation snapshots.',
}


def _inspector():
    return sa.inspect(op.get_bind())


def _table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _column(table: str, name: str) -> bool:
    return any(value['name'] == name for value in _inspector().get_columns(table))


def _constraint(table: str, name: str, kind: str) -> bool:
    getter = {
        'check': _inspector().get_check_constraints,
        'foreignkey': _inspector().get_foreign_keys,
        'unique': _inspector().get_unique_constraints,
    }[kind]
    return any(value['name'] == name for value in getter(table))


def _seed_permissions() -> None:
    connection = op.get_bind()
    for code, description in PERMISSIONS.items():
        connection.execute(sa.text('INSERT INTO permissions (code,description) SELECT :code,:description WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code=:code)'), {'code': code, 'description': description})
        connection.execute(sa.text("INSERT INTO role_permissions (role_id,permission_id) SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code=:code WHERE r.name='TENANT_ADMIN' AND r.status='ACTIVE' AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id=r.id AND rp.permission_id=p.id)"), {'code': code})


def upgrade() -> None:
    if not _column('inventory_items', 'lot_tracking_policy'):
        op.add_column('inventory_items', sa.Column('lot_tracking_policy', sa.String(16), server_default=sa.text("'OPTIONAL'"), nullable=False))
    if not _column('inventory_items', 'date_tracking_policy'):
        op.add_column('inventory_items', sa.Column('date_tracking_policy', sa.String(16), server_default=sa.text("'NONE'"), nullable=False))
    if not _constraint('inventory_items', 'ck_inventory_items_lot_tracking_policy', 'check'):
        op.create_check_constraint('ck_inventory_items_lot_tracking_policy', 'inventory_items', "lot_tracking_policy IN ('OPTIONAL','REQUIRED')")
    if not _constraint('inventory_items', 'ck_inventory_items_date_tracking_policy', 'check'):
        op.create_check_constraint('ck_inventory_items_date_tracking_policy', 'inventory_items', "date_tracking_policy IN ('NONE','EXPIRY','BEST_BEFORE','BOTH')")
    for table in ('goods_receipt_lines', 'preparation_batch_outputs'):
        if not _column(table, 'lot_code'):
            op.add_column(table, sa.Column('lot_code', sa.String(100, collation='utf8mb4_bin')))
        for name in ('manufacture_date', 'expiry_date', 'best_before_date'):
            if not _column(table, name):
                op.add_column(table, sa.Column(name, sa.Date()))

    if not _table('replenishment_policies'):
        op.create_table(
            'replenishment_policies',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
            sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
            sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
            sa.Column('minimum_quantity', sa.Numeric(19, 6)),
            sa.Column('target_quantity', sa.Numeric(19, 6)),
            sa.Column('source_uom', sa.String(32, collation='ascii_bin'), nullable=False),
            sa.Column('conversion_revision_id', sa.BigInteger()),
            sa.Column('conversion_factor', sa.Numeric(25, 12), nullable=False),
            sa.Column('base_uom_evidence', sa.String(16), nullable=False),
            sa.Column('normalized_minimum_quantity', sa.Numeric(19, 6)),
            sa.Column('normalized_target_quantity', sa.Numeric(19, 6)),
            sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
            sa.Column('actor_id', sa.BigInteger(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.ForeignKeyConstraint(['warehouse_id','tenant_id','organization_id','location_id'], ['warehouses.id','warehouses.tenant_id','warehouses.organization_id','warehouses.location_id'], name='fk_replenishment_policies_warehouse_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['inventory_item_id','tenant_id','organization_id','location_id'], ['inventory_items.id','inventory_items.tenant_id','inventory_items.organization_id','inventory_items.location_id'], name='fk_replenishment_policies_item_scope', ondelete='RESTRICT'),
            sa.UniqueConstraint('warehouse_id','inventory_item_id', name='uq_replenishment_policies_item'),
            sa.UniqueConstraint('id','tenant_id','organization_id','location_id','warehouse_id','inventory_item_id', name='uq_replenishment_policies_scope'),
            sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_replenishment_policies_status'),
            sa.CheckConstraint('version >= 1', name='ck_replenishment_policies_version'),
            sa.CheckConstraint('(minimum_quantity IS NULL OR minimum_quantity >= 0) AND (target_quantity IS NULL OR target_quantity >= 0) AND (normalized_minimum_quantity IS NULL OR normalized_minimum_quantity >= 0) AND (normalized_target_quantity IS NULL OR normalized_target_quantity >= 0) AND conversion_factor > 0', name='ck_replenishment_policies_values'),
            sa.CheckConstraint('target_quantity IS NOT NULL OR minimum_quantity IS NOT NULL', name='ck_replenishment_policies_configured'),
            sa.CheckConstraint('target_quantity IS NULL OR minimum_quantity IS NULL OR target_quantity >= minimum_quantity', name='ck_replenishment_policies_order'),
            **OPTIONS,
        )
        op.create_index('ix_replenishment_policies_location_status', 'replenishment_policies', ['tenant_id','location_id','status','inventory_item_id'])

    if not _table('inventory_lots'):
        op.create_table(
            'inventory_lots',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
            sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
            sa.Column('origin_type', sa.String(24), nullable=False),
            sa.Column('goods_receipt_line_id', sa.BigInteger()),
            sa.Column('preparation_batch_output_id', sa.BigInteger()),
            sa.Column('lot_code', sa.String(100, collation='utf8mb4_bin'), nullable=False),
            sa.Column('origin_at', sa.DateTime(), nullable=False),
            sa.Column('manufacture_date', sa.Date()),
            sa.Column('expiry_date', sa.Date()),
            sa.Column('best_before_date', sa.Date()),
            sa.Column('original_quantity', sa.Numeric(19, 6), nullable=False),
            sa.Column('source_quantity', sa.Numeric(19, 6), nullable=False),
            sa.Column('source_uom', sa.String(32, collation='ascii_bin'), nullable=False),
            sa.Column('conversion_revision_id', sa.BigInteger()),
            sa.Column('conversion_factor', sa.Numeric(25, 12), nullable=False),
            sa.Column('base_uom_evidence', sa.String(16), nullable=False),
            sa.Column('cost_evidence_status', sa.String(24), nullable=False),
            sa.Column('unit_cost_evidence', sa.Numeric(31, 12)),
            sa.Column('cost_currency_evidence', sa.String(3, collation='ascii_bin')),
            sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.ForeignKeyConstraint(['warehouse_id','tenant_id','organization_id','location_id'], ['warehouses.id','warehouses.tenant_id','warehouses.organization_id','warehouses.location_id'], name='fk_inventory_lots_warehouse_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['inventory_item_id','tenant_id','organization_id','location_id'], ['inventory_items.id','inventory_items.tenant_id','inventory_items.organization_id','inventory_items.location_id'], name='fk_inventory_lots_item_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['goods_receipt_line_id'], ['goods_receipt_lines.id'], name='fk_inventory_lots_receipt_line', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['preparation_batch_output_id'], ['preparation_batch_outputs.id'], name='fk_inventory_lots_preparation_output', ondelete='RESTRICT'),
            sa.UniqueConstraint('id','tenant_id','organization_id','location_id','warehouse_id','inventory_item_id', name='uq_inventory_lots_scope'),
            sa.UniqueConstraint('tenant_id','warehouse_id','inventory_item_id','lot_code', name='uq_inventory_lots_code'),
            sa.UniqueConstraint('goods_receipt_line_id', name='uq_inventory_lots_receipt_line'),
            sa.UniqueConstraint('preparation_batch_output_id', name='uq_inventory_lots_preparation_output'),
            sa.CheckConstraint("origin_type IN ('GOODS_RECEIPT','PREPARATION_BATCH')", name='ck_inventory_lots_origin'),
            sa.CheckConstraint("status IN ('ACTIVE','CLOSED')", name='ck_inventory_lots_status'),
            sa.CheckConstraint('original_quantity > 0 AND source_quantity > 0 AND conversion_factor > 0', name='ck_inventory_lots_quantities'),
            sa.CheckConstraint("cost_evidence_status IN ('RESOLVED','COST_NON_DERIVABLE')", name='ck_inventory_lots_cost_status'),
            sa.CheckConstraint("(origin_type='GOODS_RECEIPT' AND goods_receipt_line_id IS NOT NULL AND preparation_batch_output_id IS NULL) OR (origin_type='PREPARATION_BATCH' AND preparation_batch_output_id IS NOT NULL AND goods_receipt_line_id IS NULL)", name='ck_inventory_lots_origin_evidence'),
            sa.CheckConstraint("(cost_evidence_status='RESOLVED' AND unit_cost_evidence IS NOT NULL AND cost_currency_evidence IS NOT NULL) OR (cost_evidence_status='COST_NON_DERIVABLE' AND unit_cost_evidence IS NULL AND cost_currency_evidence IS NULL)", name='ck_inventory_lots_cost_evidence'),
            **OPTIONS,
        )
        op.create_index('ix_inventory_lots_location_item', 'inventory_lots', ['tenant_id','location_id','inventory_item_id','origin_at','id'])

    if not _column('stock_movements', 'inventory_lot_id'):
        op.add_column('stock_movements', sa.Column('inventory_lot_id', sa.BigInteger()))
    if not _constraint('stock_movements', 'fk_stock_movements_lot_scope', 'foreignkey'):
        op.create_foreign_key('fk_stock_movements_lot_scope', 'stock_movements', 'inventory_lots', ['inventory_lot_id','tenant_id','organization_id','location_id','warehouse_id','inventory_item_id'], ['id','tenant_id','organization_id','location_id','warehouse_id','inventory_item_id'], ondelete='RESTRICT')
    if not any(value['name'] == 'ix_stock_movements_lot' for value in _inspector().get_indexes('stock_movements')):
        op.create_index('ix_stock_movements_lot', 'stock_movements', ['tenant_id','inventory_lot_id','recorded_at','id'])

    if not _table('inventory_valuation_snapshots'):
        op.create_table(
            'inventory_valuation_snapshots',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
            sa.Column('status', sa.String(16), server_default=sa.text("'FINALIZED'"), nullable=False),
            sa.Column('valuation_method', sa.String(24), server_default=sa.text("'STANDARD_COST'"), nullable=False),
            sa.Column('as_of', sa.DateTime(), nullable=False),
            sa.Column('movement_cursor', sa.BigInteger(), nullable=False),
            sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
            sa.Column('derivable_total_value', sa.Numeric(31, 12), nullable=False),
            sa.Column('non_derivable_line_count', sa.Integer(), nullable=False),
            sa.Column('created_by_actor_id', sa.BigInteger(), nullable=False),
            sa.Column('idempotency_actor_scope', sa.String(200, collation='ascii_bin'), nullable=False),
            sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
            sa.Column('request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.ForeignKeyConstraint(['warehouse_id','tenant_id','organization_id','location_id'], ['warehouses.id','warehouses.tenant_id','warehouses.organization_id','warehouses.location_id'], name='fk_inventory_valuation_snapshots_warehouse_scope', ondelete='RESTRICT'),
            sa.UniqueConstraint('id','tenant_id','organization_id','location_id','warehouse_id', name='uq_inventory_valuation_snapshots_scope'),
            sa.UniqueConstraint('tenant_id','idempotency_actor_scope','idempotency_key', name='uq_inventory_valuation_snapshots_idempotency'),
            sa.CheckConstraint("status='FINALIZED' AND valuation_method='STANDARD_COST'", name='ck_inventory_valuation_snapshots_authority'),
            sa.CheckConstraint('movement_cursor >= 0 AND non_derivable_line_count >= 0', name='ck_inventory_valuation_snapshots_values'),
            sa.CheckConstraint("currency REGEXP '^[A-Z][A-Z][A-Z]$'", name='ck_inventory_valuation_snapshots_currency'),
            **OPTIONS,
        )
        op.create_index('ix_inventory_valuation_snapshots_location', 'inventory_valuation_snapshots', ['tenant_id','location_id','as_of','id'])

    if not _table('inventory_valuation_snapshot_lines'):
        op.create_table(
            'inventory_valuation_snapshot_lines',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('warehouse_id', sa.BigInteger(), nullable=False),
            sa.Column('snapshot_id', sa.BigInteger(), nullable=False),
            sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
            sa.Column('quantity_as_of', sa.Numeric(19, 6), nullable=False),
            sa.Column('cost_revision_id', sa.BigInteger()),
            sa.Column('unit_cost_evidence', sa.Numeric(19, 6)),
            sa.Column('cost_currency_evidence', sa.String(3, collation='ascii_bin')),
            sa.Column('line_value', sa.Numeric(31, 12)),
            sa.Column('evidence_status', sa.String(24), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.ForeignKeyConstraint(['snapshot_id','tenant_id','organization_id','location_id','warehouse_id'], ['inventory_valuation_snapshots.id','inventory_valuation_snapshots.tenant_id','inventory_valuation_snapshots.organization_id','inventory_valuation_snapshots.location_id','inventory_valuation_snapshots.warehouse_id'], name='fk_inventory_valuation_lines_snapshot_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['inventory_item_id','tenant_id','organization_id','location_id'], ['inventory_items.id','inventory_items.tenant_id','inventory_items.organization_id','inventory_items.location_id'], name='fk_inventory_valuation_lines_item_scope', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['cost_revision_id'], ['inventory_cost_revisions.id'], name='fk_inventory_valuation_lines_cost_revision', ondelete='RESTRICT'),
            sa.UniqueConstraint('snapshot_id','inventory_item_id', name='uq_inventory_valuation_lines_item'),
            sa.CheckConstraint("evidence_status IN ('RESOLVED','COST_NON_DERIVABLE','CURRENCY_MISMATCH')", name='ck_inventory_valuation_lines_status'),
            sa.CheckConstraint("(evidence_status='RESOLVED' AND cost_revision_id IS NOT NULL AND unit_cost_evidence IS NOT NULL AND cost_currency_evidence IS NOT NULL AND line_value IS NOT NULL) OR (evidence_status='COST_NON_DERIVABLE' AND cost_revision_id IS NULL AND unit_cost_evidence IS NULL AND cost_currency_evidence IS NULL AND line_value IS NULL) OR (evidence_status='CURRENCY_MISMATCH' AND cost_revision_id IS NOT NULL AND unit_cost_evidence IS NOT NULL AND cost_currency_evidence IS NOT NULL AND line_value IS NULL)", name='ck_inventory_valuation_lines_evidence'),
            **OPTIONS,
        )
    _seed_permissions()


def downgrade() -> None:
    connection = op.get_bind()
    for table in ('inventory_valuation_snapshot_lines','inventory_valuation_snapshots','inventory_lots','replenishment_policies'):
        if _table(table):
            count = connection.execute(sa.text(f'SELECT COUNT(*) FROM {table}')).scalar_one()
            if count:
                raise RuntimeError('Cannot downgrade 0050: B10 authority evidence exists')
    if _column('stock_movements', 'inventory_lot_id'):
        count = connection.execute(sa.text('SELECT COUNT(*) FROM stock_movements WHERE inventory_lot_id IS NOT NULL')).scalar_one()
        if count:
            raise RuntimeError('Cannot downgrade 0050: lot movement provenance exists')
        if any(value['name'] == 'ix_stock_movements_lot' for value in _inspector().get_indexes('stock_movements')):
            op.drop_index('ix_stock_movements_lot', table_name='stock_movements')
        if _constraint('stock_movements', 'fk_stock_movements_lot_scope', 'foreignkey'):
            op.drop_constraint('fk_stock_movements_lot_scope', 'stock_movements', type_='foreignkey')
        if any(value['name'] == 'fk_stock_movements_lot_scope' for value in _inspector().get_indexes('stock_movements')):
            op.drop_index('fk_stock_movements_lot_scope', table_name='stock_movements')
        op.drop_column('stock_movements', 'inventory_lot_id')
    for table in ('inventory_valuation_snapshot_lines','inventory_valuation_snapshots','inventory_lots','replenishment_policies'):
        if _table(table):
            op.drop_table(table)
    for table in ('goods_receipt_lines', 'preparation_batch_outputs'):
        for name in ('best_before_date','expiry_date','manufacture_date','lot_code'):
            if _column(table, name):
                op.drop_column(table, name)
    for name in ('ck_inventory_items_date_tracking_policy','ck_inventory_items_lot_tracking_policy'):
        if _constraint('inventory_items', name, 'check'):
            op.drop_constraint(name, 'inventory_items', type_='check')
    for name in ('date_tracking_policy','lot_tracking_policy'):
        if _column('inventory_items', name):
            op.drop_column('inventory_items', name)
    connection.execute(sa.text('DELETE rp FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id WHERE p.code IN :codes').bindparams(sa.bindparam('codes', expanding=True)), {'codes': tuple(PERMISSIONS)})
    connection.execute(sa.text('DELETE FROM permissions WHERE code IN :codes').bindparams(sa.bindparam('codes', expanding=True)), {'codes': tuple(PERMISSIONS)})
