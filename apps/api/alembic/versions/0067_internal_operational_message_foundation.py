"""add bounded internal operational message foundation

Revision ID: 0067_internal_operational_message_foundation
Revises: 0066_restaurant_table_management
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0067_internal_operational_message_foundation'
down_revision: str | None = '0066_restaurant_table_management'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OPTIONS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


def upgrade() -> None:
    op.create_table(
        'internal_operational_messages',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('creator_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('recipient_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('message_type', sa.String(40, collation='ascii_bin'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('party_size', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(16, collation='ascii_bin'), nullable=False, server_default=sa.text("'REQUESTED'")),
        sa.Column('entered_at', sa.DateTime(), nullable=True),
        sa.Column('entered_by_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('ready_at', sa.DateTime(), nullable=True),
        sa.Column('ready_by_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('prepared_table_resource_id', sa.BigInteger(), nullable=True),
        sa.Column('version', sa.BigInteger(), nullable=False, server_default=sa.text('1')),
        sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_internal_messages_location_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['creator_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_messages_creator', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['recipient_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_messages_recipient', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['entered_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_messages_entered_by', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['ready_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_messages_ready_by', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['prepared_table_resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_internal_messages_prepared_table', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_internal_messages_scope'),
        sa.UniqueConstraint('tenant_id', 'location_id', 'creator_membership_id', 'idempotency_key', name='uq_internal_messages_create_replay'),
        sa.CheckConstraint("message_type IN ('TABLE_PREPARATION_REQUEST')", name='ck_internal_messages_type'),
        sa.CheckConstraint("status IN ('REQUESTED','READY')", name='ck_internal_messages_status'),
        sa.CheckConstraint('party_size > 0', name='ck_internal_messages_party_size'),
        sa.CheckConstraint('version >= 1', name='ck_internal_messages_version'),
        sa.CheckConstraint(
            '(entered_at IS NULL AND entered_by_membership_id IS NULL) OR '
            '(entered_at IS NOT NULL AND entered_by_membership_id=recipient_membership_id)',
            name='ck_internal_messages_enterado',
        ),
        sa.CheckConstraint(
            "(status='REQUESTED' AND ready_at IS NULL AND ready_by_membership_id IS NULL AND prepared_table_resource_id IS NULL) OR "
            "(status='READY' AND entered_at IS NOT NULL AND ready_at IS NOT NULL AND ready_by_membership_id=recipient_membership_id)",
            name='ck_internal_messages_lifecycle',
        ),
        **OPTIONS,
    )
    op.create_index(
        'ix_internal_messages_sent', 'internal_operational_messages',
        ['tenant_id', 'location_id', 'creator_membership_id', 'created_at', 'id'],
    )
    op.create_index(
        'ix_internal_messages_inbox', 'internal_operational_messages',
        ['tenant_id', 'location_id', 'recipient_membership_id', 'created_at', 'id'],
    )
    op.create_table(
        'internal_operational_message_responses',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('author_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('sequence', sa.BigInteger(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(
            ['message_id', 'tenant_id', 'organization_id', 'location_id'],
            ['internal_operational_messages.id', 'internal_operational_messages.tenant_id', 'internal_operational_messages.organization_id', 'internal_operational_messages.location_id'],
            name='fk_internal_message_responses_message_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['author_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_message_responses_author', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_internal_message_responses_scope'),
        sa.UniqueConstraint('message_id', 'sequence', name='uq_internal_message_responses_sequence'),
        sa.UniqueConstraint('message_id', 'author_membership_id', 'idempotency_key', name='uq_internal_message_responses_replay'),
        sa.CheckConstraint('sequence >= 1', name='ck_internal_message_responses_sequence'),
        **OPTIONS,
    )
    op.create_index(
        'ix_internal_message_responses_message',
        'internal_operational_message_responses', ['message_id', 'sequence', 'id'],
    )
    op.create_table(
        'internal_operational_message_history',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('event_sequence', sa.BigInteger(), nullable=False),
        sa.Column('event_type', sa.String(32, collation='ascii_bin'), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('response_id', sa.BigInteger(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(
            ['message_id', 'tenant_id', 'organization_id', 'location_id'],
            ['internal_operational_messages.id', 'internal_operational_messages.tenant_id', 'internal_operational_messages.organization_id', 'internal_operational_messages.location_id'],
            name='fk_internal_message_history_message_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_message_history_actor', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['response_id', 'tenant_id'],
            ['internal_operational_message_responses.id', 'internal_operational_message_responses.tenant_id'],
            name='fk_internal_message_history_response', ondelete='RESTRICT',
        ),
        sa.UniqueConstraint('message_id', 'event_sequence', name='uq_internal_message_history_sequence'),
        sa.CheckConstraint("event_type IN ('MESSAGE_CREATED','ENTERADO','RESPONSE_ADDED','READY')", name='ck_internal_message_history_type'),
        sa.CheckConstraint('event_sequence >= 1', name='ck_internal_message_history_sequence'),
        **OPTIONS,
    )
    op.create_index(
        'ix_internal_message_history_message',
        'internal_operational_message_history', ['message_id', 'event_sequence', 'id'],
    )

    permissions = sa.table(
        'permissions', sa.column('id', sa.BigInteger()),
        sa.column('code', sa.String()), sa.column('description', sa.String()),
    )
    roles = sa.table(
        'roles', sa.column('id', sa.BigInteger()),
        sa.column('name', sa.String()), sa.column('status', sa.String()),
    )
    grants = sa.table(
        'role_permissions', sa.column('id', sa.BigInteger()),
        sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()),
    )
    connection = op.get_bind()
    descriptions = {
        'internal_message.read': 'Read participant-scoped internal operational messages.',
        'internal_message.send': 'Send internal operational messages in authorized locations.',
        'internal_message.respond': 'Acknowledge, respond to, and complete addressed internal messages.',
    }
    admin_ids = tuple(connection.execute(sa.select(roles.c.id).where(
        roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE',
    )).scalars())
    for code, description in descriptions.items():
        permission_id = connection.execute(sa.select(permissions.c.id).where(
            permissions.c.code == code,
        )).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(
                code=code, description=description,
            ))
            permission_id = connection.execute(sa.select(permissions.c.id).where(
                permissions.c.code == code,
            )).scalar_one()
        for role_id in admin_ids:
            exists = connection.execute(sa.select(grants.c.id).where(
                grants.c.role_id == role_id,
                grants.c.permission_id == permission_id,
            )).scalar_one_or_none()
            if exists is None:
                connection.execute(grants.insert().values(
                    role_id=role_id, permission_id=permission_id,
                ))


def downgrade() -> None:
    connection = op.get_bind()
    for code in (
        'internal_message.respond', 'internal_message.send', 'internal_message.read',
    ):
        permission_id = connection.execute(sa.text(
            'SELECT id FROM permissions WHERE code=:code'
        ), {'code': code}).scalar_one_or_none()
        if permission_id is not None:
            connection.execute(sa.text(
                'DELETE FROM role_permissions WHERE permission_id=:permission_id'
            ), {'permission_id': permission_id})
            connection.execute(sa.text(
                'DELETE FROM permissions WHERE id=:permission_id'
            ), {'permission_id': permission_id})
    op.drop_index(
        'ix_internal_message_history_message',
        table_name='internal_operational_message_history',
    )
    op.drop_table('internal_operational_message_history')
    op.drop_index(
        'ix_internal_message_responses_message',
        table_name='internal_operational_message_responses',
    )
    op.drop_table('internal_operational_message_responses')
    op.drop_index('ix_internal_messages_inbox', table_name='internal_operational_messages')
    op.drop_index('ix_internal_messages_sent', table_name='internal_operational_messages')
    op.drop_table('internal_operational_messages')
