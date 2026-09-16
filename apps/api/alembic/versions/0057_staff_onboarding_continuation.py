"""add secret-free Staff onboarding continuation

Revision ID: 0057_staff_onboarding_continuation
Revises: 0056_identity_invitation_foundation
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0057_staff_onboarding_continuation'
down_revision: str | None = '0056_identity_invitation_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.create_table(
        'onboarding_staff_continuations',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            'continuation_id', sa.String(36, collation='ascii_bin'), nullable=False,
        ),
        sa.Column('onboarding_import_id', sa.BigInteger(), nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('identity_invitation_id', sa.BigInteger(), nullable=True),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column(
            'staff_key', sa.String(100, collation='utf8mb4_bin'), nullable=False,
        ),
        sa.Column(
            'normalized_email', sa.String(320, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column(
            'role_name', sa.String(100, collation='utf8mb4_bin'), nullable=False,
        ),
        sa.Column('requested_permission_codes', sa.JSON(), nullable=False),
        sa.Column(
            'status', sa.String(32, collation='ascii_bin'), nullable=False,
        ),
        sa.Column(
            'completion_operation', sa.String(16, collation='ascii_bin'), nullable=True,
        ),
        sa.Column(
            'error_code', sa.String(64, collation='ascii_bin'), nullable=True,
        ),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            'updated_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ['onboarding_import_id'], ['onboarding_imports.id'],
            name='fk_staff_continuations_import', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_staff_continuations_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_staff_continuations_organization_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_staff_continuations_location_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_staff_continuations_actor_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['identity_invitation_id'], ['identity_invitations.id'],
            name='fk_staff_continuations_invitation', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name='fk_staff_continuations_user', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'continuation_id', name='uq_staff_continuations_public_id',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'normalized_email', 'role_name', 'location_id',
            name='uq_staff_continuations_logical_request',
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_ACCEPTANCE','COMPLETE','SECURITY_CONFLICT','TERMINAL_FAILURE')",
            name='ck_staff_continuations_status',
        ),
        sa.CheckConstraint(
            "completion_operation IS NULL OR completion_operation IN ('CREATE','UNCHANGED')",
            name='ck_staff_continuations_completion_operation',
        ),
        sa.CheckConstraint(
            "(status='PENDING_ACCEPTANCE' AND identity_invitation_id IS NOT NULL "
            "AND user_id IS NULL AND completion_operation IS NULL "
            "AND error_code IS NULL AND completed_at IS NULL) OR "
            "(status='COMPLETE' AND user_id IS NOT NULL "
            "AND completion_operation IS NOT NULL AND error_code IS NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status='SECURITY_CONFLICT' AND completion_operation IS NULL "
            "AND error_code IS NOT NULL AND completed_at IS NULL) OR "
            "(status='TERMINAL_FAILURE' AND completion_operation IS NULL "
            "AND error_code IS NOT NULL AND completed_at IS NOT NULL)",
            name='ck_staff_continuations_lifecycle',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_staff_continuations_resume', 'onboarding_staff_continuations',
        ['tenant_id', 'status', 'normalized_email', 'id'],
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text(
        'SELECT COUNT(*) FROM onboarding_staff_continuations'
    )).scalar_one():
        raise RuntimeError(
            'Cannot downgrade 0057 while Staff continuations exist'
        )
    op.drop_index(
        'ix_staff_continuations_resume',
        table_name='onboarding_staff_continuations',
    )
    op.drop_table('onboarding_staff_continuations')
