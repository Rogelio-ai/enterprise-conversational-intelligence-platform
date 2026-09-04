"""establish fiscal issuance persistence foundation

Revision ID: 0027_fiscal_issuance_foundation
Revises: 0026_authoritative_tax_evidence
Create Date: 2026-09-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0027_fiscal_issuance_foundation'
down_revision: str | None = '0026_authoritative_tax_evidence'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _options() -> dict[str, str]:
    return {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
        'mysql_collate': 'utf8mb4_unicode_ci',
    }


def _created_at() -> sa.Column:
    return sa.Column(
        'created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'),
        nullable=False,
    )


def _updated_at() -> sa.Column:
    return sa.Column(
        'updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'),
        nullable=False,
    )


def upgrade() -> None:
    options = _options()
    op.create_table(
        'billing_issuances',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('billing_document_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'provider_key', sa.String(128, collation='utf8mb4_bin'), nullable=False,
        ),
        sa.Column(
            'credential_binding', sa.String(200, collation='utf8mb4_bin'),
            nullable=True,
        ),
        sa.Column(
            'state', sa.String(16), server_default=sa.text("'PENDING'"), nullable=False,
        ),
        sa.Column('actor_scope', sa.String(200, collation='ascii_bin'), nullable=False),
        sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column(
            'request_schema_version', sa.Integer(), server_default=sa.text('1'),
            nullable=False,
        ),
        sa.Column('request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column(
            'provider_idempotency_key', sa.String(128, collation='ascii_bin'),
            nullable=False,
        ),
        sa.Column(
            'external_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True,
        ),
        sa.Column('external_status', sa.String(64), nullable=True),
        sa.Column('claim_token', sa.String(36, collation='ascii_bin'), nullable=True),
        sa.Column('claim_expires_at', sa.DateTime(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_error_kind', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('last_error_message', sa.String(500), nullable=True),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_billing_issuances_scope',
        ),
        sa.UniqueConstraint(
            'billing_document_id', name='uq_billing_issuances_document',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'actor_scope', 'idempotency_key',
            name='uq_billing_issuances_idempotency',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'provider_key', 'provider_idempotency_key',
            name='uq_billing_issuances_provider_operation',
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','IN_PROGRESS','SUCCEEDED','FAILED','REJECTED','UNCERTAIN')",
            name='ck_billing_issuances_state',
        ),
        sa.CheckConstraint(
            'request_schema_version >= 1 AND attempt_count >= 0',
            name='ck_billing_issuances_versions',
        ),
        sa.CheckConstraint(
            "(state='IN_PROGRESS' AND claim_token IS NOT NULL AND claim_expires_at IS NOT NULL) OR "
            "(state<>'IN_PROGRESS' AND claim_token IS NULL AND claim_expires_at IS NULL)",
            name='ck_billing_issuances_claim',
        ),
        sa.CheckConstraint(
            "(state IN ('SUCCEEDED','REJECTED') AND completed_at IS NOT NULL) OR "
            "(state NOT IN ('SUCCEEDED','REJECTED') AND completed_at IS NULL)",
            name='ck_billing_issuances_lifecycle',
        ),
        sa.CheckConstraint(
            "state<>'SUCCEEDED' OR external_reference IS NOT NULL",
            name='ck_billing_issuances_success',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_billing_issuances_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_billing_issuances_organization_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_billing_issuances_location_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['billing_document_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'billing_documents.id', 'billing_documents.tenant_id',
                'billing_documents.organization_id', 'billing_documents.location_id',
            ],
            name='fk_billing_issuances_document_scope', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_billing_issuances_state', 'billing_issuances',
        ['tenant_id', 'state', 'requested_at', 'id'],
    )
    op.create_index(
        'ix_billing_issuances_claim', 'billing_issuances',
        ['tenant_id', 'state', 'claim_expires_at', 'id'],
    )
    op.create_index(
        'ix_billing_issuances_external', 'billing_issuances',
        ['tenant_id', 'provider_key', 'external_reference', 'id'],
    )

    op.create_table(
        'billing_issuance_attempts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('billing_issuance_id', sa.BigInteger(), nullable=False),
        sa.Column('attempt_sequence', sa.Integer(), nullable=False),
        sa.Column('attempt_type', sa.String(16), nullable=False),
        sa.Column('claim_token', sa.String(36, collation='ascii_bin'), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.String(16), nullable=True),
        sa.Column(
            'external_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True,
        ),
        sa.Column('external_status', sa.String(64), nullable=True),
        sa.Column('error_kind', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('result_fingerprint', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('actor_type', sa.String(24), nullable=True),
        sa.Column('actor_id', sa.BigInteger(), nullable=True),
        sa.Column(
            'actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True,
        ),
        sa.Column('correlation_id', sa.String(128, collation='ascii_bin'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'billing_issuance_id', 'attempt_sequence',
            name='uq_billing_issuance_attempts_sequence',
        ),
        sa.UniqueConstraint(
            'claim_token', name='uq_billing_issuance_attempts_claim',
        ),
        sa.CheckConstraint(
            "attempt_type IN ('ISSUE','RETRY','RECOVER')",
            name='ck_billing_issuance_attempts_type',
        ),
        sa.CheckConstraint(
            "result IS NULL OR result IN ('SUCCEEDED','FAILED','REJECTED','UNCERTAIN')",
            name='ck_billing_issuance_attempts_result',
        ),
        sa.CheckConstraint(
            'attempt_sequence >= 1', name='ck_billing_issuance_attempts_sequence',
        ),
        sa.CheckConstraint(
            '(result IS NULL AND completed_at IS NULL) OR '
            '(result IS NOT NULL AND completed_at IS NOT NULL)',
            name='ck_billing_issuance_attempts_lifecycle',
        ),
        sa.CheckConstraint(
            "actor_type IS NULL OR actor_type IN "
            "('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')",
            name='ck_billing_issuance_attempts_actor',
        ),
        sa.ForeignKeyConstraint(
            ['billing_issuance_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'billing_issuances.id', 'billing_issuances.tenant_id',
                'billing_issuances.organization_id', 'billing_issuances.location_id',
            ],
            name='fk_billing_issuance_attempts_issuance_scope', ondelete='RESTRICT',
        ),
        **options,
    )
    op.create_index(
        'ix_billing_issuance_attempts_ordered', 'billing_issuance_attempts',
        ['tenant_id', 'billing_issuance_id', 'attempt_sequence', 'id'],
    )


def downgrade() -> None:
    op.drop_table('billing_issuance_attempts')
    op.drop_table('billing_issuances')
