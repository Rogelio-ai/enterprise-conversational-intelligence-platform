"""add open-service waiter responsibility foundation

Revision ID: 0059_service_responsibility_foundation
Revises: 0058_table_waiter_assignment_foundation
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0059_service_responsibility_foundation'
down_revision: str | None = '0058_table_waiter_assignment_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}

SERVICE_SCOPE_COLUMNS = [
    'service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id',
]
SERVICE_SCOPE_TARGETS = [
    'restaurant_service_sessions.id',
    'restaurant_service_sessions.tenant_id',
    'restaurant_service_sessions.organization_id',
    'restaurant_service_sessions.location_id',
    'restaurant_service_sessions.resource_id',
]


def upgrade() -> None:
    op.create_table(
        'service_responsible_waiters',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=False),
        sa.Column('service_session_id', sa.BigInteger(), nullable=False),
        sa.Column('waiter_membership_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            'updated_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            SERVICE_SCOPE_COLUMNS, SERVICE_SCOPE_TARGETS,
            name='fk_service_responsible_waiters_service_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['waiter_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_service_responsible_waiters_waiter_tenant', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'service_session_id', 'waiter_membership_id',
            name='uq_service_responsible_waiters_service_waiter',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_service_responsible_waiters_waiter_location',
        'service_responsible_waiters',
        ['tenant_id', 'location_id', 'waiter_membership_id', 'service_session_id'],
    )
    op.create_table(
        'service_responsibility_transitions',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=False),
        sa.Column('service_session_id', sa.BigInteger(), nullable=False),
        sa.Column('operation', sa.String(32, collation='ascii_bin'), nullable=False),
        sa.Column('result_version', sa.BigInteger(), nullable=False),
        sa.Column('before_responsible_membership_ids', sa.JSON(), nullable=False),
        sa.Column('after_responsible_membership_ids', sa.JSON(), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column(
            'idempotency_actor_scope', sa.String(200, collation='ascii_bin'),
            nullable=False,
        ),
        sa.Column(
            'idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False,
        ),
        sa.Column(
            'request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False,
        ),
        sa.Column('source_table_assignment_version', sa.BigInteger(), nullable=True),
        sa.Column(
            'recorded_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            SERVICE_SCOPE_COLUMNS, SERVICE_SCOPE_TARGETS,
            name='fk_service_responsibility_transitions_service_scope',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_service_responsibility_transitions_actor_tenant',
            ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'service_session_id', 'result_version',
            name='uq_service_responsibility_transitions_service_version',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'idempotency_actor_scope', 'idempotency_key',
            name='uq_service_responsibility_transitions_idempotency',
        ),
        sa.CheckConstraint(
            "operation IN ('INITIALIZE','RESPONSIBILITY_UPDATE')",
            name='ck_service_responsibility_transitions_operation',
        ),
        sa.CheckConstraint(
            'result_version >= 1',
            name='ck_service_responsibility_transitions_version',
        ),
        sa.CheckConstraint(
            'source_table_assignment_version IS NULL '
            'OR source_table_assignment_version >= 0',
            name='ck_service_responsibility_transitions_source_version',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_service_responsibility_transitions_scope_time',
        'service_responsibility_transitions',
        ['tenant_id', 'location_id', 'service_session_id', 'recorded_at', 'id'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_service_responsibility_transitions_scope_time',
        table_name='service_responsibility_transitions',
    )
    op.drop_table('service_responsibility_transitions')
    op.drop_index(
        'ix_service_responsible_waiters_waiter_location',
        table_name='service_responsible_waiters',
    )
    op.drop_table('service_responsible_waiters')
