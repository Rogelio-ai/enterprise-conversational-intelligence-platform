"""establish Conversation foundation

Revision ID: 0009_conversation_foundation
Revises: 0008_pricing_promotion_foundation
Create Date: 2026-08-20
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0009_conversation_foundation'
down_revision: str | None = '0008_pricing_promotion_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WS_10_PERMISSIONS = {
    'conversation.read': 'Read Tenant conversations, participants, and messages.',
    'conversation.manage': 'Manage Tenant conversations, participants, and messages.',
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
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()))
    role_permissions = sa.table('role_permissions', sa.column('id', sa.BigInteger()), sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()))
    role_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN')).scalars())
    for code, description in WS_10_PERMISSIONS.items():
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(code=code, description=description))
            permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one()
        for role_id in role_ids:
            exists = connection.execute(sa.select(role_permissions.c.id).where(role_permissions.c.role_id == role_id, role_permissions.c.permission_id == permission_id)).scalar_one_or_none()
            if exists is None:
                connection.execute(role_permissions.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    options = _options()
    op.create_unique_constraint(
        'uq_resources_id_tenant_location',
        'resources',
        ['id', 'tenant_id', 'location_id'],
    )
    op.create_table(
        'conversations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=True),
        sa.Column('resource_id', sa.BigInteger(), nullable=True),
        sa.Column('channel', sa.String(32), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('default_language', sa.String(63), nullable=True),
        sa.Column('next_message_sequence', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("channel IN ('IN_PERSON_DIGITAL', 'PHONE', 'WHATSAPP', 'WEB_CHAT', 'MOBILE_APP')", name='ck_conversations_channel'),
        sa.CheckConstraint("status IN ('ACTIVE', 'CLOSED')", name='ck_conversations_status'),
        sa.CheckConstraint("(status = 'ACTIVE' AND closed_at IS NULL) OR (status = 'CLOSED' AND closed_at IS NOT NULL)", name='ck_conversations_status_closed_at'),
        sa.CheckConstraint('next_message_sequence >= 1', name='ck_conversations_next_sequence'),
        sa.CheckConstraint('resource_id IS NULL OR location_id IS NOT NULL', name='ck_conversations_resource_requires_location'),
        sa.CheckConstraint('default_language IS NULL OR CHAR_LENGTH(default_language) BETWEEN 1 AND 63', name='ck_conversations_default_language_length'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_conversations_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['organization_id', 'tenant_id'], ['organizations.id', 'organizations.tenant_id'], name='fk_conversations_organization_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_conversations_location_tenant_org', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['resource_id', 'tenant_id', 'location_id'], ['resources.id', 'resources.tenant_id', 'resources.location_id'], name='fk_conversations_resource_tenant_location', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_conversations_id_tenant'),
        **options,
    )
    op.create_index('ix_conversations_tenant_org_status', 'conversations', ['tenant_id', 'organization_id', 'status', 'id'])
    op.create_index('ix_conversations_tenant_location_status', 'conversations', ['tenant_id', 'location_id', 'status', 'id'])
    op.create_index('ix_conversations_tenant_resource', 'conversations', ['tenant_id', 'resource_id', 'id'])

    op.create_table(
        'conversation_participants',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('conversation_id', sa.BigInteger(), nullable=False),
        sa.Column('participant_type', sa.String(32), nullable=False),
        sa.Column('customer_id', sa.BigInteger(), nullable=True),
        sa.Column('tenant_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('preferred_language', sa.String(63), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("participant_type IN ('CUSTOMER', 'DIGITAL_WAITER', 'HUMAN_STAFF', 'SYSTEM')", name='ck_conversation_participants_type'),
        sa.CheckConstraint("(participant_type = 'CUSTOMER' AND tenant_membership_id IS NULL) OR (participant_type = 'HUMAN_STAFF' AND customer_id IS NULL AND tenant_membership_id IS NOT NULL) OR (participant_type IN ('DIGITAL_WAITER', 'SYSTEM') AND customer_id IS NULL AND tenant_membership_id IS NULL)", name='ck_conversation_participants_references'),
        sa.CheckConstraint('preferred_language IS NULL OR CHAR_LENGTH(preferred_language) BETWEEN 1 AND 63', name='ck_conversation_participants_language_length'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_conversation_participants_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['conversation_id', 'tenant_id'], ['conversations.id', 'conversations.tenant_id'], name='fk_conversation_participants_conversation_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id', 'tenant_id'], ['customers.id', 'customers.tenant_id'], name='fk_conversation_participants_customer_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_conversation_participants_membership_tenant', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', 'conversation_id', name='uq_conversation_participants_id_tenant_conversation'),
        sa.UniqueConstraint('conversation_id', 'customer_id', name='uq_conversation_participants_conversation_customer'),
        **options,
    )
    op.create_index('ix_conversation_participants_conversation_type', 'conversation_participants', ['tenant_id', 'conversation_id', 'participant_type', 'id'])
    op.create_index('ix_conversation_participants_customer', 'conversation_participants', ['tenant_id', 'customer_id', 'id'])
    op.create_index('ix_conversation_participants_membership', 'conversation_participants', ['tenant_id', 'tenant_membership_id', 'id'])

    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('conversation_id', sa.BigInteger(), nullable=False),
        sa.Column('participant_id', sa.BigInteger(), nullable=False),
        sa.Column('sequence_number', sa.BigInteger(), nullable=False),
        sa.Column('modality', sa.String(16), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('language', sa.String(63), nullable=True),
        sa.Column('language_source', sa.String(16), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint('sequence_number >= 1', name='ck_conversation_messages_sequence'),
        sa.CheckConstraint("modality IN ('TEXT', 'VOICE', 'TOUCH')", name='ck_conversation_messages_modality'),
        sa.CheckConstraint("CHAR_LENGTH(content_text) BETWEEN 1 AND 10000 AND TRIM(content_text) <> ''", name='ck_conversation_messages_content'),
        sa.CheckConstraint("language_source IS NULL OR language_source IN ('DECLARED', 'DETECTED', 'INHERITED')", name='ck_conversation_messages_language_source'),
        sa.CheckConstraint('(language IS NULL AND language_source IS NULL) OR (language IS NOT NULL AND language_source IS NOT NULL)', name='ck_conversation_messages_language_pair'),
        sa.CheckConstraint('language IS NULL OR CHAR_LENGTH(language) BETWEEN 1 AND 63', name='ck_conversation_messages_language_length'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_conversation_messages_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['conversation_id', 'tenant_id'], ['conversations.id', 'conversations.tenant_id'], name='fk_conversation_messages_conversation_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['participant_id', 'tenant_id', 'conversation_id'], ['conversation_participants.id', 'conversation_participants.tenant_id', 'conversation_participants.conversation_id'], name='fk_conversation_messages_participant_tenant_conversation', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'conversation_id', 'sequence_number', name='uq_conversation_messages_tenant_conversation_sequence'),
        **options,
    )
    op.create_index('ix_conversation_messages_participant', 'conversation_messages', ['tenant_id', 'participant_id', 'id'])
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('conversation_messages')
    op.drop_table('conversation_participants')
    op.drop_table('conversations')
    op.drop_constraint('uq_resources_id_tenant_location', 'resources', type_='unique')
    # Preserve permission catalog entries and grants; their later provenance is unknowable.
