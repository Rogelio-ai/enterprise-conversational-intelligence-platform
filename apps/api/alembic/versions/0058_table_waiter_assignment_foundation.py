"""add table waiter assignment and shared responsibility foundation

Revision ID: 0058_table_waiter_assignment_foundation
Revises: 0057_staff_onboarding_continuation
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0058_table_waiter_assignment_foundation'
down_revision: str | None = '0057_staff_onboarding_continuation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.create_table(
        'table_waiter_assignments',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('table_resource_id', sa.BigInteger(), nullable=False),
        sa.Column('waiter_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('is_responsible', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(
            ['table_resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_table_waiter_assignments_table_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['waiter_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_table_waiter_assignments_waiter_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['waiter_membership_id', 'location_id'],
            ['membership_location_grants.membership_id', 'membership_location_grants.location_id'],
            name='fk_table_waiter_assignments_waiter_location', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'table_resource_id', 'waiter_membership_id',
            name='uq_table_waiter_assignments_table_waiter',
        ),
        sa.CheckConstraint('is_responsible IN (0, 1)', name='ck_table_waiter_assignments_responsible'),
        **OPTIONS,
    )
    op.create_index(
        'ix_table_waiter_assignments_waiter_location', 'table_waiter_assignments',
        ['tenant_id', 'location_id', 'waiter_membership_id', 'table_resource_id'],
    )
    op.create_table(
        'table_waiter_assignment_audits',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('table_resource_id', sa.BigInteger(), nullable=False),
        sa.Column('waiter_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('operation', sa.String(32, collation='ascii_bin'), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('result_version', sa.BigInteger(), nullable=False),
        sa.Column('assigned_membership_ids', sa.JSON(), nullable=False),
        sa.Column('responsible_membership_ids', sa.JSON(), nullable=False),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column('recorded_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(
            ['table_resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_table_waiter_audits_table_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['waiter_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_table_waiter_audits_waiter_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_table_waiter_audits_actor_tenant', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'table_resource_id', 'result_version',
            name='uq_table_waiter_audits_table_version',
        ),
        sa.CheckConstraint(
            "operation IN ('ASSIGN','UNASSIGN','RESPONSIBILITY_UPDATE')",
            name='ck_table_waiter_audits_operation',
        ),
        sa.CheckConstraint('result_version >= 1', name='ck_table_waiter_audits_version'),
        **OPTIONS,
    )
    op.create_index(
        'ix_table_waiter_audits_scope_time', 'table_waiter_assignment_audits',
        ['tenant_id', 'location_id', 'table_resource_id', 'recorded_at', 'id'],
    )


def downgrade() -> None:
    op.drop_index('ix_table_waiter_audits_scope_time', table_name='table_waiter_assignment_audits')
    op.drop_table('table_waiter_assignment_audits')
    op.drop_index('ix_table_waiter_assignments_waiter_location', table_name='table_waiter_assignments')
    op.drop_table('table_waiter_assignments')
