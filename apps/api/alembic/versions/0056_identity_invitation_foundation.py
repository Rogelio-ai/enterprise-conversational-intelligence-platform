"""add credential-free identity invitation foundation

Revision ID: 0056_identity_invitation_foundation
Revises: 0055_menu_section_import_binding
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0056_identity_invitation_foundation'
down_revision: str | None = '0055_menu_section_import_binding'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.create_table(
        'identity_invitations',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            'invitation_id', sa.String(36, collation='ascii_bin'), nullable=False,
        ),
        sa.Column('inviter_tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('created_by_user_id', sa.BigInteger(), nullable=False),
        sa.Column('accepted_user_id', sa.BigInteger(), nullable=True),
        sa.Column(
            'email', sa.String(320, collation='utf8mb4_bin'), nullable=False,
        ),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column(
            'secret_digest', sa.String(64, collation='ascii_bin'), nullable=False,
        ),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column(
            'active_slot', sa.SmallInteger(), nullable=True,
            server_default=sa.text('1'),
        ),
        sa.Column(
            'created_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            'updated_at', sa.DateTime(), nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.ForeignKeyConstraint(
            ['inviter_tenant_id'], ['tenants.id'],
            name='fk_identity_invitations_tenant', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['created_by_user_id'], ['users.id'],
            name='fk_identity_invitations_creator', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['accepted_user_id'], ['users.id'],
            name='fk_identity_invitations_accepted_user', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint(
            'invitation_id', name='uq_identity_invitations_public_id',
        ),
        sa.UniqueConstraint(
            'email', 'active_slot', name='uq_identity_invitations_active_email',
        ),
        sa.CheckConstraint(
            'active_slot IS NULL OR active_slot = 1',
            name='ck_identity_invitations_active_slot',
        ),
        sa.CheckConstraint(
            'consumed_at IS NULL OR revoked_at IS NULL',
            name='ck_identity_invitations_terminal_state',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_identity_invitations_lookup', 'identity_invitations',
        ['invitation_id', 'active_slot', 'expires_at'],
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text(
        'SELECT COUNT(*) FROM identity_invitations'
    )).scalar_one():
        raise RuntimeError('Cannot downgrade 0056 while Identity Invitations exist')
    op.drop_index(
        'ix_identity_invitations_lookup', table_name='identity_invitations',
    )
    op.drop_table('identity_invitations')
