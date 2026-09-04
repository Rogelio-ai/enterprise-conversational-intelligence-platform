"""establish authoritative tax evidence persistence foundation

Revision ID: 0026_authoritative_tax_evidence
Revises: 0025_billing_canonical_foundation
Create Date: 2026-09-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0026_authoritative_tax_evidence'
down_revision: str | None = '0025_billing_canonical_foundation'
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

    op.add_column(
        'products',
        sa.Column(
            'tax_classification_code',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=True,
        ),
    )

    op.create_table(
        'restaurant_tax_rules',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=True),
        sa.Column(
            'tax_classification_code',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'jurisdiction_code',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column('tax_category', sa.String(64), nullable=False),
        sa.Column('tax_treatment', sa.String(32), nullable=False),
        sa.Column('tax_rate', sa.Numeric(9, 6), nullable=False),
        sa.Column(
            'calculation_policy',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'rounding_policy',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column('effective_from', sa.DateTime(), nullable=False),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column(
            'status',
            sa.String(16),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_restaurant_tax_rules_scope'
        ),
        sa.CheckConstraint('tax_rate >= 0', name='ck_restaurant_tax_rules_rate'),
        sa.CheckConstraint(
            'effective_to IS NULL OR effective_from < effective_to',
            name='ck_restaurant_tax_rules_effective_interval',
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name='ck_restaurant_tax_rules_status',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_restaurant_tax_rules_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_restaurant_tax_rules_organization_scope',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_restaurant_tax_rules_location_scope',
            ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_restaurant_tax_rules_resolution',
        'restaurant_tax_rules',
        [
            'tenant_id',
            'organization_id',
            'location_id',
            'tax_classification_code',
            'status',
            'effective_from',
            'effective_to',
            'id',
        ],
    )

    op.create_table(
        'restaurant_order_item_tax_snapshots',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_item_id', sa.BigInteger(), nullable=False),
        sa.Column('source_tax_rule_id', sa.BigInteger(), nullable=False),
        sa.Column('tax_category', sa.String(64), nullable=False),
        sa.Column('tax_treatment', sa.String(32), nullable=False),
        sa.Column('tax_rate', sa.Numeric(9, 6), nullable=False),
        sa.Column('taxable_base', sa.Numeric(19, 4), nullable=False),
        sa.Column('tax_amount', sa.Numeric(19, 4), nullable=False),
        sa.Column(
            'jurisdiction_code',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'calculation_policy',
            sa.String(64, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'rounding_policy',
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
            'created_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            'tax_rate >= 0 AND taxable_base >= 0 AND tax_amount >= 0',
            name='ck_order_item_tax_snapshots_values',
        ),
        sa.CheckConstraint(
            'schema_version >= 1', name='ck_order_item_tax_snapshots_schema_version'
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_order_item_tax_snapshots_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_order_item_tax_snapshots_organization_scope',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_order_item_tax_snapshots_location_scope',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_orders.id',
                'restaurant_orders.tenant_id',
                'restaurant_orders.organization_id',
                'restaurant_orders.location_id',
            ],
            name='fk_order_item_tax_snapshots_order_scope',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'],
            [
                'restaurant_order_items.id',
                'restaurant_order_items.tenant_id',
                'restaurant_order_items.order_id',
            ],
            name='fk_order_item_tax_snapshots_item_scope',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['source_tax_rule_id', 'tenant_id', 'organization_id'],
            [
                'restaurant_tax_rules.id',
                'restaurant_tax_rules.tenant_id',
                'restaurant_tax_rules.organization_id',
            ],
            name='fk_order_item_tax_snapshots_rule_scope',
            ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_order_item_tax_snapshots_item',
        'restaurant_order_item_tax_snapshots',
        ['tenant_id', 'restaurant_order_id', 'restaurant_order_item_id', 'id'],
    )


def downgrade() -> None:
    op.drop_table('restaurant_order_item_tax_snapshots')
    op.drop_table('restaurant_tax_rules')
    op.drop_column('products', 'tax_classification_code')
