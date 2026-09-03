"""establish location payment executor configuration foundation

Revision ID: 0024_payment_executor_foundation
Revises: 0023_restaurant_payment_settlement_foundation
Create Date: 2026-09-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0024_payment_executor_foundation'
down_revision: str | None = '0023_restaurant_payment_settlement_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _options() -> dict[str, str]:
    return {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
        'mysql_collate': 'utf8mb4_unicode_ci',
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


def upgrade() -> None:
    options = _options()
    op.create_table(
        'location_payment_executor_configurations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('executor_key', sa.String(128, collation='utf8mb4_bin'), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('adapter_kind', sa.String(128, collation='utf8mb4_bin'), nullable=False),
        sa.Column('topology', sa.String(16), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('credential_binding', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('selection_priority', sa.Integer(), server_default=sa.text('100'), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_payment_executor_configurations_scope',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'executor_key',
            name='uq_payment_executor_configurations_location_key',
        ),
        sa.CheckConstraint(
            "topology IN ('LOCAL','EXTERNAL')",
            name='ck_payment_executor_configurations_topology',
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_payment_executor_configurations_status',
        ),
        sa.CheckConstraint(
            'selection_priority >= 0',
            name='ck_payment_executor_configurations_priority',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_payment_executor_configurations_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_payment_executor_configurations_location_scope', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_payment_executor_configurations_lookup',
        'location_payment_executor_configurations',
        ['tenant_id', 'organization_id', 'location_id', 'status', 'selection_priority', 'id'],
    )

    op.create_table(
        'location_payment_executor_capabilities',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('executor_configuration_id', sa.BigInteger(), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('method_category', sa.String(16), nullable=False),
        sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'executor_configuration_id', 'method_category', 'currency',
            name='uq_payment_executor_capabilities_method_currency',
        ),
        sa.CheckConstraint(
            "method_category IN ('CASH','CARD','TRANSFER')",
            name='ck_payment_executor_capabilities_method',
        ),
        sa.CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_payment_executor_capabilities_currency',
        ),
        sa.ForeignKeyConstraint(
            ['executor_configuration_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'location_payment_executor_configurations.id',
                'location_payment_executor_configurations.tenant_id',
                'location_payment_executor_configurations.organization_id',
                'location_payment_executor_configurations.location_id',
            ],
            name='fk_payment_executor_capabilities_configuration_scope', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_payment_executor_capabilities_lookup',
        'location_payment_executor_capabilities',
        [
            'tenant_id', 'organization_id', 'location_id', 'method_category', 'currency',
            'executor_configuration_id',
        ],
    )

    op.add_column(
        'restaurant_payments',
        sa.Column('executor_configuration_id', sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        'fk_restaurant_payments_executor_configuration_scope',
        'restaurant_payments',
        'location_payment_executor_configurations',
        ['executor_configuration_id', 'tenant_id', 'organization_id', 'location_id'],
        ['id', 'tenant_id', 'organization_id', 'location_id'],
        ondelete='RESTRICT',
    )
    op.create_unique_constraint(
        'uq_restaurant_payments_configuration_external_reference',
        'restaurant_payments',
        ['executor_configuration_id', 'external_reference'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_restaurant_payments_configuration_external_reference',
        'restaurant_payments',
        type_='unique',
    )
    op.drop_constraint(
        'fk_restaurant_payments_executor_configuration_scope',
        'restaurant_payments',
        type_='foreignkey',
    )
    op.drop_index(
        'fk_restaurant_payments_executor_configuration_scope',
        table_name='restaurant_payments',
    )
    op.drop_column('restaurant_payments', 'executor_configuration_id')
    op.drop_table('location_payment_executor_capabilities')
    op.drop_table('location_payment_executor_configurations')
