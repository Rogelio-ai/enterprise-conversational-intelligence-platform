"""add scoped Product Category import-key bindings

Revision ID: 0053_product_category_import_binding
Revises: 0052_onboarding_import_evidence
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0053_product_category_import_binding'
down_revision: str | None = '0052_onboarding_import_evidence'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.create_table(
        'product_category_external_mappings',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('category_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_key', sa.String(128), nullable=False),
        sa.Column(
            'external_category_id',
            sa.String(200, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'created_at', sa.DateTime(),
            server_default=sa.func.current_timestamp(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_product_category_external_mappings_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['category_id', 'tenant_id', 'organization_id'],
            ['product_categories.id', 'product_categories.tenant_id', 'product_categories.organization_id'],
            name='fk_product_category_external_mappings_category_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'organization_id', 'connector_key', 'external_category_id',
            name='uq_product_category_external_mapping_source',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_product_category_external_mappings_category',
        'product_category_external_mappings',
        ['tenant_id', 'organization_id', 'category_id', 'id'],
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text(
        'SELECT COUNT(*) FROM product_category_external_mappings'
    )).scalar_one():
        raise RuntimeError('Cannot downgrade 0053 while Product Category bindings exist')
    op.drop_index(
        'ix_product_category_external_mappings_category',
        table_name='product_category_external_mappings',
    )
    op.drop_table('product_category_external_mappings')
