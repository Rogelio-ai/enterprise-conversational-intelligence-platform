"""persist authoritative fiscal results and artifact metadata

Revision ID: 0031_fiscal_result_artifact_persistence
Revises: 0030_billing_cfdi_readiness_snapshot
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0031_fiscal_result_artifact_persistence'
down_revision: str | None = '0030_billing_cfdi_readiness_snapshot'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'billing_fiscal_results',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('billing_document_id', sa.BigInteger(), nullable=False),
        sa.Column('billing_issuance_id', sa.BigInteger(), nullable=False),
        sa.Column('successful_attempt_sequence', sa.Integer(), nullable=False),
        sa.Column('provider_key', sa.String(128, collation='utf8mb4_bin'), nullable=False),
        sa.Column(
            'external_fiscal_identifier',
            sa.String(200, collation='utf8mb4_bin'), nullable=False,
        ),
        sa.Column(
            'provider_external_reference',
            sa.String(200, collation='utf8mb4_bin'), nullable=False,
        ),
        sa.Column('fiscal_document_type', sa.String(64), nullable=False),
        sa.Column('fiscal_document_version', sa.String(32), nullable=False),
        sa.Column('issued_at', sa.DateTime(), nullable=False),
        sa.Column(
            'result_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False
        ),
        sa.Column(
            'created_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            'successful_attempt_sequence >= 1',
            name='ck_billing_fiscal_results_attempt_sequence',
        ),
        sa.ForeignKeyConstraint(
            ['billing_issuance_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'billing_issuances.id',
                'billing_issuances.tenant_id',
                'billing_issuances.organization_id',
                'billing_issuances.location_id',
            ],
            name='fk_billing_fiscal_results_issuance_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['billing_document_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'billing_documents.id',
                'billing_documents.tenant_id',
                'billing_documents.organization_id',
                'billing_documents.location_id',
            ],
            name='fk_billing_fiscal_results_document_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['billing_issuance_id', 'successful_attempt_sequence'],
            [
                'billing_issuance_attempts.billing_issuance_id',
                'billing_issuance_attempts.attempt_sequence',
            ],
            name='fk_billing_fiscal_results_success_attempt', ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_billing_fiscal_results_scope',
        ),
        sa.UniqueConstraint(
            'billing_issuance_id', name='uq_billing_fiscal_results_issuance'
        ),
        sa.UniqueConstraint(
            'tenant_id', 'provider_key', 'external_fiscal_identifier',
            name='uq_billing_fiscal_results_external_identity',
        ),
    )
    op.create_index(
        'ix_billing_fiscal_results_document', 'billing_fiscal_results',
        ['tenant_id', 'billing_document_id', 'id'], unique=False,
    )

    op.create_table(
        'billing_fiscal_artifacts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('fiscal_result_id', sa.BigInteger(), nullable=False),
        sa.Column('artifact_kind', sa.String(64), nullable=False),
        sa.Column('media_type', sa.String(128), nullable=False),
        sa.Column('storage_strategy', sa.String(64), nullable=False),
        sa.Column(
            'storage_reference', sa.String(500, collation='utf8mb4_bin'), nullable=False
        ),
        sa.Column(
            'content_hash', sa.String(64, collation='ascii_bin'), nullable=False
        ),
        sa.Column('byte_size', sa.BigInteger(), nullable=False),
        sa.Column(
            'provider_artifact_reference',
            sa.String(500, collation='utf8mb4_bin'), nullable=True,
        ),
        sa.Column(
            'created_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.CheckConstraint(
            'byte_size > 0', name='ck_billing_fiscal_artifacts_byte_size'
        ),
        sa.ForeignKeyConstraint(
            ['fiscal_result_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'billing_fiscal_results.id',
                'billing_fiscal_results.tenant_id',
                'billing_fiscal_results.organization_id',
                'billing_fiscal_results.location_id',
            ],
            name='fk_billing_fiscal_artifacts_result_scope', ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'fiscal_result_id', 'artifact_kind',
            name='uq_billing_fiscal_artifacts_kind',
        ),
    )
    op.create_index(
        'ix_billing_fiscal_artifacts_result', 'billing_fiscal_artifacts',
        ['tenant_id', 'fiscal_result_id', 'id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_billing_fiscal_artifacts_result', table_name='billing_fiscal_artifacts'
    )
    op.drop_table('billing_fiscal_artifacts')
    op.drop_index(
        'ix_billing_fiscal_results_document', table_name='billing_fiscal_results'
    )
    op.drop_table('billing_fiscal_results')
