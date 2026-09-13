"""add prepared component recipes, batches, yield, and ledger provenance

Revision ID: 0049_prepared_components_yield
Revises: 0048_purchase_order_operations
Create Date: 2026-09-12
"""
from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0049_prepared_components_yield'
down_revision: str | None = '0048_purchase_order_operations'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
OPTIONS = {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
PERMISSIONS = {
    'inventory.preparation.read': 'Read preparation recipes and batches.',
    'inventory.preparation.manage': 'Manage preparation recipes and batches.',
    'inventory.preparation.complete': 'Complete preparation batches.',
}


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _column(table: str, name: str) -> bool:
    return any(row['name'] == name for row in _inspector().get_columns(table))


def _constraint(table: str, name: str, kind: str) -> bool:
    getter = {'foreignkey': _inspector().get_foreign_keys, 'unique': _inspector().get_unique_constraints, 'check': _inspector().get_check_constraints}[kind]
    return any(row['name'] == name for row in getter(table))


def _index(table: str, name: str) -> bool:
    return any(row['name'] == name for row in _inspector().get_indexes(table))


def _seed_permissions() -> None:
    connection = op.get_bind()
    for code, description in PERMISSIONS.items():
        connection.execute(sa.text('INSERT INTO permissions (code,description) SELECT :code,:description WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code=:code)'), {'code': code, 'description': description})
        connection.execute(sa.text("INSERT INTO role_permissions (role_id,permission_id) SELECT r.id,p.id FROM roles r JOIN permissions p ON p.code=:code WHERE r.name='TENANT_ADMIN' AND r.status='ACTIVE' AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id=r.id AND rp.permission_id=p.id)"), {'code': code})


def _create_tables() -> None:
    if not _table('preparation_recipe_versions'):
        op.create_table('preparation_recipe_versions',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True), sa.Column('tenant_id', sa.BigInteger(), nullable=False), sa.Column('organization_id', sa.BigInteger(), nullable=False), sa.Column('location_id', sa.BigInteger(), nullable=False), sa.Column('output_inventory_item_id', sa.BigInteger(), nullable=False), sa.Column('revision', sa.BigInteger(), nullable=False), sa.Column('status', sa.String(16), nullable=False), sa.Column('publication_status', sa.String(16), server_default=sa.text("'PUBLISHED'"), nullable=False), sa.Column('expected_output_quantity', sa.Numeric(19,6), nullable=False), sa.Column('output_source_uom', sa.String(32, collation='ascii_bin'), nullable=False), sa.Column('output_conversion_revision_id', sa.BigInteger()), sa.Column('output_conversion_factor', sa.Numeric(25,12), nullable=False), sa.Column('output_base_uom_evidence', sa.String(16), nullable=False), sa.Column('normalized_expected_output_quantity', sa.Numeric(19,6), nullable=False), sa.Column('effective_from', sa.DateTime(), nullable=False), sa.Column('effective_to', sa.DateTime()), sa.Column('actor_id', sa.BigInteger(), nullable=False), sa.Column('source', sa.String(48, collation='ascii_bin'), nullable=False), sa.Column('published_at', sa.DateTime(), nullable=False), sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.ForeignKeyConstraint(['output_inventory_item_id','tenant_id','organization_id','location_id'], ['inventory_items.id','inventory_items.tenant_id','inventory_items.organization_id','inventory_items.location_id'], name='fk_preparation_recipe_versions_output_scope', ondelete='RESTRICT'), sa.UniqueConstraint('id','tenant_id','organization_id','location_id', name='uq_preparation_recipe_versions_scope'), sa.UniqueConstraint('tenant_id','location_id','output_inventory_item_id','revision', name='uq_preparation_recipe_versions_revision'), sa.CheckConstraint('revision >= 1 AND expected_output_quantity > 0 AND normalized_expected_output_quantity > 0 AND output_conversion_factor > 0', name='ck_preparation_recipe_versions_values'), sa.CheckConstraint("status IN ('ACTIVE','INACTIVE') AND publication_status='PUBLISHED'", name='ck_preparation_recipe_versions_status'), sa.CheckConstraint('effective_to IS NULL OR effective_to >= effective_from', name='ck_preparation_recipe_versions_effectivity'), **OPTIONS)
        op.create_index('ix_preparation_recipe_versions_resolve','preparation_recipe_versions',['tenant_id','location_id','output_inventory_item_id','effective_from','revision'])
    if not _table('preparation_recipe_components'):
        op.create_table('preparation_recipe_components',
            sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column('tenant_id',sa.BigInteger(),nullable=False),sa.Column('organization_id',sa.BigInteger(),nullable=False),sa.Column('location_id',sa.BigInteger(),nullable=False),sa.Column('recipe_version_id',sa.BigInteger(),nullable=False),sa.Column('inventory_item_id',sa.BigInteger(),nullable=False),sa.Column('line_number',sa.Integer(),nullable=False),sa.Column('expected_quantity',sa.Numeric(19,6),nullable=False),sa.Column('source_uom',sa.String(32,collation='ascii_bin'),nullable=False),sa.Column('conversion_revision_id',sa.BigInteger()),sa.Column('conversion_factor',sa.Numeric(25,12),nullable=False),sa.Column('base_uom_evidence',sa.String(16),nullable=False),sa.Column('normalized_expected_quantity',sa.Numeric(19,6),nullable=False),sa.Column('yield_basis_slot',sa.SmallInteger()),sa.Column('created_at',sa.DateTime(),server_default=sa.func.current_timestamp(),nullable=False),
            sa.ForeignKeyConstraint(['recipe_version_id','tenant_id','organization_id','location_id'],['preparation_recipe_versions.id','preparation_recipe_versions.tenant_id','preparation_recipe_versions.organization_id','preparation_recipe_versions.location_id'],name='fk_preparation_recipe_components_version_scope',ondelete='RESTRICT'),sa.ForeignKeyConstraint(['inventory_item_id','tenant_id','organization_id','location_id'],['inventory_items.id','inventory_items.tenant_id','inventory_items.organization_id','inventory_items.location_id'],name='fk_preparation_recipe_components_item_scope',ondelete='RESTRICT'),sa.UniqueConstraint('id','recipe_version_id','inventory_item_id',name='uq_preparation_recipe_components_batch_scope'),sa.UniqueConstraint('recipe_version_id','inventory_item_id',name='uq_preparation_recipe_components_item'),sa.UniqueConstraint('recipe_version_id','yield_basis_slot',name='uq_preparation_recipe_components_yield_basis'),sa.CheckConstraint('expected_quantity > 0 AND normalized_expected_quantity > 0 AND conversion_factor > 0',name='ck_preparation_recipe_components_values'),sa.CheckConstraint('yield_basis_slot IS NULL OR yield_basis_slot=1',name='ck_preparation_recipe_components_yield_basis'),**OPTIONS)
    if not _table('preparation_batches'):
        op.create_table('preparation_batches',
            sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column('tenant_id',sa.BigInteger(),nullable=False),sa.Column('organization_id',sa.BigInteger(),nullable=False),sa.Column('location_id',sa.BigInteger(),nullable=False),sa.Column('warehouse_id',sa.BigInteger(),nullable=False),sa.Column('recipe_version_id',sa.BigInteger(),nullable=False),sa.Column('status',sa.String(16),server_default=sa.text("'DRAFT'"),nullable=False),sa.Column('version',sa.BigInteger(),server_default=sa.text('1'),nullable=False),sa.Column('expected_yield',sa.Numeric(25,12),nullable=False),sa.Column('actual_yield',sa.Numeric(25,12),nullable=False),sa.Column('yield_variance',sa.Numeric(25,12),nullable=False),sa.Column('cost_evidence_status',sa.String(24),nullable=False),sa.Column('material_cost',sa.Numeric(31,12)),sa.Column('prepared_unit_material_cost',sa.Numeric(31,12)),sa.Column('cost_currency_evidence',sa.String(3,collation='ascii_bin')),sa.Column('reference',sa.String(200)),sa.Column('created_by_actor_id',sa.BigInteger(),nullable=False),sa.Column('started_at',sa.DateTime()),sa.Column('started_by_actor_id',sa.BigInteger()),sa.Column('completed_at',sa.DateTime()),sa.Column('completed_by_actor_id',sa.BigInteger()),sa.Column('cancelled_at',sa.DateTime()),sa.Column('cancelled_by_actor_id',sa.BigInteger()),sa.Column('completion_command_key',sa.String(128,collation='ascii_bin')),sa.Column('completion_fingerprint',sa.String(64,collation='ascii_bin')),sa.Column('created_at',sa.DateTime(),server_default=sa.func.current_timestamp(),nullable=False),sa.Column('updated_at',sa.DateTime(),server_default=sa.func.current_timestamp(),nullable=False),
            sa.ForeignKeyConstraint(['warehouse_id','tenant_id','organization_id','location_id'],['warehouses.id','warehouses.tenant_id','warehouses.organization_id','warehouses.location_id'],name='fk_preparation_batches_warehouse_scope',ondelete='RESTRICT'),sa.ForeignKeyConstraint(['recipe_version_id','tenant_id','organization_id','location_id'],['preparation_recipe_versions.id','preparation_recipe_versions.tenant_id','preparation_recipe_versions.organization_id','preparation_recipe_versions.location_id'],name='fk_preparation_batches_recipe_scope',ondelete='RESTRICT'),sa.UniqueConstraint('id','tenant_id','organization_id','location_id','warehouse_id',name='uq_preparation_batches_scope'),sa.CheckConstraint("status IN ('DRAFT','IN_PROGRESS','COMPLETED','CANCELLED')",name='ck_preparation_batches_status'),sa.CheckConstraint("cost_evidence_status IN ('RESOLVED','COST_NON_DERIVABLE')",name='ck_preparation_batches_cost_status'),sa.CheckConstraint('version >= 1 AND expected_yield > 0 AND actual_yield > 0',name='ck_preparation_batches_values'),sa.CheckConstraint("(cost_evidence_status='RESOLVED' AND material_cost IS NOT NULL AND prepared_unit_material_cost IS NOT NULL AND cost_currency_evidence IS NOT NULL) OR (cost_evidence_status='COST_NON_DERIVABLE' AND material_cost IS NULL AND prepared_unit_material_cost IS NULL AND cost_currency_evidence IS NULL)",name='ck_preparation_batches_cost_evidence'),**OPTIONS)
        op.create_index('ix_preparation_batches_location_status','preparation_batches',['tenant_id','location_id','status','id'])
    else:
        scope = next((row for row in _inspector().get_unique_constraints('preparation_batches') if row['name'] == 'uq_preparation_batches_scope'), None)
        expected_scope = ['id','tenant_id','organization_id','location_id','warehouse_id']
        if scope is not None and scope['column_names'] != expected_scope:
            op.drop_constraint('uq_preparation_batches_scope','preparation_batches',type_='unique')
            scope = None
        if scope is None:
            op.create_unique_constraint('uq_preparation_batches_scope','preparation_batches',expected_scope)
    if not _table('preparation_batch_inputs'):
        op.create_table('preparation_batch_inputs',
            sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column('tenant_id',sa.BigInteger(),nullable=False),sa.Column('organization_id',sa.BigInteger(),nullable=False),sa.Column('location_id',sa.BigInteger(),nullable=False),sa.Column('warehouse_id',sa.BigInteger(),nullable=False),sa.Column('batch_id',sa.BigInteger(),nullable=False),sa.Column('recipe_version_id',sa.BigInteger(),nullable=False),sa.Column('recipe_component_id',sa.BigInteger(),nullable=False),sa.Column('inventory_item_id',sa.BigInteger(),nullable=False),sa.Column('line_number',sa.Integer(),nullable=False),sa.Column('source_quantity',sa.Numeric(19,6),nullable=False),sa.Column('source_uom',sa.String(32,collation='ascii_bin'),nullable=False),sa.Column('normalized_quantity',sa.Numeric(19,6),nullable=False),sa.Column('conversion_revision_id',sa.BigInteger()),sa.Column('conversion_factor',sa.Numeric(25,12),nullable=False),sa.Column('base_uom_evidence',sa.String(16),nullable=False),sa.Column('standard_cost_revision_id',sa.BigInteger()),sa.Column('standard_unit_cost_evidence',sa.Numeric(19,6)),sa.Column('cost_currency_evidence',sa.String(3,collation='ascii_bin')),sa.Column('extended_material_cost',sa.Numeric(31,12)),sa.Column('evidence_status',sa.String(24),nullable=False),sa.Column('created_at',sa.DateTime(),server_default=sa.func.current_timestamp(),nullable=False),
            sa.ForeignKeyConstraint(['batch_id','tenant_id','organization_id','location_id','warehouse_id'],['preparation_batches.id','preparation_batches.tenant_id','preparation_batches.organization_id','preparation_batches.location_id','preparation_batches.warehouse_id'],name='fk_preparation_batch_inputs_batch_scope',ondelete='RESTRICT'),sa.ForeignKeyConstraint(['recipe_component_id','recipe_version_id','inventory_item_id'],['preparation_recipe_components.id','preparation_recipe_components.recipe_version_id','preparation_recipe_components.inventory_item_id'],name='fk_preparation_batch_inputs_component_scope',ondelete='RESTRICT'),sa.UniqueConstraint('id','batch_id','inventory_item_id',name='uq_preparation_batch_inputs_movement_scope'),sa.UniqueConstraint('batch_id','recipe_component_id',name='uq_preparation_batch_inputs_component'),sa.CheckConstraint('source_quantity > 0 AND normalized_quantity > 0 AND conversion_factor > 0',name='ck_preparation_batch_inputs_values'),**OPTIONS)
    if not _table('preparation_batch_outputs'):
        op.create_table('preparation_batch_outputs',
            sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=True),sa.Column('tenant_id',sa.BigInteger(),nullable=False),sa.Column('organization_id',sa.BigInteger(),nullable=False),sa.Column('location_id',sa.BigInteger(),nullable=False),sa.Column('warehouse_id',sa.BigInteger(),nullable=False),sa.Column('batch_id',sa.BigInteger(),nullable=False),sa.Column('recipe_version_id',sa.BigInteger(),nullable=False),sa.Column('inventory_item_id',sa.BigInteger(),nullable=False),sa.Column('source_quantity',sa.Numeric(19,6),nullable=False),sa.Column('source_uom',sa.String(32,collation='ascii_bin'),nullable=False),sa.Column('normalized_quantity',sa.Numeric(19,6),nullable=False),sa.Column('conversion_revision_id',sa.BigInteger()),sa.Column('conversion_factor',sa.Numeric(25,12),nullable=False),sa.Column('base_uom_evidence',sa.String(16),nullable=False),sa.Column('allocated_material_cost',sa.Numeric(31,12)),sa.Column('unit_material_cost',sa.Numeric(31,12)),sa.Column('cost_currency_evidence',sa.String(3,collation='ascii_bin')),sa.Column('evidence_status',sa.String(24),nullable=False),sa.Column('created_at',sa.DateTime(),server_default=sa.func.current_timestamp(),nullable=False),
            sa.ForeignKeyConstraint(['batch_id','tenant_id','organization_id','location_id','warehouse_id'],['preparation_batches.id','preparation_batches.tenant_id','preparation_batches.organization_id','preparation_batches.location_id','preparation_batches.warehouse_id'],name='fk_preparation_batch_outputs_batch_scope',ondelete='RESTRICT'),sa.ForeignKeyConstraint(['inventory_item_id','tenant_id','organization_id','location_id'],['inventory_items.id','inventory_items.tenant_id','inventory_items.organization_id','inventory_items.location_id'],name='fk_preparation_batch_outputs_item_scope',ondelete='RESTRICT'),sa.UniqueConstraint('id','batch_id','inventory_item_id',name='uq_preparation_batch_outputs_movement_scope'),sa.UniqueConstraint('batch_id',name='uq_preparation_batch_outputs_primary'),sa.CheckConstraint('source_quantity > 0 AND normalized_quantity > 0 AND conversion_factor > 0',name='ck_preparation_batch_outputs_values'),**OPTIONS)


def _extend_movements() -> None:
    for name in ('preparation_batch_id','preparation_batch_input_id','preparation_batch_output_id'):
        if not _column('stock_movements',name): op.add_column('stock_movements',sa.Column(name,sa.BigInteger()))
    for name in ('ck_stock_movements_type','ck_stock_movements_sign'):
        if _constraint('stock_movements',name,'check'): op.drop_constraint(name,'stock_movements',type_='check')
    op.create_check_constraint('ck_stock_movements_type','stock_movements',"movement_type IN ('OPENING_BALANCE','MANUAL_IN','MANUAL_OUT','ADJUSTMENT','REVERSAL','CONSUMPTION','GOODS_RECEIPT','WASTE','PREPARATION_INPUT','PREPARATION_OUTPUT')")
    op.create_check_constraint('ck_stock_movements_sign','stock_movements',"(movement_type IN ('OPENING_BALANCE','MANUAL_IN','GOODS_RECEIPT','PREPARATION_OUTPUT') AND quantity>0) OR (movement_type IN ('MANUAL_OUT','CONSUMPTION','WASTE','PREPARATION_INPUT') AND quantity<0) OR (movement_type IN ('ADJUSTMENT','REVERSAL') AND quantity<>0)")
    if not _constraint('stock_movements','fk_stock_movements_preparation_input_scope','foreignkey'): op.create_foreign_key('fk_stock_movements_preparation_input_scope','stock_movements','preparation_batch_inputs',['preparation_batch_input_id','preparation_batch_id','inventory_item_id'],['id','batch_id','inventory_item_id'],ondelete='RESTRICT')
    if not _constraint('stock_movements','fk_stock_movements_preparation_output_scope','foreignkey'): op.create_foreign_key('fk_stock_movements_preparation_output_scope','stock_movements','preparation_batch_outputs',['preparation_batch_output_id','preparation_batch_id','inventory_item_id'],['id','batch_id','inventory_item_id'],ondelete='RESTRICT')
    if not _constraint('stock_movements','uq_stock_movements_preparation_input','unique'): op.create_unique_constraint('uq_stock_movements_preparation_input','stock_movements',['preparation_batch_input_id'])
    if not _constraint('stock_movements','uq_stock_movements_preparation_output','unique'): op.create_unique_constraint('uq_stock_movements_preparation_output','stock_movements',['preparation_batch_output_id'])
    if not _constraint('stock_movements','ck_stock_movements_preparation_evidence','check'): op.create_check_constraint('ck_stock_movements_preparation_evidence','stock_movements',"(movement_type='PREPARATION_INPUT' AND preparation_batch_id IS NOT NULL AND preparation_batch_input_id IS NOT NULL AND preparation_batch_output_id IS NULL) OR (movement_type='PREPARATION_OUTPUT' AND preparation_batch_id IS NOT NULL AND preparation_batch_output_id IS NOT NULL AND preparation_batch_input_id IS NULL) OR (movement_type NOT IN ('PREPARATION_INPUT','PREPARATION_OUTPUT') AND preparation_batch_id IS NULL AND preparation_batch_input_id IS NULL AND preparation_batch_output_id IS NULL)")
    if not _index('stock_movements','ix_stock_movements_preparation'): op.create_index('ix_stock_movements_preparation','stock_movements',['tenant_id','preparation_batch_id','preparation_batch_input_id','preparation_batch_output_id'])


def upgrade() -> None:
    _seed_permissions(); _create_tables(); _extend_movements()


def downgrade() -> None:
    connection=op.get_bind()
    if any(
        _table(table) and connection.scalar(sa.text(f'SELECT COUNT(*) FROM {table}'))
        for table in ('preparation_batches', 'preparation_recipe_versions')
    ):
        raise RuntimeError('Cannot downgrade 0049: preparation authority evidence exists')
    for name in ('fk_stock_movements_preparation_input_scope','fk_stock_movements_preparation_output_scope'):
        if _constraint('stock_movements',name,'foreignkey'): op.drop_constraint(name,'stock_movements',type_='foreignkey')
    for name in ('uq_stock_movements_preparation_input','uq_stock_movements_preparation_output'):
        if _constraint('stock_movements',name,'unique'): op.drop_constraint(name,'stock_movements',type_='unique')
    for name in ('ck_stock_movements_preparation_evidence','ck_stock_movements_type','ck_stock_movements_sign'):
        if _constraint('stock_movements',name,'check'): op.drop_constraint(name,'stock_movements',type_='check')
    op.create_check_constraint('ck_stock_movements_type','stock_movements',"movement_type IN ('OPENING_BALANCE','MANUAL_IN','MANUAL_OUT','ADJUSTMENT','REVERSAL','CONSUMPTION','GOODS_RECEIPT','WASTE')")
    op.create_check_constraint('ck_stock_movements_sign','stock_movements',"(movement_type IN ('OPENING_BALANCE','MANUAL_IN','GOODS_RECEIPT') AND quantity>0) OR (movement_type IN ('MANUAL_OUT','CONSUMPTION','WASTE') AND quantity<0) OR (movement_type IN ('ADJUSTMENT','REVERSAL') AND quantity<>0)")
    if _index('stock_movements','ix_stock_movements_preparation'): op.drop_index('ix_stock_movements_preparation',table_name='stock_movements')
    for name in ('preparation_batch_output_id','preparation_batch_input_id','preparation_batch_id'):
        if _column('stock_movements',name): op.drop_column('stock_movements',name)
    for table in ('preparation_batch_outputs','preparation_batch_inputs','preparation_batches','preparation_recipe_components','preparation_recipe_versions'):
        if _table(table): op.drop_table(table)
    connection.execute(sa.text('DELETE rp FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id WHERE p.code IN :codes').bindparams(sa.bindparam('codes',expanding=True)),{'codes':tuple(PERMISSIONS)})
    connection.execute(sa.text('DELETE FROM permissions WHERE code IN :codes').bindparams(sa.bindparam('codes',expanding=True)),{'codes':tuple(PERMISSIONS)})
