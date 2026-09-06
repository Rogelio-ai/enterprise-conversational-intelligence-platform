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
        UniqueConstraint('id', 'tenant_id', name='uq_diner_operational_requests_id_tenant'),
        UniqueConstraint(
            'tenant_id', 'diner_session_id', 'idempotency_key',
            name='uq_diner_operational_requests_idempotency',
        ),
        CheckConstraint(
            "request_type IN ('HUMAN_ASSISTANCE','CASH_PAYMENT_ASSISTANCE',"
            "'INVOICE_ASSISTANCE','PAID_CHECK_PRINT')",
            name='ck_diner_operational_requests_type',
        ),
        CheckConstraint(
            "status IN ('PENDING','ACKNOWLEDGED','COMPLETED','CANCELLED')",
            name='ck_diner_operational_requests_status',
        ),
        CheckConstraint(
            "(request_type = 'HUMAN_ASSISTANCE' AND related_restaurant_check_id IS NULL) OR "
            "(request_type <> 'HUMAN_ASSISTANCE' AND related_restaurant_check_id IS NOT NULL)",
            name='ck_diner_operational_requests_related_check',
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
    diner_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
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
    resolved_by_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
