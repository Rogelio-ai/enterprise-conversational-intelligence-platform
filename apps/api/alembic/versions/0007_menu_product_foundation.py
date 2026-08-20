"""establish tenant-safe Menu and Product foundation

Revision ID: 0007_menu_product_foundation
Revises: 0006_customer_foundation
Create Date: 2026-08-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0007_menu_product_foundation'
down_revision: str | None = '0006_customer_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


WS_08_PERMISSIONS = {
    'product.read': 'Read Organization products and categories.',
    'product.manage': 'Manage Organization products and categories.',
    'menu.read': 'Read Organization menus.',
    'menu.manage': 'Manage Organization menus.',
}


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
    )


def _table_options() -> dict[str, str]:
    return {
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
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()))
    role_permissions = sa.table(
        'role_permissions',
        sa.column('id', sa.BigInteger()),
        sa.column('role_id', sa.BigInteger()),
        sa.column('permission_id', sa.BigInteger()),
    )

    admin_role_ids = tuple(
        connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN')).scalars()
    )
    for code, description in WS_08_PERMISSIONS.items():
        permission_id = connection.execute(
            sa.select(permissions.c.id).where(permissions.c.code == code)
        ).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(code=code, description=description))
            permission_id = connection.execute(
                sa.select(permissions.c.id).where(permissions.c.code == code)
            ).scalar_one()
        for role_id in admin_role_ids:
            assignment_exists = connection.execute(
                sa.select(role_permissions.c.id).where(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id,
                )
            ).scalar_one_or_none()
            if assignment_exists is None:
                connection.execute(
                    role_permissions.insert().values(
                        role_id=role_id, permission_id=permission_id
                    )
                )


def upgrade() -> None:
    options = _table_options()
    op.create_unique_constraint(
        'uq_locations_id_tenant_organization',
        'locations',
        ['id', 'tenant_id', 'organization_id'],
    )

    op.create_table(
        'product_categories',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_categories_status'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_categories_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_categories_organization_tenant',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_product_categories_id_tenant'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_product_categories_id_tenant_org'
        ),
        sa.UniqueConstraint(
            'tenant_id',
            'organization_id',
            'name',
            name='uq_product_categories_tenant_org_name',
        ),
        **options,
    )
    op.create_index(
        'ix_product_categories_tenant_org_status_name',
        'product_categories',
        ['tenant_id', 'organization_id', 'status', 'name', 'id'],
        unique=False,
    )

    op.create_table(
        'products',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('category_id', sa.BigInteger(), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=2000), nullable=True),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_products_status'),
        sa.CheckConstraint("source IN ('PLATFORM', 'POS')", name='ck_products_source'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_products_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_products_organization_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['category_id', 'tenant_id', 'organization_id'],
            [
                'product_categories.id',
                'product_categories.tenant_id',
                'product_categories.organization_id',
            ],
            name='fk_products_category_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_products_id_tenant'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', name='uq_products_id_tenant_org'),
        **options,
    )
    op.create_index(
        'ix_products_tenant_org_status_name',
        'products',
        ['tenant_id', 'organization_id', 'status', 'name', 'id'],
        unique=False,
    )
    op.create_index(
        'ix_products_tenant_org_category',
        'products',
        ['tenant_id', 'organization_id', 'category_id', 'id'],
        unique=False,
    )

    op.create_table(
        'product_external_mappings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_key', sa.String(length=128), nullable=False),
        sa.Column(
            'external_product_id',
            sa.String(length=200, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_product_external_mappings_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['product_id', 'tenant_id'],
            ['products.id', 'products.tenant_id'],
            name='fk_product_external_mappings_product_tenant',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id',
            'connector_key',
            'external_product_id',
            name='uq_product_external_mapping_source',
        ),
        **options,
    )
    op.create_index(
        'ix_product_external_mappings_product',
        'product_external_mappings',
        ['tenant_id', 'product_id', 'id'],
        unique=False,
    )

    op.create_table(
        'menus',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_menus_status'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_menus_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_menus_organization_tenant',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_menus_id_tenant'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', name='uq_menus_id_tenant_org'),
        **options,
    )
    op.create_index(
        'ix_menus_tenant_org_status_name',
        'menus',
        ['tenant_id', 'organization_id', 'status', 'name', 'id'],
        unique=False,
    )

    op.create_table(
        'menu_locations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('menu_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_menu_locations_status'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_menu_locations_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['menu_id', 'tenant_id', 'organization_id'],
            ['menus.id', 'menus.tenant_id', 'menus.organization_id'],
            name='fk_menu_locations_menu_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_menu_locations_location_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'menu_id', 'location_id', name='uq_menu_locations_tenant_menu_location'
        ),
        **options,
    )
    op.create_index(
        'ix_menu_locations_tenant_location_status',
        'menu_locations',
        ['tenant_id', 'location_id', 'status', 'menu_id'],
        unique=False,
    )

    op.create_table(
        'menu_sections',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('menu_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('display_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint('display_order >= 0', name='ck_menu_sections_display_order'),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_menu_sections_status'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_menu_sections_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['menu_id', 'tenant_id', 'organization_id'],
            ['menus.id', 'menus.tenant_id', 'menus.organization_id'],
            name='fk_menu_sections_menu_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id',
            'menu_id',
            'tenant_id',
            'organization_id',
            name='uq_menu_sections_id_menu_tenant_org',
        ),
        **options,
    )
    op.create_index(
        'ix_menu_sections_menu_status_order',
        'menu_sections',
        ['tenant_id', 'menu_id', 'status', 'display_order', 'id'],
        unique=False,
    )

    op.create_table(
        'menu_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('menu_id', sa.BigInteger(), nullable=False),
        sa.Column('section_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('display_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint('display_order >= 0', name='ck_menu_items_display_order'),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_menu_items_status'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_menu_items_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['menu_id', 'tenant_id', 'organization_id'],
            ['menus.id', 'menus.tenant_id', 'menus.organization_id'],
            name='fk_menu_items_menu_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['section_id', 'menu_id', 'tenant_id', 'organization_id'],
            [
                'menu_sections.id',
                'menu_sections.menu_id',
                'menu_sections.tenant_id',
                'menu_sections.organization_id',
            ],
            name='fk_menu_items_section_menu_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_menu_items_product_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'menu_id', 'product_id', name='uq_menu_items_tenant_menu_product'
        ),
        **options,
    )
    op.create_index(
        'ix_menu_items_section_status_order',
        'menu_items',
        ['tenant_id', 'menu_id', 'section_id', 'status', 'display_order', 'id'],
        unique=False,
    )
    op.create_index(
        'ix_menu_items_tenant_product',
        'menu_items',
        ['tenant_id', 'product_id', 'menu_id', 'id'],
        unique=False,
    )
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('menu_items')
    op.drop_table('menu_sections')
    op.drop_table('menu_locations')
    op.drop_table('menus')
    op.drop_table('product_external_mappings')
    op.drop_table('products')
    op.drop_table('product_categories')
    op.drop_constraint('uq_locations_id_tenant_organization', 'locations', type_='unique')
    # Preserve permission catalog entries and grants; their later provenance is unknowable.
