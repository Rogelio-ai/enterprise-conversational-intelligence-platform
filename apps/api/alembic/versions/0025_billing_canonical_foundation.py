"""establish canonical billing persistence foundation

Revision ID: 0025_billing_canonical_foundation
Revises: 0024_payment_executor_foundation
Create Date: 2026-09-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0025_billing_canonical_foundation'
down_revision: str | None = '0024_payment_executor_foundation'
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


def _created_at() -> sa.Column:
    return sa.Column(
        'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False
    )


def upgrade() -> None:
    options = _options()

    op.create_table(
        'issuer_fiscal_profiles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('legal_name', sa.String(200), nullable=False),
        sa.Column('tax_identifier', sa.String(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column('tax_regime', sa.String(100), nullable=False),
        sa.Column('fiscal_postal_code', sa.String(32), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id',
            name='uq_issuer_fiscal_profiles_scope',
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_issuer_fiscal_profiles_status',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_issuer_fiscal_profiles_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_issuer_fiscal_profiles_organization_scope', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_issuer_fiscal_profiles_organization_status',
        'issuer_fiscal_profiles',
        ['tenant_id', 'organization_id', 'status', 'id'],
    )

    op.create_table(
        'customer_fiscal_profiles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('customer_id', sa.BigInteger(), nullable=False),
        sa.Column('legal_name', sa.String(200), nullable=False),
        sa.Column('tax_identifier', sa.String(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column('tax_regime', sa.String(100), nullable=False),
        sa.Column('fiscal_postal_code', sa.String(32), nullable=False),
        sa.Column('invoice_usage', sa.String(64), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'customer_id',
            name='uq_customer_fiscal_profiles_scope',
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_customer_fiscal_profiles_status',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_customer_fiscal_profiles_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['customer_id', 'tenant_id'],
            ['customers.id', 'customers.tenant_id'],
            name='fk_customer_fiscal_profiles_customer_scope', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_customer_fiscal_profiles_customer_status',
        'customer_fiscal_profiles',
        ['tenant_id', 'customer_id', 'status', 'id'],
    )

    op.create_table(
        'billing_documents',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_check_id', sa.BigInteger(), nullable=False),
        sa.Column('source_check_version', sa.BigInteger(), nullable=False),
        sa.Column(
            'source_check_fingerprint',
            sa.String(64, collation='ascii_bin'),
            nullable=False,
        ),
        sa.Column(
            'document_type',
            sa.String(16),
            server_default=sa.text("'INVOICE'"),
            nullable=False,
        ),
        sa.Column(
            'status', sa.String(16), server_default=sa.text("'DRAFT'"), nullable=False
        ),
        sa.Column('currency', sa.String(3, collation='ascii_bin'), nullable=False),
        sa.Column('subtotal', sa.Numeric(19, 4), nullable=False),
        sa.Column('discount_total', sa.Numeric(19, 4), nullable=False),
        sa.Column('tax_total', sa.Numeric(19, 4), nullable=False),
        sa.Column('total', sa.Numeric(19, 4), nullable=False),
        sa.Column('issuer_snapshot', sa.JSON(), nullable=False),
        sa.Column('recipient_snapshot', sa.JSON(), nullable=False),
        sa.Column('actor_scope', sa.String(200, collation='ascii_bin'), nullable=False),
        sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_billing_documents_scope',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'actor_scope', 'idempotency_key',
            name='uq_billing_documents_idempotency',
        ),
        sa.CheckConstraint(
            "document_type IN ('INVOICE')",
            name='ck_billing_documents_type',
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT')",
            name='ck_billing_documents_status',
        ),
        sa.CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_billing_documents_currency',
        ),
        sa.CheckConstraint(
            'source_check_version >= 1',
            name='ck_billing_documents_check_version_value',
        ),
        sa.CheckConstraint(
            'subtotal >= 0 AND discount_total >= 0 AND tax_total >= 0 AND total >= 0',
            name='ck_billing_documents_money',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_billing_documents_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_billing_documents_organization_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_billing_documents_location_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['restaurant_check_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_checks.id',
                'restaurant_checks.tenant_id',
                'restaurant_checks.organization_id',
                'restaurant_checks.location_id',
            ],
            name='fk_billing_documents_check_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['restaurant_check_id', 'source_check_version'],
            ['restaurant_check_versions.check_id', 'restaurant_check_versions.version'],
            name='fk_billing_documents_check_version', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_billing_documents_check_history',
        'billing_documents',
        ['tenant_id', 'restaurant_check_id', 'created_at', 'id'],
    )
    op.create_index(
        'ix_billing_documents_organization_status',
        'billing_documents',
        ['tenant_id', 'organization_id', 'status', 'id'],
    )

    op.create_table(
        'billing_document_lines',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('billing_document_id', sa.BigInteger(), nullable=False),
        sa.Column('source_restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('source_restaurant_order_item_id', sa.BigInteger(), nullable=False),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('quantity', sa.Numeric(19, 4), nullable=False),
        sa.Column('unit_price', sa.Numeric(19, 4), nullable=False),
        sa.Column('base_amount', sa.Numeric(19, 4), nullable=False),
        sa.Column('discount_amount', sa.Numeric(19, 4), nullable=False),
        sa.Column('commercial_total', sa.Numeric(19, 4), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            'quantity > 0',
            name='ck_billing_document_lines_quantity',
        ),
        sa.CheckConstraint(
            'unit_price >= 0 AND base_amount >= 0 AND discount_amount >= 0 '
            'AND commercial_total >= 0',
            name='ck_billing_document_lines_money',
        ),
        sa.CheckConstraint(
            'commercial_total = base_amount - discount_amount',
            name='ck_billing_document_lines_arithmetic',
        ),
        sa.ForeignKeyConstraint(
            ['billing_document_id'], ['billing_documents.id'],
            name='fk_billing_document_lines_document', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['source_restaurant_order_id'], ['restaurant_orders.id'],
            name='fk_billing_document_lines_source_order', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['source_restaurant_order_item_id'], ['restaurant_order_items.id'],
            name='fk_billing_document_lines_source_order_item', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_billing_document_lines_document',
        'billing_document_lines',
        ['billing_document_id', 'id'],
    )

    op.create_table(
        'billing_document_line_taxes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('billing_document_line_id', sa.BigInteger(), nullable=False),
        sa.Column('tax_category', sa.String(64), nullable=False),
        sa.Column('tax_rate', sa.Numeric(9, 6), nullable=False),
        sa.Column('taxable_base', sa.Numeric(19, 4), nullable=False),
        sa.Column('tax_amount', sa.Numeric(19, 4), nullable=False),
        sa.Column('tax_treatment', sa.String(32), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            'tax_rate >= 0 AND taxable_base >= 0 AND tax_amount >= 0',
            name='ck_billing_document_line_taxes_values',
        ),
        sa.ForeignKeyConstraint(
            ['billing_document_line_id'], ['billing_document_lines.id'],
            name='fk_billing_document_line_taxes_line', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_billing_document_line_taxes_line',
        'billing_document_line_taxes',
        ['billing_document_line_id', 'id'],
    )


def downgrade() -> None:
    op.drop_table('billing_document_line_taxes')
    op.drop_table('billing_document_lines')
    op.drop_table('billing_documents')
    op.drop_table('customer_fiscal_profiles')
    op.drop_table('issuer_fiscal_profiles')
