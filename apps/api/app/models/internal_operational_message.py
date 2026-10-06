from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sql_text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class InternalOperationalMessage(TimestampMixin, Base):
    __tablename__ = 'internal_operational_messages'
    __table_args__ = (
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_internal_messages_location_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['creator_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_messages_creator', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['recipient_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_messages_recipient', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['entered_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_messages_entered_by', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['ready_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_messages_ready_by', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['prepared_table_resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_internal_messages_prepared_table', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_internal_messages_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'location_id', 'creator_membership_id', 'idempotency_key',
            name='uq_internal_messages_create_replay',
        ),
        CheckConstraint(
            "message_type IN ('TABLE_PREPARATION_REQUEST')",
            name='ck_internal_messages_type',
        ),
        CheckConstraint(
            "status IN ('REQUESTED','READY')", name='ck_internal_messages_status',
        ),
        CheckConstraint('party_size > 0', name='ck_internal_messages_party_size'),
        CheckConstraint('version >= 1', name='ck_internal_messages_version'),
        CheckConstraint(
            '(entered_at IS NULL AND entered_by_membership_id IS NULL) OR '
            '(entered_at IS NOT NULL AND '
            'entered_by_membership_id=recipient_membership_id)',
            name='ck_internal_messages_enterado',
        ),
        CheckConstraint(
            "(status='REQUESTED' AND ready_at IS NULL AND "
            "ready_by_membership_id IS NULL AND prepared_table_resource_id IS NULL) OR "
            "(status='READY' AND entered_at IS NOT NULL AND ready_at IS NOT NULL AND "
            'ready_by_membership_id=recipient_membership_id)',
            name='ck_internal_messages_lifecycle',
        ),
        Index(
            'ix_internal_messages_sent', 'tenant_id', 'location_id',
            'creator_membership_id', 'created_at', 'id',
        ),
        Index(
            'ix_internal_messages_inbox', 'tenant_id', 'location_id',
            'recipient_membership_id', 'created_at', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    creator_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recipient_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_type: Mapped[str] = mapped_column(String(40, collation='ascii_bin'), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16, collation='ascii_bin'), nullable=False,
        default='REQUESTED', server_default=sql_text("'REQUESTED'"),
    )
    entered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    entered_by_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ready_by_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prepared_table_resource_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=sql_text('1'),
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False,
    )
    request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False,
    )


class InternalOperationalMessageResponse(Base):
    __tablename__ = 'internal_operational_message_responses'
    __table_args__ = (
        ForeignKeyConstraint(
            ['message_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'internal_operational_messages.id',
                'internal_operational_messages.tenant_id',
                'internal_operational_messages.organization_id',
                'internal_operational_messages.location_id',
            ],
            name='fk_internal_message_responses_message_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['author_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_message_responses_author', ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', name='uq_internal_message_responses_scope'),
        UniqueConstraint(
            'message_id', 'sequence', name='uq_internal_message_responses_sequence',
        ),
        UniqueConstraint(
            'message_id', 'author_membership_id', 'idempotency_key',
            name='uq_internal_message_responses_replay',
        ),
        CheckConstraint('sequence >= 1', name='ck_internal_message_responses_sequence'),
        Index(
            'ix_internal_message_responses_message', 'message_id', 'sequence', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False,
    )
    request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(),
    )


class InternalOperationalMessageHistory(Base):
    __tablename__ = 'internal_operational_message_history'
    __table_args__ = (
        ForeignKeyConstraint(
            ['message_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'internal_operational_messages.id',
                'internal_operational_messages.tenant_id',
                'internal_operational_messages.organization_id',
                'internal_operational_messages.location_id',
            ],
            name='fk_internal_message_history_message_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_internal_message_history_actor', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['response_id', 'tenant_id'],
            ['internal_operational_message_responses.id', 'internal_operational_message_responses.tenant_id'],
            name='fk_internal_message_history_response', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'message_id', 'event_sequence', name='uq_internal_message_history_sequence',
        ),
        CheckConstraint(
            "event_type IN ('MESSAGE_CREATED','ENTERADO','RESPONSE_ADDED','READY')",
            name='ck_internal_message_history_type',
        ),
        CheckConstraint('event_sequence >= 1', name='ck_internal_message_history_sequence'),
        Index(
            'ix_internal_message_history_message', 'message_id', 'event_sequence', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32, collation='ascii_bin'), nullable=False)
    actor_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    response_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp(),
    )
