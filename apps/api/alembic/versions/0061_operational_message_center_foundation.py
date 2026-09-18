"""add operational message center persistence foundation

Revision ID: 0061_operational_message_center_foundation
Revises: 0060_preparation_handoff_foundation
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0061_operational_message_center_foundation'
down_revision: str | None = '0060_preparation_handoff_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.add_column(
        'diner_operational_requests',
        sa.Column('acknowledged_by_membership_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'diner_operational_requests',
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'diner_operational_requests',
        sa.Column('preparation_work_id', sa.BigInteger(), nullable=True),
    )
    op.drop_constraint(
        'fk_diner_operational_requests_diner_scope',
        'diner_operational_requests',
        type_='foreignkey',
    )
    op.alter_column(
        'diner_operational_requests',
        'diner_session_id',
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_foreign_key(
        'fk_diner_operational_requests_diner_scope',
        'diner_operational_requests',
        'diner_sessions',
        ['diner_session_id', 'tenant_id', 'organization_id', 'location_id'],
        ['id', 'tenant_id', 'organization_id', 'location_id'],
        ondelete='RESTRICT',
    )
    op.drop_constraint(
        'ck_diner_operational_requests_related_check',
        'diner_operational_requests',
        type_='check',
    )
    op.drop_constraint(
        'ck_diner_operational_requests_type',
        'diner_operational_requests',
        type_='check',
    )
    op.create_check_constraint(
        'ck_diner_operational_requests_type',
        'diner_operational_requests',
        "request_type IN ('HUMAN_ASSISTANCE','CASH_PAYMENT_ASSISTANCE',"
        "'INVOICE_ASSISTANCE','PAID_CHECK_PRINT','PREPARATION_READY')",
    )
    op.create_check_constraint(
        'ck_diner_operational_requests_ownership',
        'diner_operational_requests',
        "(request_type = 'PREPARATION_READY' AND diner_session_id IS NULL "
        "AND preparation_work_id IS NOT NULL AND related_restaurant_check_id IS NULL) OR "
        "(request_type = 'HUMAN_ASSISTANCE' AND diner_session_id IS NOT NULL "
        "AND preparation_work_id IS NULL AND related_restaurant_check_id IS NULL) OR "
        "(request_type IN ('CASH_PAYMENT_ASSISTANCE','INVOICE_ASSISTANCE',"
        "'PAID_CHECK_PRINT') AND diner_session_id IS NOT NULL "
        "AND preparation_work_id IS NULL AND related_restaurant_check_id IS NOT NULL)",
    )
    op.create_check_constraint(
        'ck_diner_operational_requests_acknowledgement_pair',
        'diner_operational_requests',
        '(acknowledged_by_membership_id IS NULL AND acknowledged_at IS NULL) OR '
        '(acknowledged_by_membership_id IS NOT NULL AND acknowledged_at IS NOT NULL)',
    )
    op.create_unique_constraint(
        'uq_diner_operational_requests_preparation_work',
        'diner_operational_requests',
        ['preparation_work_id'],
    )
    op.create_foreign_key(
        'fk_diner_operational_requests_acknowledger',
        'diner_operational_requests',
        'tenant_memberships',
        ['acknowledged_by_membership_id', 'tenant_id'],
        ['id', 'tenant_id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_diner_operational_requests_preparation_work',
        'diner_operational_requests',
        'preparation_works',
        ['preparation_work_id', 'tenant_id'],
        ['id', 'tenant_id'],
        ondelete='RESTRICT',
    )

    op.create_table(
        'operational_request_waiter_states',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('operational_request_id', sa.BigInteger(), nullable=False),
        sa.Column('waiter_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('entered_at', sa.DateTime(), nullable=True),
        sa.Column('hidden_at', sa.DateTime(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            'updated_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ['operational_request_id', 'tenant_id'],
            ['diner_operational_requests.id', 'diner_operational_requests.tenant_id'],
            name='fk_operational_request_waiter_states_request_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['waiter_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_operational_request_waiter_states_waiter_tenant',
            ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'operational_request_id', 'waiter_membership_id',
            name='uq_operational_request_waiter_states_request_waiter',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_operational_request_waiter_states_waiter_view',
        'operational_request_waiter_states',
        ['tenant_id', 'waiter_membership_id', 'hidden_at', 'operational_request_id'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_operational_request_waiter_states_waiter_view',
        table_name='operational_request_waiter_states',
    )
    op.drop_table('operational_request_waiter_states')

    op.drop_constraint(
        'fk_diner_operational_requests_preparation_work',
        'diner_operational_requests',
        type_='foreignkey',
    )
    op.drop_constraint(
        'fk_diner_operational_requests_acknowledger',
        'diner_operational_requests',
        type_='foreignkey',
    )
    op.drop_constraint(
        'uq_diner_operational_requests_preparation_work',
        'diner_operational_requests',
        type_='unique',
    )
    op.drop_constraint(
        'ck_diner_operational_requests_acknowledgement_pair',
        'diner_operational_requests',
        type_='check',
    )
    op.drop_constraint(
        'ck_diner_operational_requests_ownership',
        'diner_operational_requests',
        type_='check',
    )
    op.drop_constraint(
        'ck_diner_operational_requests_type',
        'diner_operational_requests',
        type_='check',
    )
    op.drop_column('diner_operational_requests', 'preparation_work_id')
    op.drop_column('diner_operational_requests', 'acknowledged_at')
    op.drop_column('diner_operational_requests', 'acknowledged_by_membership_id')
    op.drop_constraint(
        'fk_diner_operational_requests_diner_scope',
        'diner_operational_requests',
        type_='foreignkey',
    )
    op.alter_column(
        'diner_operational_requests',
        'diner_session_id',
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_foreign_key(
        'fk_diner_operational_requests_diner_scope',
        'diner_operational_requests',
        'diner_sessions',
        ['diner_session_id', 'tenant_id', 'organization_id', 'location_id'],
        ['id', 'tenant_id', 'organization_id', 'location_id'],
        ondelete='RESTRICT',
    )
    op.create_check_constraint(
        'ck_diner_operational_requests_type',
        'diner_operational_requests',
        "request_type IN ('HUMAN_ASSISTANCE','CASH_PAYMENT_ASSISTANCE',"
        "'INVOICE_ASSISTANCE','PAID_CHECK_PRINT')",
    )
    op.create_check_constraint(
        'ck_diner_operational_requests_related_check',
        'diner_operational_requests',
        "(request_type = 'HUMAN_ASSISTANCE' AND related_restaurant_check_id IS NULL) OR "
        "(request_type <> 'HUMAN_ASSISTANCE' AND related_restaurant_check_id IS NOT NULL)",
    )
