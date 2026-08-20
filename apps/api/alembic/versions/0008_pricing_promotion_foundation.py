"""establish Product Price and Promotion foundation

Revision ID: 0008_pricing_promotion_foundation
Revises: 0007_menu_product_foundation
Create Date: 2026-08-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0008_pricing_promotion_foundation'
down_revision: str | None = '0007_menu_product_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WS_09_PERMISSIONS = {
    'pricing.read': 'Read Organization product prices.',
    'pricing.manage': 'Manage Organization product prices.',
    'promotion.read': 'Read Organization promotions.',
    'promotion.manage': 'Manage Organization promotions.',
}


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def _options() -> dict[str, str]:
    return {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}


def _seed_permissions() -> None:
    connection = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.BigInteger()), sa.column('code', sa.String()), sa.column('description', sa.String()))
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()))
    role_permissions = sa.table('role_permissions', sa.column('id', sa.BigInteger()), sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()))
    role_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN')).scalars())
    for code, description in WS_09_PERMISSIONS.items():
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(code=code, description=description))
            permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one()
        for role_id in role_ids:
            exists = connection.execute(sa.select(role_permissions.c.id).where(role_permissions.c.role_id == role_id, role_permissions.c.permission_id == permission_id)).scalar_one_or_none()
            if exists is None:
                connection.execute(role_permissions.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    options = _options()
    op.create_table(
        'product_prices',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.Numeric(19, 4), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('source', sa.String(16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint('amount >= 0', name='ck_product_prices_amount'),
        sa.CheckConstraint("OCTET_LENGTH(currency) = 3 AND ASCII(SUBSTRING(currency, 1, 1)) BETWEEN 65 AND 90 AND ASCII(SUBSTRING(currency, 2, 1)) BETWEEN 65 AND 90 AND ASCII(SUBSTRING(currency, 3, 1)) BETWEEN 65 AND 90", name='ck_product_prices_currency'),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_product_prices_status'),
        sa.CheckConstraint("source IN ('PLATFORM', 'POS')", name='ck_product_prices_source'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_product_prices_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id', 'tenant_id'], ['organizations.id', 'organizations.tenant_id'], name='fk_product_prices_organization_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['product_id', 'tenant_id', 'organization_id'], ['products.id', 'products.tenant_id', 'products.organization_id'], name='fk_product_prices_product_tenant_org', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_product_prices_location_tenant_org', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'product_id', 'location_id', name='uq_product_prices_tenant_product_location'),
        **options,
    )
    op.create_index('ix_product_prices_tenant_org_location_status_product', 'product_prices', ['tenant_id', 'organization_id', 'location_id', 'status', 'product_id'])
    op.create_index('ix_product_prices_tenant_org_product_status', 'product_prices', ['tenant_id', 'organization_id', 'product_id', 'status'])

    op.create_table(
        'promotions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.String(2000), nullable=True),
        sa.Column('promotion_type', sa.String(32), nullable=False),
        sa.Column('benefit_value', sa.Numeric(19, 4), nullable=False),
        sa.Column('currency', sa.String(3), nullable=True),
        sa.Column('starts_at', sa.DateTime(), nullable=False),
        sa.Column('ends_at', sa.DateTime(), nullable=False),
        sa.Column('applies_to_all_locations', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'INACTIVE'"), nullable=False),
        sa.Column('source', sa.String(16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("promotion_type IN ('PERCENTAGE_DISCOUNT', 'FIXED_AMOUNT_DISCOUNT')", name='ck_promotions_type'),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_promotions_status'),
        sa.CheckConstraint("source IN ('PLATFORM', 'POS')", name='ck_promotions_source'),
        sa.CheckConstraint('starts_at < ends_at', name='ck_promotions_interval'),
        sa.CheckConstraint("currency IS NULL OR (OCTET_LENGTH(currency) = 3 AND ASCII(SUBSTRING(currency, 1, 1)) BETWEEN 65 AND 90 AND ASCII(SUBSTRING(currency, 2, 1)) BETWEEN 65 AND 90 AND ASCII(SUBSTRING(currency, 3, 1)) BETWEEN 65 AND 90)", name='ck_promotions_currency'),
        sa.CheckConstraint("(promotion_type = 'PERCENTAGE_DISCOUNT' AND benefit_value > 0 AND benefit_value <= 100 AND currency IS NULL) OR (promotion_type = 'FIXED_AMOUNT_DISCOUNT' AND benefit_value > 0 AND currency IS NOT NULL)", name='ck_promotions_benefit'),
        sa.CheckConstraint('applies_to_all_locations IN (0, 1)', name='ck_promotions_all_locations'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_promotions_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id', 'tenant_id'], ['organizations.id', 'organizations.tenant_id'], name='fk_promotions_organization_tenant', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', name='uq_promotions_id_tenant_org'),
        **options,
    )
    op.create_index('ix_promotions_tenant_org_status_type', 'promotions', ['tenant_id', 'organization_id', 'status', 'promotion_type', 'id'])
    op.create_index('ix_promotions_tenant_org_interval', 'promotions', ['tenant_id', 'organization_id', 'starts_at', 'ends_at', 'id'])

    for table, target, target_table, target_columns in (
        ('promotion_products', 'product', 'products', ['product_id', 'tenant_id', 'organization_id']),
        ('promotion_locations', 'location', 'locations', ['location_id', 'tenant_id', 'organization_id']),
    ):
        target_id = f'{target}_id'
        op.create_table(
            table,
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('tenant_id', sa.BigInteger(), nullable=False),
            sa.Column('organization_id', sa.BigInteger(), nullable=False),
            sa.Column('promotion_id', sa.BigInteger(), nullable=False),
            sa.Column(target_id, sa.BigInteger(), nullable=False),
            sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
            *_timestamps(),
            sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name=f'ck_{table}_status'),
            sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=f'fk_{table}_tenant', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['promotion_id', 'tenant_id', 'organization_id'], ['promotions.id', 'promotions.tenant_id', 'promotions.organization_id'], name=f'fk_{table}_promotion_tenant_org', ondelete='RESTRICT'),
            sa.ForeignKeyConstraint([target_id, 'tenant_id', 'organization_id'], [f'{target_table}.id', f'{target_table}.tenant_id', f'{target_table}.organization_id'], name=f'fk_{table}_{target}_tenant_org', ondelete='RESTRICT'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('tenant_id', 'promotion_id', target_id, name=f'uq_{table}_tenant_promotion_{target}'),
            **options,
        )
        op.create_index(f'ix_{table}_tenant_{target}_status', table, ['tenant_id', target_id, 'status', 'promotion_id'])
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('promotion_locations')
    op.drop_table('promotion_products')
    op.drop_table('promotions')
    op.drop_table('product_prices')
