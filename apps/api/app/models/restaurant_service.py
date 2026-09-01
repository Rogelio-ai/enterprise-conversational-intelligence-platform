from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class RestaurantServiceSession(TimestampMixin, Base):
    __tablename__ = 'restaurant_service_sessions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_restaurant_service_sessions_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_restaurant_service_sessions_organization_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_restaurant_service_sessions_location_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_restaurant_service_sessions_resource_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['opened_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_restaurant_service_sessions_opened_membership',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['closed_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_restaurant_service_sessions_closed_membership',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('resource_id', 'open_slot', name='uq_restaurant_service_sessions_resource_open'),
        UniqueConstraint('join_context_key', name='uq_restaurant_service_sessions_join_context'),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'resource_id',
            name='uq_restaurant_service_sessions_scope',
        ),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name='ck_restaurant_service_sessions_status'),
        CheckConstraint('party_size BETWEEN 1 AND 999', name='ck_restaurant_service_sessions_party_size'),
        CheckConstraint('access_code_version >= 1', name='ck_restaurant_service_sessions_code_version'),
        CheckConstraint('failed_join_attempts >= 0', name='ck_restaurant_service_sessions_failed_attempts'),
        CheckConstraint('open_slot IS NULL OR open_slot = 1', name='ck_restaurant_service_sessions_open_slot'),
        CheckConstraint(
            "(status = 'OPEN' AND open_slot = 1 AND access_code_digest IS NOT NULL "
            "AND closed_at IS NULL AND closed_by_membership_id IS NULL) OR "
            "(status = 'CLOSED' AND open_slot IS NULL AND access_code_digest IS NULL "
            "AND closed_at IS NOT NULL AND closed_by_membership_id IS NOT NULL)",
            name='ck_restaurant_service_sessions_lifecycle',
        ),
        Index('ix_restaurant_service_sessions_resource_history', 'resource_id', 'id'),
        Index('ix_restaurant_service_sessions_tenant_location_status', 'tenant_id', 'location_id', 'status', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='OPEN', server_default=text("'OPEN'"))
    open_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, default=1, server_default=text('1'))
    join_context_key: Mapped[str] = mapped_column(String(64, collation='utf8mb4_bin'), nullable=False)
    access_code_digest: Mapped[str | None] = mapped_column(String(64, collation='ascii_bin'), nullable=True)
    access_code_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    failed_join_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text('0'))
    failed_window_started_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    join_locked_until: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    opened_by_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    closed_by_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class DinerSession(TimestampMixin, Base):
    __tablename__ = 'diner_sessions'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_diner_sessions_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(
            ['service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'],
            [
                'restaurant_service_sessions.id',
                'restaurant_service_sessions.tenant_id',
                'restaurant_service_sessions.organization_id',
                'restaurant_service_sessions.location_id',
                'restaurant_service_sessions.resource_id',
            ],
            name='fk_diner_sessions_service_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['customer_id', 'tenant_id'], ['customers.id', 'customers.tenant_id'],
            name='fk_diner_sessions_customer_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['conversation_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'],
            [
                'conversations.id', 'conversations.tenant_id', 'conversations.organization_id',
                'conversations.location_id', 'conversations.resource_id',
            ],
            name='fk_diner_sessions_conversation_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['conversation_participant_id', 'tenant_id', 'conversation_id'],
            ['conversation_participants.id', 'conversation_participants.tenant_id', 'conversation_participants.conversation_id'],
            name='fk_diner_sessions_participant_scope',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('service_session_id', 'normalized_email', 'active_slot', name='uq_diner_sessions_active_email'),
        UniqueConstraint('conversation_id', name='uq_diner_sessions_conversation'),
        UniqueConstraint('conversation_participant_id', name='uq_diner_sessions_participant'),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_diner_sessions_check_controller_scope',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'resource_id',
            'service_session_id', 'conversation_id', name='uq_diner_sessions_full_scope',
        ),
        CheckConstraint("status IN ('ACTIVE', 'ENDED')", name='ck_diner_sessions_status'),
        CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_diner_sessions_active_slot'),
        CheckConstraint("CHAR_LENGTH(display_name) BETWEEN 1 AND 200 AND TRIM(display_name) <> ''", name='ck_diner_sessions_display_name'),
        CheckConstraint(
            "(status = 'ACTIVE' AND active_slot = 1 AND ended_at IS NULL) OR "
            "(status = 'ENDED' AND active_slot IS NULL AND ended_at IS NOT NULL)",
            name='ck_diner_sessions_lifecycle',
        ),
        Index('ix_diner_sessions_service_active', 'service_session_id', 'active_slot', 'id'),
        Index('ix_diner_sessions_customer', 'tenant_id', 'customer_id', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    service_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    conversation_participant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'"))
    active_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, default=1, server_default=text('1'))
    joined_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
