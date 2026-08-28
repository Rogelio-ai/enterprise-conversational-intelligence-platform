"""establish Restaurant service session and diner access foundation

Revision ID: 0015_restaurant_service_diner_access_foundation
Revises: 0014_commercial_resolution_foundation
Create Date: 2026-08-27
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0015_restaurant_service_diner_access_foundation'
down_revision: str | None = '0014_commercial_resolution_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WS_16_PERMISSIONS = {
    'restaurant_service.read': 'Read Restaurant service sessions.',
    'restaurant_service.manage': 'Manage Restaurant service sessions.',
}


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def _options() -> dict[str, str]:
    return {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}


def _seed_permissions() -> None:
    connection = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.BigInteger()), sa.column('code', sa.String()), sa.column('description', sa.String()))
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()), sa.column('status', sa.String()))
    grants = sa.table('role_permissions', sa.column('id', sa.BigInteger()), sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()))
    role_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE')).scalars())
    for code, description in WS_16_PERMISSIONS.items():
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(code=code, description=description))
            permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one()
        for role_id in role_ids:
            if connection.execute(sa.select(grants.c.id).where(grants.c.role_id == role_id, grants.c.permission_id == permission_id)).scalar_one_or_none() is None:
                connection.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_conversations_id_full_scope', 'conversations',
        ['id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'],
    )
    options = _options()
    op.create_table(
        'restaurant_service_sessions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=False),
        sa.Column('party_size', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column('open_slot', sa.SmallInteger(), server_default=sa.text('1'), nullable=True),
        sa.Column('join_context_key', sa.String(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column('access_code_digest', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('access_code_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('failed_join_attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('failed_window_started_at', sa.DateTime(), nullable=True),
        sa.Column('join_locked_until', sa.DateTime(), nullable=True),
        sa.Column('opened_by_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('closed_by_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name='ck_restaurant_service_sessions_status'),
        sa.CheckConstraint('party_size BETWEEN 1 AND 999', name='ck_restaurant_service_sessions_party_size'),
        sa.CheckConstraint('access_code_version >= 1', name='ck_restaurant_service_sessions_code_version'),
        sa.CheckConstraint('failed_join_attempts >= 0', name='ck_restaurant_service_sessions_failed_attempts'),
        sa.CheckConstraint('open_slot IS NULL OR open_slot = 1', name='ck_restaurant_service_sessions_open_slot'),
        sa.CheckConstraint(
            "(status = 'OPEN' AND open_slot = 1 AND access_code_digest IS NOT NULL AND closed_at IS NULL AND closed_by_membership_id IS NULL) OR "
            "(status = 'CLOSED' AND open_slot IS NULL AND access_code_digest IS NULL AND closed_at IS NOT NULL AND closed_by_membership_id IS NOT NULL)",
            name='ck_restaurant_service_sessions_lifecycle',
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_restaurant_service_sessions_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id', 'tenant_id'], ['organizations.id', 'organizations.tenant_id'], name='fk_restaurant_service_sessions_organization_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_restaurant_service_sessions_location_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['resource_id', 'tenant_id', 'location_id'], ['resources.id', 'resources.tenant_id', 'resources.location_id'], name='fk_restaurant_service_sessions_resource_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['opened_by_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_restaurant_service_sessions_opened_membership', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['closed_by_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_restaurant_service_sessions_closed_membership', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resource_id', 'open_slot', name='uq_restaurant_service_sessions_resource_open'),
        sa.UniqueConstraint('join_context_key', name='uq_restaurant_service_sessions_join_context'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', name='uq_restaurant_service_sessions_scope'),
        **options,
    )
    op.create_index('ix_restaurant_service_sessions_resource_history', 'restaurant_service_sessions', ['resource_id', 'id'])
    op.create_index('ix_restaurant_service_sessions_tenant_location_status', 'restaurant_service_sessions', ['tenant_id', 'location_id', 'status', 'id'])

    op.create_table(
        'diner_sessions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=False),
        sa.Column('service_session_id', sa.BigInteger(), nullable=False),
        sa.Column('customer_id', sa.BigInteger(), nullable=True),
        sa.Column('conversation_id', sa.BigInteger(), nullable=False),
        sa.Column('conversation_participant_id', sa.BigInteger(), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('normalized_email', sa.String(320), nullable=True),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('active_slot', sa.SmallInteger(), server_default=sa.text('1'), nullable=True),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'ENDED')", name='ck_diner_sessions_status'),
        sa.CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_diner_sessions_active_slot'),
        sa.CheckConstraint("CHAR_LENGTH(display_name) BETWEEN 1 AND 200 AND TRIM(display_name) <> ''", name='ck_diner_sessions_display_name'),
        sa.CheckConstraint("(status = 'ACTIVE' AND active_slot = 1 AND ended_at IS NULL) OR (status = 'ENDED' AND active_slot IS NULL AND ended_at IS NOT NULL)", name='ck_diner_sessions_lifecycle'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_diner_sessions_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'], ['restaurant_service_sessions.id', 'restaurant_service_sessions.tenant_id', 'restaurant_service_sessions.organization_id', 'restaurant_service_sessions.location_id', 'restaurant_service_sessions.resource_id'], name='fk_diner_sessions_service_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id', 'tenant_id'], ['customers.id', 'customers.tenant_id'], name='fk_diner_sessions_customer_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['conversation_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'], ['conversations.id', 'conversations.tenant_id', 'conversations.organization_id', 'conversations.location_id', 'conversations.resource_id'], name='fk_diner_sessions_conversation_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['conversation_participant_id', 'tenant_id', 'conversation_id'], ['conversation_participants.id', 'conversation_participants.tenant_id', 'conversation_participants.conversation_id'], name='fk_diner_sessions_participant_scope', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_session_id', 'normalized_email', 'active_slot', name='uq_diner_sessions_active_email'),
        sa.UniqueConstraint('conversation_id', name='uq_diner_sessions_conversation'),
        sa.UniqueConstraint('conversation_participant_id', name='uq_diner_sessions_participant'),
        **options,
    )
    op.create_index('ix_diner_sessions_service_active', 'diner_sessions', ['service_session_id', 'active_slot', 'id'])
    op.create_index('ix_diner_sessions_customer', 'diner_sessions', ['tenant_id', 'customer_id', 'id'])
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('diner_sessions')
    op.drop_table('restaurant_service_sessions')
    op.drop_constraint('uq_conversations_id_full_scope', 'conversations', type_='unique')
    # Preserve global permission rows and grants; their later provenance is unknowable.
