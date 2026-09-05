"""freeze billing fiscal-readiness evidence

Revision ID: 0030_billing_cfdi_readiness_snapshot
Revises: 0029_canonical_fiscal_monetary_tax_effect
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0030_billing_cfdi_readiness_snapshot'
down_revision: str | None = '0029_canonical_fiscal_monetary_tax_effect'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'billing_documents',
        sa.Column('issuer_fiscal_postal_code', sa.String(32), nullable=True),
    )
    op.add_column(
        'billing_documents',
        sa.Column(
            'readiness_evidence_fingerprint',
            sa.String(64, collation='ascii_bin'),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        'ck_billing_documents_fiscal_readiness',
        'billing_documents',
        '(issuer_fiscal_postal_code IS NULL AND readiness_evidence_fingerprint IS NULL) '
        'OR (issuer_fiscal_postal_code IS NOT NULL '
        'AND readiness_evidence_fingerprint IS NOT NULL)',
    )

    line_columns = (
        sa.Column(
            'fiscal_product_classification_scheme',
            sa.String(64, collation='utf8mb4_bin'), nullable=True,
        ),
        sa.Column(
            'fiscal_product_classification_code',
            sa.String(64, collation='utf8mb4_bin'), nullable=True,
        ),
        sa.Column(
            'fiscal_unit_classification_scheme',
            sa.String(64, collation='utf8mb4_bin'), nullable=True,
        ),
        sa.Column(
            'fiscal_unit_classification_code',
            sa.String(64, collation='utf8mb4_bin'), nullable=True,
        ),
        sa.Column('fiscal_unit_value', sa.Numeric(19, 4), nullable=True),
        sa.Column('fiscal_line_amount', sa.Numeric(19, 4), nullable=True),
        sa.Column('fiscal_discount_amount', sa.Numeric(19, 4), nullable=True),
        sa.Column(
            'source_fiscal_evidence_fingerprint',
            sa.String(64, collation='ascii_bin'), nullable=True,
        ),
    )
    for column in line_columns:
        op.add_column('billing_document_lines', column)
    op.create_check_constraint(
        'ck_billing_document_lines_fiscal_evidence',
        'billing_document_lines',
        '(fiscal_product_classification_scheme IS NULL '
        'AND fiscal_product_classification_code IS NULL '
        'AND fiscal_unit_classification_scheme IS NULL '
        'AND fiscal_unit_classification_code IS NULL '
        'AND fiscal_unit_value IS NULL AND fiscal_line_amount IS NULL '
        'AND fiscal_discount_amount IS NULL '
        'AND source_fiscal_evidence_fingerprint IS NULL) OR '
        '(fiscal_product_classification_scheme IS NOT NULL '
        'AND fiscal_product_classification_code IS NOT NULL '
        'AND fiscal_unit_classification_scheme IS NOT NULL '
        'AND fiscal_unit_classification_code IS NOT NULL '
        'AND fiscal_unit_value IS NOT NULL AND fiscal_line_amount IS NOT NULL '
        'AND fiscal_discount_amount IS NOT NULL '
        'AND source_fiscal_evidence_fingerprint IS NOT NULL '
        'AND fiscal_unit_value >= 0 AND fiscal_line_amount >= 0 '
        'AND fiscal_discount_amount >= 0)',
    )

    op.add_column(
        'billing_document_line_taxes',
        sa.Column(
            'jurisdiction_code', sa.String(64, collation='utf8mb4_bin'), nullable=True
        ),
    )
    op.add_column(
        'billing_document_line_taxes',
        sa.Column('tax_effect', sa.String(16), nullable=True),
    )
    op.add_column(
        'billing_document_line_taxes',
        sa.Column(
            'source_tax_evidence_fingerprint',
            sa.String(64, collation='ascii_bin'), nullable=True,
        ),
    )
    op.create_check_constraint(
        'ck_billing_document_line_taxes_fiscal_evidence',
        'billing_document_line_taxes',
        '(jurisdiction_code IS NULL AND tax_effect IS NULL '
        'AND source_tax_evidence_fingerprint IS NULL) OR '
        '(jurisdiction_code IS NOT NULL AND tax_effect IS NOT NULL '
        'AND source_tax_evidence_fingerprint IS NOT NULL '
        "AND tax_effect IN ('TRANSFERRED','WITHHELD'))",
    )


def downgrade() -> None:
    op.drop_constraint(
        'ck_billing_document_line_taxes_fiscal_evidence',
        'billing_document_line_taxes', type_='check',
    )
    op.drop_column('billing_document_line_taxes', 'source_tax_evidence_fingerprint')
    op.drop_column('billing_document_line_taxes', 'tax_effect')
    op.drop_column('billing_document_line_taxes', 'jurisdiction_code')

    op.drop_constraint(
        'ck_billing_document_lines_fiscal_evidence',
        'billing_document_lines', type_='check',
    )
    for name in (
        'source_fiscal_evidence_fingerprint',
        'fiscal_discount_amount',
        'fiscal_line_amount',
        'fiscal_unit_value',
        'fiscal_unit_classification_code',
        'fiscal_unit_classification_scheme',
        'fiscal_product_classification_code',
        'fiscal_product_classification_scheme',
    ):
        op.drop_column('billing_document_lines', name)

    op.drop_constraint(
        'ck_billing_documents_fiscal_readiness',
        'billing_documents', type_='check',
    )
    op.drop_column('billing_documents', 'readiness_evidence_fingerprint')
    op.drop_column('billing_documents', 'issuer_fiscal_postal_code')
