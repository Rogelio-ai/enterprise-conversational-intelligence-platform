"""add conversation responder persistence foundation

Revision ID: 0062_conversation_responder_foundation
Revises: 0061_operational_message_center_foundation
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0062_conversation_responder_foundation'
down_revision: str | None = '0061_operational_message_center_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'conversation_messages',
        sa.Column('operational_request_id', sa.BigInteger(), nullable=True),
    )
    op.add_column(
        'conversation_messages',
        sa.Column(
            'response_idempotency_key',
            sa.String(128, collation='ascii_bin'),
            nullable=True,
        ),
    )
    op.add_column(
        'conversation_messages',
        sa.Column(
            'response_request_fingerprint',
            sa.String(64, collation='ascii_bin'),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_conversation_messages_operational_request',
        'conversation_messages',
        ['operational_request_id', 'tenant_id', 'id'],
    )
    op.create_foreign_key(
        'fk_conversation_messages_operational_request_tenant',
        'conversation_messages',
        'diner_operational_requests',
        ['operational_request_id', 'tenant_id'],
        ['id', 'tenant_id'],
        ondelete='RESTRICT',
    )
    op.create_check_constraint(
        'ck_conversation_messages_responder_evidence',
        'conversation_messages',
        '(operational_request_id IS NULL AND response_idempotency_key IS NULL '
        'AND response_request_fingerprint IS NULL) OR '
        '(operational_request_id IS NOT NULL AND response_idempotency_key IS NOT NULL '
        'AND response_request_fingerprint IS NOT NULL)',
    )
    op.create_unique_constraint(
        'uq_conversation_messages_responder_replay',
        'conversation_messages',
        [
            'tenant_id',
            'operational_request_id',
            'participant_id',
            'response_idempotency_key',
        ],
    )
    op.create_unique_constraint(
        'uq_conversation_participants_conversation_membership',
        'conversation_participants',
        ['conversation_id', 'tenant_membership_id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_conversation_participants_conversation_membership',
        'conversation_participants',
        type_='unique',
    )
    op.drop_constraint(
        'uq_conversation_messages_responder_replay',
        'conversation_messages',
        type_='unique',
    )
    op.drop_constraint(
        'ck_conversation_messages_responder_evidence',
        'conversation_messages',
        type_='check',
    )
    op.drop_constraint(
        'fk_conversation_messages_operational_request_tenant',
        'conversation_messages',
        type_='foreignkey',
    )
    op.drop_index(
        'ix_conversation_messages_operational_request',
        table_name='conversation_messages',
    )
    op.drop_column('conversation_messages', 'response_request_fingerprint')
    op.drop_column('conversation_messages', 'response_idempotency_key')
    op.drop_column('conversation_messages', 'operational_request_id')
