"""add explicit paid RestaurantCheck printing dispatches

Revision ID: 0037_paid_check_printing
Revises: 0036_restaurant_order_consumption
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0037_paid_check_printing'
down_revision: str | None = '0036_restaurant_order_consumption'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.create_table(
        'paid_check_dispatches',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_check_id', sa.BigInteger(), nullable=False),
        sa.Column('check_version', sa.BigInteger(), nullable=False),
        sa.Column(
            'check_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False,
        ),
        sa.Column('cashier_resource_id', sa.BigInteger(), nullable=False),
        sa.Column('cashier_resource_code_snapshot', sa.String(64), nullable=False),
        sa.Column('cashier_resource_name_snapshot', sa.String(200), nullable=False),
        sa.Column('connector_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'connector_code_snapshot',
            sa.String(64, collation='utf8mb4_bin'), nullable=False,
        ),
        sa.Column('connector_name_snapshot', sa.String(200), nullable=False),
        sa.Column(
            'local_target_key_snapshot',
            sa.String(128, collation='utf8mb4_bin'), nullable=False,
        ),
        sa.Column(
            'operation_id', sa.String(128, collation='ascii_bin'), nullable=False,
        ),
        sa.Column(
            'actor_scope', sa.String(200, collation='ascii_bin'), nullable=False,
        ),
        sa.Column(
            'idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False,
        ),
        sa.Column(
            'request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False,
        ),
        sa.Column(
            'state', sa.String(40), server_default=sa.text("'PENDING'"), nullable=False,
        ),
        sa.Column(
            'payload_schema', sa.String(64, collation='ascii_bin'), nullable=False,
        ),
        sa.Column('payload_text', sa.Text(collation='utf8mb4_bin'), nullable=False),
        sa.Column(
            'payload_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False,
        ),
        sa.Column('claim_token', sa.String(36, collation='ascii_bin'), nullable=True),
        sa.Column('claim_expires_at', sa.DateTime(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('available_at', sa.DateTime(), nullable=False),
        sa.Column('last_error_kind', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('last_error_message', sa.String(500), nullable=True),
        sa.Column('created_by_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column('terminal_at', sa.DateTime(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_paid_check_dispatches_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['restaurant_check_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_checks.id', 'restaurant_checks.tenant_id',
                'restaurant_checks.organization_id', 'restaurant_checks.location_id',
            ],
            name='fk_paid_check_dispatches_check_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['cashier_resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_paid_check_dispatches_resource_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['connector_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'preparation_delivery_connectors.id',
                'preparation_delivery_connectors.tenant_id',
                'preparation_delivery_connectors.organization_id',
                'preparation_delivery_connectors.location_id',
            ],
            name='fk_paid_check_dispatches_connector_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['created_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_paid_check_dispatches_membership', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'id', 'tenant_id', name='uq_paid_check_dispatches_id_tenant',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'operation_id', name='uq_paid_check_dispatches_operation',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'actor_scope', 'idempotency_key',
            name='uq_paid_check_dispatches_idempotency',
        ),
        sa.CheckConstraint(
            'check_version >= 1', name='ck_paid_check_dispatches_check_version',
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','IN_PROGRESS','DESTINATION_SUBMISSION_ACCEPTED',"
            "'RETRYABLE_FAILURE','UNCERTAIN','ACTION_REQUIRED')",
            name='ck_paid_check_dispatches_state',
        ),
        sa.CheckConstraint(
            'attempt_count >= 0', name='ck_paid_check_dispatches_attempt_count',
        ),
        sa.CheckConstraint(
            "(state = 'IN_PROGRESS' AND claim_token IS NOT NULL AND claim_expires_at IS NOT NULL) "
            "OR (state <> 'IN_PROGRESS' AND claim_token IS NULL AND claim_expires_at IS NULL)",
            name='ck_paid_check_dispatches_claim',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_paid_check_dispatches_eligibility', 'paid_check_dispatches',
        ['tenant_id', 'location_id', 'connector_id', 'state', 'available_at', 'id'],
        unique=False,
    )
    op.create_index(
        'ix_paid_check_dispatches_check', 'paid_check_dispatches',
        ['tenant_id', 'restaurant_check_id', 'created_at', 'id'], unique=False,
    )

    op.create_table(
        'paid_check_dispatch_attempts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('dispatch_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_id', sa.BigInteger(), nullable=False),
        sa.Column('attempt_sequence', sa.Integer(), nullable=False),
        sa.Column('attempt_type', sa.String(16), nullable=False),
        sa.Column(
            'claim_token', sa.String(36, collation='ascii_bin'), nullable=False,
        ),
        sa.Column(
            'claim_request_id', sa.String(128, collation='ascii_bin'), nullable=True,
        ),
        sa.Column('actor_principal_reference', sa.String(128), nullable=False),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column(
            'result', sa.String(40),
            server_default=sa.text("'IN_PROGRESS'"), nullable=False,
        ),
        sa.Column(
            'result_fingerprint', sa.String(64, collation='ascii_bin'), nullable=True,
        ),
        sa.Column(
            'local_job_reference',
            sa.String(200, collation='utf8mb4_bin'), nullable=True,
        ),
        sa.Column('error_kind', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['dispatch_id', 'tenant_id'],
            ['paid_check_dispatches.id', 'paid_check_dispatches.tenant_id'],
            name='fk_paid_check_attempts_dispatch_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['connector_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'preparation_delivery_connectors.id',
                'preparation_delivery_connectors.tenant_id',
                'preparation_delivery_connectors.organization_id',
                'preparation_delivery_connectors.location_id',
            ],
            name='fk_paid_check_attempts_connector_scope', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'dispatch_id', 'attempt_sequence', name='uq_paid_check_attempts_sequence',
        ),
        sa.UniqueConstraint('claim_token', name='uq_paid_check_attempts_claim'),
        sa.UniqueConstraint(
            'tenant_id', 'connector_id', 'claim_request_id',
            name='uq_paid_check_attempts_claim_request',
        ),
        sa.CheckConstraint(
            "attempt_type IN ('DELIVER','RETRY','RECOVERY')",
            name='ck_paid_check_attempts_type',
        ),
        sa.CheckConstraint(
            "result IN ('IN_PROGRESS','DESTINATION_SUBMISSION_ACCEPTED',"
            "'RETRYABLE_FAILURE','UNCERTAIN','ACTION_REQUIRED')",
            name='ck_paid_check_attempts_result',
        ),
        sa.CheckConstraint(
            "(result = 'IN_PROGRESS' AND ended_at IS NULL AND result_fingerprint IS NULL) "
            "OR (result <> 'IN_PROGRESS' AND ended_at IS NOT NULL AND result_fingerprint IS NOT NULL)",
            name='ck_paid_check_attempts_lifecycle',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_paid_check_attempts_ordered', 'paid_check_dispatch_attempts',
        ['tenant_id', 'dispatch_id', 'attempt_sequence', 'id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_paid_check_attempts_ordered', table_name='paid_check_dispatch_attempts',
    )
    op.drop_table('paid_check_dispatch_attempts')
    op.drop_index(
        'ix_paid_check_dispatches_check', table_name='paid_check_dispatches',
    )
    op.drop_index(
        'ix_paid_check_dispatches_eligibility', table_name='paid_check_dispatches',
    )
    op.drop_table('paid_check_dispatches')
