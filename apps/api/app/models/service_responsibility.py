from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


SERVICE_SCOPE_COLUMNS = (
    'service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id',
)
SERVICE_SCOPE_TARGETS = (
    'restaurant_service_sessions.id',
    'restaurant_service_sessions.tenant_id',
    'restaurant_service_sessions.organization_id',
    'restaurant_service_sessions.location_id',
    'restaurant_service_sessions.resource_id',
)


class ServiceResponsibleWaiter(TimestampMixin, Base):
    __tablename__ = 'service_responsible_waiters'
    __table_args__ = (
        ForeignKeyConstraint(
            SERVICE_SCOPE_COLUMNS, SERVICE_SCOPE_TARGETS,
            name='fk_service_responsible_waiters_service_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['waiter_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_service_responsible_waiters_waiter_tenant', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'service_session_id', 'waiter_membership_id',
            name='uq_service_responsible_waiters_service_waiter',
        ),
        Index(
            'ix_service_responsible_waiters_waiter_location',
            'tenant_id', 'location_id', 'waiter_membership_id', 'service_session_id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    service_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    waiter_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ServiceResponsibilityTransition(Base):
    __tablename__ = 'service_responsibility_transitions'
    __table_args__ = (
        ForeignKeyConstraint(
            SERVICE_SCOPE_COLUMNS, SERVICE_SCOPE_TARGETS,
            name='fk_service_responsibility_transitions_service_scope',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_service_responsibility_transitions_actor_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'service_session_id', 'result_version',
            name='uq_service_responsibility_transitions_service_version',
        ),
        UniqueConstraint(
            'tenant_id', 'idempotency_actor_scope', 'idempotency_key',
            name='uq_service_responsibility_transitions_idempotency',
        ),
        CheckConstraint(
            "operation IN ('INITIALIZE','RESPONSIBILITY_UPDATE')",
            name='ck_service_responsibility_transitions_operation',
        ),
        CheckConstraint(
            'result_version >= 1',
            name='ck_service_responsibility_transitions_version',
        ),
        CheckConstraint(
            'source_table_assignment_version IS NULL OR source_table_assignment_version >= 0',
            name='ck_service_responsibility_transitions_source_version',
        ),
        Index(
            'ix_service_responsibility_transitions_scope_time',
            'tenant_id', 'location_id', 'service_session_id', 'recorded_at', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    service_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation: Mapped[str] = mapped_column(String(32, collation='ascii_bin'), nullable=False)
    result_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    before_responsible_membership_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    after_responsible_membership_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    actor_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_actor_scope: Mapped[str] = mapped_column(
        String(200, collation='ascii_bin'), nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False,
    )
    request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False,
    )
    source_table_assignment_version: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp(),
    )
