from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class Conversation(TimestampMixin, Base):
    __tablename__ = 'conversations'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_conversations_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_conversations_organization_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_conversations_location_tenant_org',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_conversations_resource_tenant_location',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', name='uq_conversations_id_tenant'),
        UniqueConstraint(
            'id',
            'tenant_id',
            'organization_id',
            'location_id',
            name='uq_conversations_id_tenant_org_location',
        ),
        CheckConstraint(
            "channel IN ('IN_PERSON_DIGITAL', 'PHONE', 'WHATSAPP', 'WEB_CHAT', 'MOBILE_APP')",
            name='ck_conversations_channel',
        ),
        CheckConstraint("status IN ('ACTIVE', 'CLOSED')", name='ck_conversations_status'),
        CheckConstraint(
            "(status = 'ACTIVE' AND closed_at IS NULL) OR "
            "(status = 'CLOSED' AND closed_at IS NOT NULL)",
            name='ck_conversations_status_closed_at',
        ),
        CheckConstraint('next_message_sequence >= 1', name='ck_conversations_next_sequence'),
        CheckConstraint(
            'resource_id IS NULL OR location_id IS NOT NULL',
            name='ck_conversations_resource_requires_location',
        ),
        CheckConstraint(
            'default_language IS NULL OR CHAR_LENGTH(default_language) BETWEEN 1 AND 63',
            name='ck_conversations_default_language_length',
        ),
        Index(
            'ix_conversations_tenant_org_status',
            'tenant_id',
            'organization_id',
            'status',
            'id',
        ),
        Index(
            'ix_conversations_tenant_location_status',
            'tenant_id',
            'location_id',
            'status',
            'id',
        ),
        Index('ix_conversations_tenant_resource', 'tenant_id', 'resource_id', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    resource_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    default_language: Mapped[str | None] = mapped_column(String(63), nullable=True)
    next_message_sequence: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class ConversationParticipant(TimestampMixin, Base):
    __tablename__ = 'conversation_participants'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_conversation_participants_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['conversation_id', 'tenant_id'],
            ['conversations.id', 'conversations.tenant_id'],
            name='fk_conversation_participants_conversation_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['customer_id', 'tenant_id'],
            ['customers.id', 'customers.tenant_id'],
            name='fk_conversation_participants_customer_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['tenant_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_conversation_participants_membership_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id',
            'tenant_id',
            'conversation_id',
            name='uq_conversation_participants_id_tenant_conversation',
        ),
        UniqueConstraint(
            'conversation_id',
            'customer_id',
            name='uq_conversation_participants_conversation_customer',
        ),
        CheckConstraint(
            "participant_type IN ('CUSTOMER', 'DIGITAL_WAITER', 'HUMAN_STAFF', 'SYSTEM')",
            name='ck_conversation_participants_type',
        ),
        CheckConstraint(
            "(participant_type = 'CUSTOMER' AND tenant_membership_id IS NULL) OR "
            "(participant_type = 'HUMAN_STAFF' AND customer_id IS NULL "
            "AND tenant_membership_id IS NOT NULL) OR "
            "(participant_type IN ('DIGITAL_WAITER', 'SYSTEM') "
            "AND customer_id IS NULL AND tenant_membership_id IS NULL)",
            name='ck_conversation_participants_references',
        ),
        CheckConstraint(
            'preferred_language IS NULL OR CHAR_LENGTH(preferred_language) BETWEEN 1 AND 63',
            name='ck_conversation_participants_language_length',
        ),
        Index(
            'ix_conversation_participants_conversation_type',
            'tenant_id',
            'conversation_id',
            'participant_type',
            'id',
        ),
        Index('ix_conversation_participants_customer', 'tenant_id', 'customer_id', 'id'),
        Index(
            'ix_conversation_participants_membership',
            'tenant_id',
            'tenant_membership_id',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    participant_type: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tenant_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(63), nullable=True)


class ConversationMessage(Base):
    __tablename__ = 'conversation_messages'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_conversation_messages_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['conversation_id', 'tenant_id'],
            ['conversations.id', 'conversations.tenant_id'],
            name='fk_conversation_messages_conversation_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['participant_id', 'tenant_id', 'conversation_id'],
            [
                'conversation_participants.id',
                'conversation_participants.tenant_id',
                'conversation_participants.conversation_id',
            ],
            name='fk_conversation_messages_participant_tenant_conversation',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'tenant_id',
            'conversation_id',
            'sequence_number',
            name='uq_conversation_messages_tenant_conversation_sequence',
        ),
        UniqueConstraint(
            'id',
            'tenant_id',
            'conversation_id',
            name='uq_conversation_messages_id_tenant_conversation',
        ),
        CheckConstraint('sequence_number >= 1', name='ck_conversation_messages_sequence'),
        CheckConstraint(
            "modality IN ('TEXT', 'VOICE', 'TOUCH')",
            name='ck_conversation_messages_modality',
        ),
        CheckConstraint(
            "CHAR_LENGTH(content_text) BETWEEN 1 AND 10000 AND TRIM(content_text) <> ''",
            name='ck_conversation_messages_content',
        ),
        CheckConstraint(
            "language_source IS NULL OR language_source IN ('DECLARED', 'DETECTED', 'INHERITED')",
            name='ck_conversation_messages_language_source',
        ),
        CheckConstraint(
            '(language IS NULL AND language_source IS NULL) OR '
            '(language IS NOT NULL AND language_source IS NOT NULL)',
            name='ck_conversation_messages_language_pair',
        ),
        CheckConstraint(
            'language IS NULL OR CHAR_LENGTH(language) BETWEEN 1 AND 63',
            name='ck_conversation_messages_language_length',
        ),
        Index('ix_conversation_messages_participant', 'tenant_id', 'participant_id', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    participant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    modality: Mapped[str] = mapped_column(String(16), nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(63), nullable=True)
    language_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
