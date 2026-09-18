from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class DinerOperationalRequest(Base):
    __tablename__ = 'diner_operational_requests'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_diner_operational_requests_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'],
            [
                'restaurant_service_sessions.id',
                'restaurant_service_sessions.tenant_id',
                'restaurant_service_sessions.organization_id',
                'restaurant_service_sessions.location_id',
                'restaurant_service_sessions.resource_id',
            ],
            name='fk_diner_operational_requests_service_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['diner_session_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'diner_sessions.id', 'diner_sessions.tenant_id',
                'diner_sessions.organization_id', 'diner_sessions.location_id',
            ],
            name='fk_diner_operational_requests_diner_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['related_restaurant_check_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_checks.id', 'restaurant_checks.tenant_id',
                'restaurant_checks.organization_id', 'restaurant_checks.location_id',
            ],
            name='fk_diner_operational_requests_check_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['resolved_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_diner_operational_requests_resolver', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['acknowledged_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_diner_operational_requests_acknowledger', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['preparation_work_id', 'tenant_id'],
            ['preparation_works.id', 'preparation_works.tenant_id'],
            name='fk_diner_operational_requests_preparation_work', ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', name='uq_diner_operational_requests_id_tenant'),
        UniqueConstraint(
            'preparation_work_id', name='uq_diner_operational_requests_preparation_work',
        ),
        UniqueConstraint(
            'tenant_id', 'diner_session_id', 'idempotency_key',
            name='uq_diner_operational_requests_idempotency',
        ),
        CheckConstraint(
            "request_type IN ('HUMAN_ASSISTANCE','CASH_PAYMENT_ASSISTANCE',"
            "'INVOICE_ASSISTANCE','PAID_CHECK_PRINT','PREPARATION_READY')",
            name='ck_diner_operational_requests_type',
        ),
        CheckConstraint(
            "status IN ('PENDING','ACKNOWLEDGED','COMPLETED','CANCELLED')",
            name='ck_diner_operational_requests_status',
        ),
        CheckConstraint(
            "(request_type = 'PREPARATION_READY' AND diner_session_id IS NULL "
            "AND preparation_work_id IS NOT NULL AND related_restaurant_check_id IS NULL) OR "
            "(request_type = 'HUMAN_ASSISTANCE' AND diner_session_id IS NOT NULL "
            "AND preparation_work_id IS NULL AND related_restaurant_check_id IS NULL) OR "
            "(request_type IN ('CASH_PAYMENT_ASSISTANCE','INVOICE_ASSISTANCE',"
            "'PAID_CHECK_PRINT') AND diner_session_id IS NOT NULL "
            "AND preparation_work_id IS NULL AND related_restaurant_check_id IS NOT NULL)",
            name='ck_diner_operational_requests_ownership',
        ),
        CheckConstraint(
            '(acknowledged_by_membership_id IS NULL AND acknowledged_at IS NULL) OR '
            '(acknowledged_by_membership_id IS NOT NULL AND acknowledged_at IS NOT NULL)',
            name='ck_diner_operational_requests_acknowledgement_pair',
        ),
        CheckConstraint(
            "(status IN ('PENDING','ACKNOWLEDGED') AND resolved_at IS NULL "
            "AND resolved_by_membership_id IS NULL) OR "
            "(status IN ('COMPLETED','CANCELLED') AND resolved_at IS NOT NULL "
            "AND resolved_by_membership_id IS NOT NULL)",
            name='ck_diner_operational_requests_resolution',
        ),
        Index(
            'ix_diner_operational_requests_staff_queue',
            'tenant_id', 'location_id', 'status', 'created_at', 'id',
        ),
        Index(
            'ix_diner_operational_requests_diner_history',
            'tenant_id', 'diner_session_id', 'created_at', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    service_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    diner_session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    request_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default='PENDING', server_default=text("'PENDING'")
    )
    related_restaurant_check_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False
    )
    request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    preparation_work_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    acknowledged_by_membership_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    resolved_by_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class OperationalRequestWaiterState(TimestampMixin, Base):
    __tablename__ = 'operational_request_waiter_states'
    __table_args__ = (
        ForeignKeyConstraint(
            ['operational_request_id', 'tenant_id'],
            ['diner_operational_requests.id', 'diner_operational_requests.tenant_id'],
            name='fk_operational_request_waiter_states_request_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['waiter_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_operational_request_waiter_states_waiter_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'operational_request_id', 'waiter_membership_id',
            name='uq_operational_request_waiter_states_request_waiter',
        ),
        Index(
            'ix_operational_request_waiter_states_waiter_view',
            'tenant_id', 'waiter_membership_id', 'hidden_at', 'operational_request_id',
        ),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8mb4',
            'mysql_collate': 'utf8mb4_unicode_ci',
        },
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operational_request_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    waiter_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entered_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
