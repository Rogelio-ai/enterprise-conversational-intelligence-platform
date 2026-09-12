"""add immutable effective-dated recipe versions

Revision ID: 0043_immutable_recipe_versions
Revises: 0042_inventory_operational_uom_cost_evidence
Create Date: 2026-09-11
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0043_immutable_recipe_versions'
down_revision: str | None = '0042_inventory_operational_uom_cost_evidence'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _column(table: str, name: str) -> bool:
    return any(value['name'] == name for value in _inspector().get_columns(table))


def _foreign_key(table: str, name: str) -> bool:
    return any(value['name'] == name for value in _inspector().get_foreign_keys(table))


def _index(table: str, name: str) -> bool:
    return any(value['name'] == name for value in _inspector().get_indexes(table))


def _create_versions() -> None:
    if not _table('product_consumption_versions'):
        op.create_table(
            'product_consumption_versions',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('definition_id', sa.BigInteger(), nullable=False),
            sa.Column('revision', sa.BigInteger(), nullable=False),
            sa.Column('status', sa.String(16), nullable=False),
            sa.Column('tracking_mode', sa.String(24), nullable=False),
            sa.Column('publication_status', sa.String(16), server_default=sa.text("'PUBLISHED'"), nullable=False),
            sa.Column('effective_from', sa.DateTime(), nullable=False),
            sa.Column('effective_to', sa.DateTime(), nullable=True),
            sa.Column('actor_id', sa.BigInteger(), nullable=True),
            sa.Column('source', sa.String(48, collation='ascii_bin'), nullable=False),
            sa.Column('published_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(
                ['definition_id', 'tenant_id', 'organization_id', 'location_id'],
                ['product_consumption_definitions.id', 'product_consumption_definitions.tenant_id', 'product_consumption_definitions.organization_id', 'product_consumption_definitions.location_id'],
                name='fk_consumption_versions_definition_scope', ondelete='RESTRICT',
            ),
            sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'definition_id', name='uq_consumption_versions_scope'),
            sa.UniqueConstraint('definition_id', 'revision', name='uq_consumption_versions_revision'),
            sa.CheckConstraint('revision >= 1', name='ck_consumption_versions_revision'),
            sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_consumption_versions_status'),
            sa.CheckConstraint("tracking_mode IN ('DERIVABLE','NON_DERIVABLE')", name='ck_consumption_versions_tracking_mode'),
            sa.CheckConstraint("publication_status='PUBLISHED'", name='ck_consumption_versions_publication'),
            sa.CheckConstraint('effective_to IS NULL OR effective_to >= effective_from', name='ck_consumption_versions_effectivity'),
            **OPTIONS,
        )
        op.create_index('ix_consumption_versions_resolve', 'product_consumption_versions', ['tenant_id', 'location_id', 'definition_id', 'effective_from', 'effective_to', 'revision'])

    if not _table('product_consumption_version_components'):
        op.create_table(
            'product_consumption_version_components',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('location_id', sa.BigInteger(), nullable=False),
            sa.Column('definition_id', sa.BigInteger(), nullable=False),
            sa.Column('version_id', sa.BigInteger(), nullable=False),
            sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
            sa.Column('quantity', sa.Numeric(19, 6), nullable=False),
            sa.Column('source_quantity', sa.Numeric(19, 6), nullable=False),
            sa.Column('source_uom', sa.String(32, collation='ascii_bin'), nullable=False),
            sa.Column('conversion_revision_id', sa.BigInteger(), nullable=True),
            sa.Column('conversion_factor', sa.Numeric(25, 12), nullable=False),
            sa.Column('base_uom_evidence', sa.String(16), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(
                ['version_id', 'tenant_id', 'organization_id', 'location_id', 'definition_id'],
                ['product_consumption_versions.id', 'product_consumption_versions.tenant_id', 'product_consumption_versions.organization_id', 'product_consumption_versions.location_id', 'product_consumption_versions.definition_id'],
                name='fk_version_components_version_scope', ondelete='RESTRICT',
            ),
            sa.ForeignKeyConstraint(
                ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
                ['inventory_items.id', 'inventory_items.tenant_id', 'inventory_items.organization_id', 'inventory_items.location_id'],
                name='fk_version_components_item_scope', ondelete='RESTRICT',
            ),
            sa.ForeignKeyConstraint(
                ['conversion_revision_id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id'],
                ['item_uom_conversions.id', 'item_uom_conversions.tenant_id', 'item_uom_conversions.organization_id', 'item_uom_conversions.location_id', 'item_uom_conversions.inventory_item_id'],
                name='fk_version_components_conversion_scope', ondelete='RESTRICT',
            ),
            sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'definition_id', 'version_id', name='uq_version_components_scope'),
            sa.UniqueConstraint('version_id', 'inventory_item_id', name='uq_version_components_version_item'),
            sa.CheckConstraint('quantity > 0 AND source_quantity > 0 AND conversion_factor > 0', name='ck_version_components_quantity_evidence'),
            **OPTIONS,
        )
        op.create_index('ix_version_components_version', 'product_consumption_version_components', ['tenant_id', 'version_id', 'inventory_item_id', 'id'])


def _backfill() -> None:
    op.execute(sa.text(
        "INSERT INTO product_consumption_versions "
        "(tenant_id,organization_id,location_id,definition_id,revision,status,"
        "tracking_mode,publication_status,effective_from,effective_to,actor_id,source,published_at) "
        "SELECT d.tenant_id,d.organization_id,d.location_id,d.id,1,d.status,"
        "d.tracking_mode,'PUBLISHED',CURRENT_TIMESTAMP,NULL,NULL,"
        "'LEGACY_RECIPE_SNAPSHOT',CURRENT_TIMESTAMP FROM product_consumption_definitions d "
        "WHERE NOT EXISTS (SELECT 1 FROM product_consumption_versions v WHERE v.definition_id=d.id)"
    ))
    op.execute(sa.text(
        "INSERT INTO product_consumption_version_components "
        "(tenant_id,organization_id,location_id,definition_id,version_id,inventory_item_id,"
        "quantity,source_quantity,source_uom,conversion_revision_id,conversion_factor,base_uom_evidence) "
        "SELECT c.tenant_id,c.organization_id,c.location_id,c.definition_id,v.id,c.inventory_item_id,"
        "c.quantity,c.quantity,i.base_uom,NULL,1.000000000000,i.base_uom "
        "FROM product_consumption_components c "
        "JOIN product_consumption_versions v ON v.definition_id=c.definition_id AND v.revision=1 "
        "JOIN inventory_items i ON i.id=c.inventory_item_id "
        "WHERE NOT EXISTS (SELECT 1 FROM product_consumption_version_components vc "
        "WHERE vc.version_id=v.id AND vc.inventory_item_id=c.inventory_item_id)"
    ))


def _add_movement_evidence() -> None:
    for name in ('consumption_version_id', 'consumption_version_component_id'):
        if not _column('stock_movements', name):
            op.add_column('stock_movements', sa.Column(name, sa.BigInteger(), nullable=True))
    if not _foreign_key('stock_movements', 'fk_stock_movements_consumption_version_scope'):
        op.create_foreign_key(
            'fk_stock_movements_consumption_version_scope', 'stock_movements',
            'product_consumption_versions',
            ['consumption_version_id', 'tenant_id', 'organization_id', 'location_id', 'consumption_definition_id'],
            ['id', 'tenant_id', 'organization_id', 'location_id', 'definition_id'],
            ondelete='RESTRICT',
        )
    if not _foreign_key('stock_movements', 'fk_stock_movements_version_component_scope'):
        op.create_foreign_key(
            'fk_stock_movements_version_component_scope', 'stock_movements',
            'product_consumption_version_components',
            ['consumption_version_component_id', 'tenant_id', 'organization_id', 'location_id', 'consumption_definition_id', 'consumption_version_id'],
            ['id', 'tenant_id', 'organization_id', 'location_id', 'definition_id', 'version_id'],
            ondelete='RESTRICT',
        )


def upgrade() -> None:
    _create_versions()
    _backfill()
    _add_movement_evidence()


def downgrade() -> None:
    for name in (
        'fk_stock_movements_version_component_scope',
        'fk_stock_movements_consumption_version_scope',
    ):
        if _foreign_key('stock_movements', name):
            op.drop_constraint(name, 'stock_movements', type_='foreignkey')
        if _index('stock_movements', name):
            op.drop_index(name, table_name='stock_movements')
    for name in ('consumption_version_component_id', 'consumption_version_id'):
        if _column('stock_movements', name):
            op.drop_column('stock_movements', name)
    if _table('product_consumption_version_components'):
        op.drop_table('product_consumption_version_components')
    if _table('product_consumption_versions'):
        op.drop_table('product_consumption_versions')
