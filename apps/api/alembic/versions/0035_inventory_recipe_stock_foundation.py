"""establish minimum inventory recipe and stock foundation

Revision ID: 0035_inventory_recipe_stock_foundation
Revises: 0034_cash_payment_integration
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0035_inventory_recipe_stock_foundation'
down_revision: str | None = '0034_cash_payment_integration'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    'inventory.read': 'Read location inventory, stock, recipes, and current costs.',
    'inventory.manage': 'Manage location inventory, recipes, and stock movements.',
}
OPTIONS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def _seed_permissions() -> None:
    connection = op.get_bind()
    permissions = sa.table(
        'permissions',
        sa.column('id', sa.BigInteger()),
        sa.column('code', sa.String()),
        sa.column('description', sa.String()),
    )
    roles = sa.table(
        'roles',
        sa.column('id', sa.BigInteger()),
        sa.column('name', sa.String()),
        sa.column('status', sa.String()),
    )
    grants = sa.table(
        'role_permissions',
        sa.column('id', sa.BigInteger()),
        sa.column('role_id', sa.BigInteger()),
        sa.column('permission_id', sa.BigInteger()),
    )
    admin_role_ids = tuple(
        connection.execute(
            sa.select(roles.c.id).where(
                roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE'
            )
        ).scalars()
    )
    for code, description in PERMISSIONS.items():
        permission_id = connection.execute(
            sa.select(permissions.c.id).where(permissions.c.code == code)
        ).scalar_one_or_none()
        if permission_id is None:
            connection.execute(
                permissions.insert().values(code=code, description=description)
            )
            permission_id = connection.execute(
                sa.select(permissions.c.id).where(permissions.c.code == code)
            ).scalar_one()
        for role_id in admin_role_ids:
            exists = connection.execute(
                sa.select(grants.c.id).where(
                    grants.c.role_id == role_id,
                    grants.c.permission_id == permission_id,
                )
            ).scalar_one_or_none()
            if exists is None:
                connection.execute(
                    grants.insert().values(
                        role_id=role_id, permission_id=permission_id
                    )
                )


def upgrade() -> None:
    op.create_table(
        'inventory_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('base_uom', sa.String(16), nullable=False),
        sa.Column('standard_unit_cost', sa.Numeric(19, 6), nullable=False),
        sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
        sa.Column(
            'status', sa.String(16), server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            'version', sa.BigInteger(), server_default=sa.text('1'), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_inventory_items_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_inventory_items_organization_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_inventory_items_location_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_inventory_items_scope',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'code',
            name='uq_inventory_items_location_code',
        ),
        sa.CheckConstraint(
            "base_uom IN ('KG','G','L','ML','UNIT','PORTION')",
            name='ck_inventory_items_base_uom',
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')", name='ck_inventory_items_status'
        ),
        sa.CheckConstraint(
            'standard_unit_cost >= 0', name='ck_inventory_items_standard_cost'
        ),
        sa.CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_inventory_items_currency',
        ),
        sa.CheckConstraint('version >= 1', name='ck_inventory_items_version'),
        **OPTIONS,
    )
    op.create_index(
        'ix_inventory_items_location_status_name', 'inventory_items',
        ['tenant_id', 'location_id', 'status', 'name', 'id'], unique=False,
    )

    op.create_table(
        'product_consumption_definitions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'version', sa.BigInteger(), server_default=sa.text('1'), nullable=False
        ),
        sa.Column(
            'status', sa.String(16), server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column('tracking_mode', sa.String(24), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_consumption_definitions_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_consumption_definitions_organization_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_consumption_definitions_location_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_consumption_definitions_product_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_consumption_definitions_scope',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'product_id',
            name='uq_consumption_definitions_product_location',
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_consumption_definitions_status',
        ),
        sa.CheckConstraint(
            "tracking_mode IN ('DERIVABLE','NON_DERIVABLE')",
            name='ck_consumption_definitions_tracking_mode',
        ),
        sa.CheckConstraint(
            'version >= 1', name='ck_consumption_definitions_version'
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_consumption_definitions_location_status',
        'product_consumption_definitions',
        ['tenant_id', 'location_id', 'status', 'product_id', 'id'], unique=False,
    )

    op.create_table(
        'product_consumption_components',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('definition_id', sa.BigInteger(), nullable=False),
        sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
        sa.Column('quantity', sa.Numeric(19, 6), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['definition_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'product_consumption_definitions.id',
                'product_consumption_definitions.tenant_id',
                'product_consumption_definitions.organization_id',
                'product_consumption_definitions.location_id',
            ],
            name='fk_consumption_components_definition_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'inventory_items.id', 'inventory_items.tenant_id',
                'inventory_items.organization_id', 'inventory_items.location_id',
            ],
            name='fk_consumption_components_item_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'definition_id', 'inventory_item_id',
            name='uq_consumption_components_definition_item',
        ),
        sa.CheckConstraint(
            'quantity > 0', name='ck_consumption_components_quantity'
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_consumption_components_definition',
        'product_consumption_components',
        ['tenant_id', 'definition_id', 'inventory_item_id', 'id'], unique=False,
    )

    op.create_table(
        'stock_movements',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('inventory_item_id', sa.BigInteger(), nullable=False),
        sa.Column('movement_type', sa.String(24), nullable=False),
        sa.Column('quantity', sa.Numeric(19, 6), nullable=False),
        sa.Column('reversal_of_movement_id', sa.BigInteger(), nullable=True),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column(
            'reference', sa.String(200, collation='utf8mb4_bin'), nullable=True
        ),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.Column('actor_type', sa.String(24), nullable=False),
        sa.Column('actor_id', sa.BigInteger(), nullable=True),
        sa.Column(
            'actor_reference', sa.String(200, collation='utf8mb4_bin'),
            nullable=True,
        ),
        sa.Column('opening_balance_slot', sa.SmallInteger(), nullable=True),
        sa.Column(
            'idempotency_actor_scope', sa.String(200, collation='ascii_bin'),
            nullable=False,
        ),
        sa.Column(
            'idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False
        ),
        sa.Column('request_schema_version', sa.Integer(), nullable=False),
        sa.Column(
            'request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'inventory_items.id', 'inventory_items.tenant_id',
                'inventory_items.organization_id', 'inventory_items.location_id',
            ],
            name='fk_stock_movements_item_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            [
                'reversal_of_movement_id', 'tenant_id', 'organization_id',
                'location_id', 'inventory_item_id',
            ],
            [
                'stock_movements.id', 'stock_movements.tenant_id',
                'stock_movements.organization_id', 'stock_movements.location_id',
                'stock_movements.inventory_item_id',
            ],
            name='fk_stock_movements_reversal_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id',
            name='uq_stock_movements_scope',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'idempotency_actor_scope', 'idempotency_key',
            name='uq_stock_movements_idempotency',
        ),
        sa.UniqueConstraint(
            'inventory_item_id', 'opening_balance_slot',
            name='uq_stock_movements_opening_balance',
        ),
        sa.UniqueConstraint(
            'reversal_of_movement_id', name='uq_stock_movements_direct_reversal'
        ),
        sa.CheckConstraint(
            "movement_type IN ('OPENING_BALANCE','MANUAL_IN','MANUAL_OUT',"
            "'ADJUSTMENT','REVERSAL','CONSUMPTION')",
            name='ck_stock_movements_type',
        ),
        sa.CheckConstraint('quantity <> 0', name='ck_stock_movements_nonzero'),
        sa.CheckConstraint(
            "(movement_type IN ('OPENING_BALANCE','MANUAL_IN') AND quantity>0) OR "
            "(movement_type IN ('MANUAL_OUT','CONSUMPTION') AND quantity<0) OR "
            "(movement_type IN ('ADJUSTMENT','REVERSAL') AND quantity<>0)",
            name='ck_stock_movements_sign',
        ),
        sa.CheckConstraint(
            "(movement_type='OPENING_BALANCE' AND opening_balance_slot=1) OR "
            "(movement_type<>'OPENING_BALANCE' AND opening_balance_slot IS NULL)",
            name='ck_stock_movements_opening_slot',
        ),
        sa.CheckConstraint(
            "(movement_type='REVERSAL' AND reversal_of_movement_id IS NOT NULL) OR "
            "(movement_type<>'REVERSAL' AND reversal_of_movement_id IS NULL)",
            name='ck_stock_movements_reversal',
        ),
        sa.CheckConstraint(
            "movement_type='OPENING_BALANCE' OR "
            "(reason IS NOT NULL AND TRIM(reason)<>'')",
            name='ck_stock_movements_reason',
        ),
        sa.CheckConstraint(
            'request_schema_version >= 1', name='ck_stock_movements_version'
        ),
        sa.CheckConstraint(
            "(actor_type='EMPLOYEE' AND actor_id IS NOT NULL AND actor_reference IS NULL) OR "
            "(actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND actor_id IS NULL "
            "AND actor_reference IS NOT NULL)",
            name='ck_stock_movements_actor',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_stock_movements_stock', 'stock_movements',
        ['tenant_id', 'location_id', 'inventory_item_id', 'recorded_at', 'id'],
        unique=False,
    )
    _seed_permissions()


def downgrade() -> None:
    connection = op.get_bind()
    permissions = sa.table(
        'permissions', sa.column('id', sa.BigInteger()), sa.column('code', sa.String())
    )
    grants = sa.table(
        'role_permissions', sa.column('permission_id', sa.BigInteger())
    )
    permission_ids = tuple(
        connection.execute(
            sa.select(permissions.c.id).where(permissions.c.code.in_(tuple(PERMISSIONS)))
        ).scalars()
    )
    if permission_ids:
        connection.execute(grants.delete().where(grants.c.permission_id.in_(permission_ids)))
        connection.execute(permissions.delete().where(permissions.c.id.in_(permission_ids)))
    op.drop_index('ix_stock_movements_stock', table_name='stock_movements')
    op.drop_table('stock_movements')
    op.drop_index(
        'ix_consumption_components_definition',
        table_name='product_consumption_components',
    )
    op.drop_table('product_consumption_components')
    op.drop_index(
        'ix_consumption_definitions_location_status',
        table_name='product_consumption_definitions',
    )
    op.drop_table('product_consumption_definitions')
    op.drop_index(
        'ix_inventory_items_location_status_name', table_name='inventory_items'
    )
    op.drop_table('inventory_items')
