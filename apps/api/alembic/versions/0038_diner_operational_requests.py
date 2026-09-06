"""add durable diner operational requests

Revision ID: 0038_diner_operational_requests
Revises: 0037_paid_check_printing
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0038_diner_operational_requests'
down_revision: str | None = '0037_paid_check_printing'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.create_table(
        'diner_operational_requests',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=False),
        sa.Column('service_session_id', sa.BigInteger(), nullable=False),
        sa.Column('diner_session_id', sa.BigInteger(), nullable=False),
        sa.Column('request_type', sa.String(40), nullable=False),
        sa.Column('status', sa.String(20), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column('related_restaurant_check_id', sa.BigInteger(), nullable=True),
        sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column('resolved_by_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_diner_operational_requests_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'],
            [
                'restaurant_service_sessions.id', 'restaurant_service_sessions.tenant_id',
                'restaurant_service_sessions.organization_id',
                'restaurant_service_sessions.location_id',
                'restaurant_service_sessions.resource_id',
            ],
            name='fk_diner_operational_requests_service_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['diner_session_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'diner_sessions.id', 'diner_sessions.tenant_id',
                'diner_sessions.organization_id', 'diner_sessions.location_id',
            ],
            name='fk_diner_operational_requests_diner_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['related_restaurant_check_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_checks.id', 'restaurant_checks.tenant_id',
                'restaurant_checks.organization_id', 'restaurant_checks.location_id',
            ],
            name='fk_diner_operational_requests_check_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['resolved_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_diner_operational_requests_resolver', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_diner_operational_requests_id_tenant'),
        sa.UniqueConstraint(
            'tenant_id', 'diner_session_id', 'idempotency_key',
            name='uq_diner_operational_requests_idempotency',
        ),
        sa.CheckConstraint(
            "request_type IN ('HUMAN_ASSISTANCE','CASH_PAYMENT_ASSISTANCE',"
            "'INVOICE_ASSISTANCE','PAID_CHECK_PRINT')",
            name='ck_diner_operational_requests_type',
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','ACKNOWLEDGED','COMPLETED','CANCELLED')",
            name='ck_diner_operational_requests_status',
        ),
        sa.CheckConstraint(
            "(request_type = 'HUMAN_ASSISTANCE' AND related_restaurant_check_id IS NULL) OR "
            "(request_type <> 'HUMAN_ASSISTANCE' AND related_restaurant_check_id IS NOT NULL)",
            name='ck_diner_operational_requests_related_check',
        ),
        sa.CheckConstraint(
            "(status IN ('PENDING','ACKNOWLEDGED') AND resolved_at IS NULL "
            "AND resolved_by_membership_id IS NULL) OR "
            "(status IN ('COMPLETED','CANCELLED') AND resolved_at IS NOT NULL "
            "AND resolved_by_membership_id IS NOT NULL)",
            name='ck_diner_operational_requests_resolution',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_diner_operational_requests_staff_queue', 'diner_operational_requests',
        ['tenant_id', 'location_id', 'status', 'created_at', 'id'], unique=False,
    )
    op.create_index(
        'ix_diner_operational_requests_diner_history', 'diner_operational_requests',
        ['tenant_id', 'diner_session_id', 'created_at', 'id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        'ix_diner_operational_requests_diner_history',
        table_name='diner_operational_requests',
    )
    op.drop_index(
        'ix_diner_operational_requests_staff_queue',
        table_name='diner_operational_requests',
    )
    op.drop_table('diner_operational_requests')
