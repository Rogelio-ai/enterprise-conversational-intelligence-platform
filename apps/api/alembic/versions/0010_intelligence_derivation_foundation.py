"""establish intelligence derivation foundation

Revision ID: 0010_intelligence_derivation_foundation
Revises: 0009_conversation_foundation
Create Date: 2026-08-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0010_intelligence_derivation_foundation'
down_revision: str | None = '0009_conversation_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _options() -> dict[str, str]:
    return {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
        'mysql_collate': 'utf8mb4_unicode_ci',
    }


def upgrade() -> None:
    options = _options()
    op.create_unique_constraint(
        'uq_conversation_messages_id_tenant_conversation',
        'conversation_messages',
        ['id', 'tenant_id', 'conversation_id'],
    )
    op.create_table(
        'intelligence_derivations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('conversation_id', sa.BigInteger(), nullable=False),
        sa.Column('source_message_id', sa.BigInteger(), nullable=False),
        sa.Column('schema_key', sa.String(100), nullable=False),
        sa.Column('schema_version', sa.String(64), nullable=False),
        sa.Column('producer_key', sa.String(128), nullable=False),
        sa.Column('producer_version', sa.String(128), nullable=False),
        sa.Column('correlation_id', sa.String(128), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "CHAR_LENGTH(schema_key) BETWEEN 1 AND 100 AND TRIM(schema_key) <> ''",
            name='ck_intelligence_derivations_schema_key',
        ),
        sa.CheckConstraint(
            "CHAR_LENGTH(schema_version) BETWEEN 1 AND 64 AND TRIM(schema_version) <> ''",
            name='ck_intelligence_derivations_schema_version',
        ),
        sa.CheckConstraint(
            "CHAR_LENGTH(producer_key) BETWEEN 1 AND 128 AND TRIM(producer_key) <> ''",
            name='ck_intelligence_derivations_producer_key',
        ),
        sa.CheckConstraint(
            "CHAR_LENGTH(producer_version) BETWEEN 1 AND 128 AND TRIM(producer_version) <> ''",
            name='ck_intelligence_derivations_producer_version',
        ),
        sa.CheckConstraint(
            "CHAR_LENGTH(correlation_id) BETWEEN 1 AND 128 AND TRIM(correlation_id) <> ''",
            name='ck_intelligence_derivations_correlation_id',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_intelligence_derivations_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['conversation_id', 'tenant_id'],
            ['conversations.id', 'conversations.tenant_id'],
            name='fk_intelligence_derivations_conversation_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['source_message_id', 'tenant_id', 'conversation_id'],
            [
                'conversation_messages.id',
                'conversation_messages.tenant_id',
                'conversation_messages.conversation_id',
            ],
            name='fk_intelligence_derivations_message_tenant_conversation',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', name='uq_intelligence_derivations_id_tenant'
        ),
        **options,
    )
    op.create_index(
        'ix_intelligence_derivations_tenant_message_created',
        'intelligence_derivations',
        ['tenant_id', 'source_message_id', 'created_at', 'id'],
    )
    op.create_index(
        'ix_intelligence_derivations_tenant_conversation',
        'intelligence_derivations',
        ['tenant_id', 'conversation_id', 'id'],
    )
    op.create_table(
        'restaurant_message_intents',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('derivation_id', sa.BigInteger(), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('intent_code', sa.String(64), nullable=False),
        sa.Column('confidence', sa.Numeric(5, 4), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.CheckConstraint(
            'ordinal >= 1', name='ck_restaurant_message_intents_ordinal'
        ),
        sa.CheckConstraint(
            'confidence IS NULL OR (confidence >= 0 AND confidence <= 1)',
            name='ck_restaurant_message_intents_confidence',
        ),
        sa.CheckConstraint(
            "CHAR_LENGTH(intent_code) BETWEEN 1 AND 64 AND TRIM(intent_code) <> ''",
            name='ck_restaurant_message_intents_code',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_restaurant_message_intents_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['derivation_id', 'tenant_id'],
            ['intelligence_derivations.id', 'intelligence_derivations.tenant_id'],
            name='fk_restaurant_message_intents_derivation_tenant',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'derivation_id',
            'ordinal',
            name='uq_restaurant_message_intents_derivation_ordinal',
        ),
        **options,
    )
    op.create_index(
        'ix_restaurant_message_intents_tenant_code',
        'restaurant_message_intents',
        ['tenant_id', 'intent_code', 'id'],
    )


def downgrade() -> None:
    op.drop_table('restaurant_message_intents')
    op.drop_table('intelligence_derivations')
    op.drop_constraint(
        'uq_conversation_messages_id_tenant_conversation',
        'conversation_messages',
        type_='unique',
    )
