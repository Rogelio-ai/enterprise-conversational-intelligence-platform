"""establish menu-aware Product and Choice resolution foundation

Revision ID: 0012_product_resolution_foundation
Revises: 0011_product_structure_composition_foundation
Create Date: 2026-08-26
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0012_product_resolution_foundation'
down_revision: str | None = '0011_product_structure_composition_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'product_aliases',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column('alias', sa.String(200), nullable=False),
        sa.Column('normalized_alias', sa.String(400, collation='utf8mb4_bin'), nullable=False),
        sa.Column(
            'language',
            sa.String(63, collation='utf8mb4_bin'),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            'status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_aliases_status'
        ),
        sa.CheckConstraint(
            'CHAR_LENGTH(alias) > 0', name='ck_product_aliases_alias_nonempty'
        ),
        sa.CheckConstraint(
            'CHAR_LENGTH(normalized_alias) > 0',
            name='ck_product_aliases_normalized_nonempty',
        ),
        sa.CheckConstraint(
            'CHAR_LENGTH(language) <= 63', name='ck_product_aliases_language_length'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_aliases_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_aliases_organization_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_product_aliases_product_tenant_org',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id',
            'organization_id',
            'product_id',
            'normalized_alias',
            'language',
            name='uq_product_aliases_product_identity',
        ),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index(
        'ix_product_aliases_tenant_org_lookup',
        'product_aliases',
        [
            'tenant_id',
            'organization_id',
            'normalized_alias',
            'language',
            'status',
            'product_id',
            'id',
        ],
        unique=False,
    )
    op.create_index(
        'ix_product_aliases_tenant_org_product',
        'product_aliases',
        ['tenant_id', 'organization_id', 'product_id', 'id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table('product_aliases')
