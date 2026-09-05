"""establish canonical fiscal product evidence

Revision ID: 0028_canonical_fiscal_product_evidence
Revises: 0027_fiscal_issuance_foundation
Create Date: 2026-09-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0028_canonical_fiscal_product_evidence'
down_revision: str | None = '0027_fiscal_issuance_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _options() -> dict[str, str]:
    return {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
        'mysql_collate': 'utf8mb4_unicode_ci',
    }


def upgrade() -> None:
    options = _options()
    op.create_table(
        'product_fiscal_classifications',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('product_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'fiscal_jurisdiction_code',
            sa.String(16, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'product_classification_scheme',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'product_classification_code',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'unit_classification_scheme',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'unit_classification_code',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column('effective_from', sa.DateTime(), nullable=False),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column(
            'status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id',
            name='uq_product_fiscal_classifications_scope',
        ),
        sa.CheckConstraint(
            'effective_to IS NULL OR effective_from < effective_to',
            name='ck_product_fiscal_classifications_interval',
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_product_fiscal_classifications_status',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_product_fiscal_classifications_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_fiscal_classifications_org', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_product_fiscal_classifications_product', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_product_fiscal_classifications_resolution',
        'product_fiscal_classifications',
        [
            'tenant_id', 'organization_id', 'product_id',
            'fiscal_jurisdiction_code', 'status', 'effective_from', 'effective_to', 'id',
        ],
    )

    op.create_table(
        'restaurant_order_item_fiscal_snapshots',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_item_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'source_product_fiscal_classification_id', sa.BigInteger(), nullable=False
        ),
        sa.Column(
            'fiscal_jurisdiction_code',
            sa.String(16, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'product_classification_scheme',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'product_classification_code',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'unit_classification_scheme',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'unit_classification_code',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column(
            'evidence_fingerprint',
            sa.String(64, collation='ascii_bin'),
            nullable=False,
        ),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'restaurant_order_item_id', name='uq_order_item_fiscal_snapshots_item'
        ),
        sa.CheckConstraint(
            'schema_version >= 1', name='ck_order_item_fiscal_snapshots_version'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_order_item_fiscal_snapshots_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_order_item_fiscal_snapshots_org', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_order_item_fiscal_snapshots_location', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_orders.id', 'restaurant_orders.tenant_id',
                'restaurant_orders.organization_id', 'restaurant_orders.location_id',
            ],
            name='fk_order_item_fiscal_snapshots_order', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'],
            [
                'restaurant_order_items.id', 'restaurant_order_items.tenant_id',
                'restaurant_order_items.order_id',
            ],
            name='fk_order_item_fiscal_snapshots_item', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['source_product_fiscal_classification_id', 'tenant_id', 'organization_id'],
            [
                'product_fiscal_classifications.id',
                'product_fiscal_classifications.tenant_id',
                'product_fiscal_classifications.organization_id',
            ],
            name='fk_order_item_fiscal_snapshots_source', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_order_item_fiscal_snapshots_item',
        'restaurant_order_item_fiscal_snapshots',
        ['tenant_id', 'restaurant_order_id', 'restaurant_order_item_id', 'id'],
    )


def downgrade() -> None:
    op.drop_table('restaurant_order_item_fiscal_snapshots')
    op.drop_table('product_fiscal_classifications')
