"""integrate accepted restaurant orders with inventory consumption

Revision ID: 0036_restaurant_order_consumption
Revises: 0035_inventory_recipe_stock_foundation
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0036_restaurant_order_consumption'
down_revision: str | None = '0035_inventory_recipe_stock_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.create_table(
        'restaurant_order_consumptions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('coverage_status', sa.String(16), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column(
            'source_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False
        ),
        sa.Column('unresolved_evidence', sa.JSON(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_orders.id', 'restaurant_orders.tenant_id',
                'restaurant_orders.organization_id', 'restaurant_orders.location_id',
            ],
            name='fk_order_consumptions_order_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            'restaurant_order_id', name='uq_order_consumptions_scope',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id',
            name='uq_order_consumptions_order',
        ),
        sa.CheckConstraint(
            "coverage_status IN ('COMPLETE','PARTIAL')",
            name='ck_order_consumptions_coverage',
        ),
        sa.CheckConstraint(
            'schema_version >= 1', name='ck_order_consumptions_version'
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_order_consumptions_order', 'restaurant_order_consumptions',
        ['tenant_id', 'restaurant_order_id', 'id'], unique=False,
    )

    columns = (
        sa.Column('restaurant_order_consumption_id', sa.BigInteger(), nullable=True),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=True),
        sa.Column('restaurant_order_item_id', sa.BigInteger(), nullable=True),
        sa.Column('restaurant_order_item_component_id', sa.BigInteger(), nullable=True),
        sa.Column('source_product_id', sa.BigInteger(), nullable=True),
        sa.Column('consumption_definition_id', sa.BigInteger(), nullable=True),
        sa.Column('consumption_definition_version', sa.BigInteger(), nullable=True),
        sa.Column('inventory_item_name_snapshot', sa.String(200), nullable=True),
        sa.Column('base_uom_snapshot', sa.String(16), nullable=True),
        sa.Column('unit_cost_snapshot', sa.Numeric(19, 6), nullable=True),
        sa.Column(
            'currency_snapshot', sa.String(3, collation='ascii_bin'), nullable=True
        ),
        sa.Column('extended_cost_snapshot', sa.Numeric(31, 12), nullable=True),
        sa.Column(
            'consumption_source_key', sa.String(128, collation='ascii_bin'),
            nullable=True,
        ),
    )
    for column in columns:
        op.add_column('stock_movements', column)

    op.create_foreign_key(
        'fk_stock_movements_order_consumption_scope', 'stock_movements',
        'restaurant_order_consumptions',
        [
            'restaurant_order_consumption_id', 'tenant_id', 'organization_id',
            'location_id', 'restaurant_order_id',
        ],
        ['id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_stock_movements_order_item_scope', 'stock_movements',
        'restaurant_order_items',
        ['restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'],
        ['id', 'tenant_id', 'order_id'], ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_stock_movements_order_component_scope', 'stock_movements',
        'restaurant_order_item_components',
        [
            'restaurant_order_item_component_id', 'tenant_id',
            'restaurant_order_id', 'restaurant_order_item_id',
        ],
        ['id', 'tenant_id', 'order_id', 'order_item_id'], ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_stock_movements_source_product_scope', 'stock_movements', 'products',
        ['source_product_id', 'tenant_id', 'organization_id'],
        ['id', 'tenant_id', 'organization_id'], ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_stock_movements_definition_scope', 'stock_movements',
        'product_consumption_definitions',
        ['consumption_definition_id', 'tenant_id', 'organization_id', 'location_id'],
        ['id', 'tenant_id', 'organization_id', 'location_id'], ondelete='RESTRICT',
    )
    op.create_unique_constraint(
        'uq_stock_movements_consumption_source', 'stock_movements',
        ['restaurant_order_consumption_id', 'consumption_source_key'],
    )
    op.create_check_constraint(
        'ck_stock_movements_consumption_evidence', 'stock_movements',
        "(movement_type='CONSUMPTION' AND "
        'restaurant_order_consumption_id IS NOT NULL AND '
        'restaurant_order_id IS NOT NULL AND restaurant_order_item_id IS NOT NULL AND '
        'source_product_id IS NOT NULL AND consumption_definition_id IS NOT NULL AND '
        'consumption_definition_version IS NOT NULL AND '
        'inventory_item_name_snapshot IS NOT NULL AND base_uom_snapshot IS NOT NULL AND '
        'unit_cost_snapshot IS NOT NULL AND currency_snapshot IS NOT NULL AND '
        'extended_cost_snapshot IS NOT NULL AND consumption_source_key IS NOT NULL) OR '
        "(movement_type<>'CONSUMPTION' AND "
        'restaurant_order_consumption_id IS NULL AND restaurant_order_id IS NULL AND '
        'restaurant_order_item_id IS NULL AND restaurant_order_item_component_id IS NULL AND '
        'source_product_id IS NULL AND consumption_definition_id IS NULL AND '
        'consumption_definition_version IS NULL AND inventory_item_name_snapshot IS NULL AND '
        'base_uom_snapshot IS NULL AND unit_cost_snapshot IS NULL AND '
        'currency_snapshot IS NULL AND extended_cost_snapshot IS NULL AND '
        'consumption_source_key IS NULL)',
    )
    op.create_check_constraint(
        'ck_stock_movements_consumption_cost', 'stock_movements',
        '(unit_cost_snapshot IS NULL OR unit_cost_snapshot >= 0) AND '
        '(extended_cost_snapshot IS NULL OR extended_cost_snapshot >= 0)',
    )
    op.create_index(
        'ix_stock_movements_order_consumption', 'stock_movements',
        ['tenant_id', 'restaurant_order_id', 'restaurant_order_item_id', 'id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_stock_movements_order_consumption', table_name='stock_movements'
    )
    op.drop_constraint(
        'ck_stock_movements_consumption_cost', 'stock_movements', type_='check'
    )
    op.drop_constraint(
        'ck_stock_movements_consumption_evidence', 'stock_movements', type_='check'
    )
    op.drop_constraint(
        'uq_stock_movements_consumption_source', 'stock_movements', type_='unique'
    )
    for name in (
        'fk_stock_movements_definition_scope',
        'fk_stock_movements_source_product_scope',
        'fk_stock_movements_order_component_scope',
        'fk_stock_movements_order_item_scope',
        'fk_stock_movements_order_consumption_scope',
    ):
        op.drop_constraint(name, 'stock_movements', type_='foreignkey')
        op.drop_index(name, table_name='stock_movements')
    for name in (
        'consumption_source_key', 'extended_cost_snapshot', 'currency_snapshot',
        'unit_cost_snapshot', 'base_uom_snapshot', 'inventory_item_name_snapshot',
        'consumption_definition_version', 'consumption_definition_id',
        'source_product_id', 'restaurant_order_item_component_id',
        'restaurant_order_item_id', 'restaurant_order_id',
        'restaurant_order_consumption_id',
    ):
        op.drop_column('stock_movements', name)
    op.drop_index(
        'ix_order_consumptions_order', table_name='restaurant_order_consumptions'
    )
    op.drop_table('restaurant_order_consumptions')
