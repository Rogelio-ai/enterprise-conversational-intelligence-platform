"""add canonical Staff authentication sessions

Revision ID: 0065_staff_auth_session_foundation
Revises: 0064_location_scoped_staff_rbac
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0065_staff_auth_session_foundation'
down_revision: str | None = '0064_location_scoped_staff_rbac'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_tenant_memberships_id_tenant_user',
        'tenant_memberships',
        ['id', 'tenant_id', 'user_id'],
    )
    op.create_table(
        'staff_auth_sessions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            'session_id', sa.String(36, collation='ascii_bin'), nullable=False,
        ),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('membership_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'status', sa.String(16), server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            'active_slot', sa.SmallInteger(), server_default=sa.text('1'),
            nullable=True,
        ),
        sa.Column(
            'activated_at', sa.DateTime(), nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(), nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column(
            'updated_at', sa.DateTime(), nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.ForeignKeyConstraint(
            ['membership_id', 'tenant_id', 'user_id'],
            [
                'tenant_memberships.id',
                'tenant_memberships.tenant_id',
                'tenant_memberships.user_id',
            ],
            name='fk_staff_auth_sessions_membership_scope',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'session_id', name='uq_staff_auth_sessions_public_id',
        ),
        sa.UniqueConstraint(
            'user_id', 'active_slot', name='uq_staff_auth_sessions_user_active',
        ),
        sa.CheckConstraint(
            'active_slot IS NULL OR active_slot = 1',
            name='ck_staff_auth_sessions_active_slot',
        ),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND active_slot = 1 AND closed_at IS NULL) OR "
            "(status IN ('REPLACED', 'CLOSED') AND active_slot IS NULL "
            'AND closed_at IS NOT NULL)',
            name='ck_staff_auth_sessions_lifecycle',
        ),
    )
    op.create_index(
        'ix_staff_auth_sessions_lookup',
        'staff_auth_sessions',
        ['session_id', 'status', 'active_slot'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_staff_auth_sessions_lookup', table_name='staff_auth_sessions',
    )
    op.drop_table('staff_auth_sessions')
    op.drop_constraint(
        'uq_tenant_memberships_id_tenant_user',
        'tenant_memberships',
        type_='unique',
    )
