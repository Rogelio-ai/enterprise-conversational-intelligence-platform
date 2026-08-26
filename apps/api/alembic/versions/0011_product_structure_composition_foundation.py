"""establish Product taxonomy and commercial composition foundation

Revision ID: 0011_product_structure_composition_foundation
Revises: 0010_intelligence_derivation_foundation
Create Date: 2026-08-25
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0011_product_structure_composition_foundation'
down_revision: str | None = '0010_intelligence_derivation_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
    )


def _options() -> dict[str, str]:
    return {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
        'mysql_collate': 'utf8mb4_unicode_ci',
    }


def upgrade() -> None:
    options = _options()
    op.add_column('product_categories', sa.Column('parent_id', sa.BigInteger(), nullable=True))
    op.add_column(
        'product_categories',
        sa.Column('display_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )
    op.create_check_constraint(
        'ck_product_categories_display_order', 'product_categories', 'display_order >= 0'
    )
    op.create_foreign_key(
        'fk_product_categories_parent_tenant_org',
        'product_categories',
        'product_categories',
        ['parent_id', 'tenant_id', 'organization_id'],
        ['id', 'tenant_id', 'organization_id'],
        ondelete='RESTRICT',
    )
    op.create_index(
        'ix_product_categories_tenant_org_parent_status_order',
        'product_categories',
        ['tenant_id', 'organization_id', 'parent_id', 'status', 'display_order', 'id'],
        unique=False,
    )

    op.create_table(
        'product_compositions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'status', sa.String(16), server_default=sa.text("'INACTIVE'"), nullable=False
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_compositions_status'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_compositions_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_compositions_organization_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_product_compositions_product_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_product_compositions_id_tenant_org'
        ),
        sa.UniqueConstraint(
            'tenant_id',
            'organization_id',
            'product_id',
            name='uq_product_compositions_tenant_org_product',
        ),
        **options,
    )
    op.create_index(
        'ix_product_compositions_tenant_org_product_status',
        'product_compositions',
        ['tenant_id', 'organization_id', 'product_id', 'status', 'id'],
        unique=False,
    )

    op.create_table(
        'product_components',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('composition_id', sa.BigInteger(), nullable=False),
        sa.Column('component_product_id', sa.BigInteger(), nullable=False),
        sa.Column('quantity', sa.Numeric(19, 4), nullable=False),
        sa.Column('display_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint('quantity > 0', name='ck_product_components_quantity'),
        sa.CheckConstraint('display_order >= 0', name='ck_product_components_display_order'),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_components_status'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_components_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_components_organization_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['composition_id', 'tenant_id', 'organization_id'],
            [
                'product_compositions.id',
                'product_compositions.tenant_id',
                'product_compositions.organization_id',
            ],
            name='fk_product_components_composition_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['component_product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_product_components_product_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id',
            'organization_id',
            'composition_id',
            'component_product_id',
            name='uq_product_components_composition_product',
        ),
        **options,
    )
    op.create_index(
        'ix_product_components_tenant_org_composition_status_order',
        'product_components',
        ['tenant_id', 'organization_id', 'composition_id', 'status', 'display_order', 'id'],
        unique=False,
    )

    op.create_table(
        'product_choice_groups',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('composition_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('min_selections', sa.Integer(), nullable=False),
        sa.Column('max_selections', sa.Integer(), nullable=False),
        sa.Column('display_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint('min_selections >= 0', name='ck_product_choice_groups_min'),
        sa.CheckConstraint('max_selections > 0', name='ck_product_choice_groups_max'),
        sa.CheckConstraint(
            'min_selections <= max_selections', name='ck_product_choice_groups_range'
        ),
        sa.CheckConstraint('display_order >= 0', name='ck_product_choice_groups_display_order'),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_choice_groups_status'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_choice_groups_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_choice_groups_organization_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['composition_id', 'tenant_id', 'organization_id'],
            [
                'product_compositions.id',
                'product_compositions.tenant_id',
                'product_compositions.organization_id',
            ],
            name='fk_product_choice_groups_composition_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_product_choice_groups_id_tenant_org'
        ),
        sa.UniqueConstraint(
            'tenant_id',
            'organization_id',
            'composition_id',
            'name',
            name='uq_product_choice_groups_composition_name',
        ),
        **options,
    )
    op.create_index(
        'ix_product_choice_groups_tenant_org_composition_status_order',
        'product_choice_groups',
        ['tenant_id', 'organization_id', 'composition_id', 'status', 'display_order', 'id'],
        unique=False,
    )

    op.create_table(
        'product_choice_options',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('group_id', sa.BigInteger(), nullable=False),
        sa.Column('option_product_id', sa.BigInteger(), nullable=False),
        sa.Column('quantity', sa.Numeric(19, 4), nullable=False),
        sa.Column('display_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint('quantity > 0', name='ck_product_choice_options_quantity'),
        sa.CheckConstraint('display_order >= 0', name='ck_product_choice_options_display_order'),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_choice_options_status'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_choice_options_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_choice_options_organization_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['group_id', 'tenant_id', 'organization_id'],
            [
                'product_choice_groups.id',
                'product_choice_groups.tenant_id',
                'product_choice_groups.organization_id',
            ],
            name='fk_product_choice_options_group_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['option_product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_product_choice_options_product_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id',
            'organization_id',
            'group_id',
            'option_product_id',
            name='uq_product_choice_options_group_product',
        ),
        **options,
    )
    op.create_index(
        'ix_product_choice_options_tenant_org_group_status_order',
        'product_choice_options',
        ['tenant_id', 'organization_id', 'group_id', 'status', 'display_order', 'id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table('product_choice_options')
    op.drop_table('product_choice_groups')
    op.drop_table('product_components')
    op.drop_table('product_compositions')
    op.drop_index(
        'ix_product_categories_tenant_org_parent_status_order',
        table_name='product_categories',
    )
    op.drop_constraint(
        'fk_product_categories_parent_tenant_org', 'product_categories', type_='foreignkey'
    )
    op.drop_constraint(
        'ck_product_categories_display_order', 'product_categories', type_='check'
    )
    op.drop_column('product_categories', 'display_order')
    op.drop_column('product_categories', 'parent_id')
