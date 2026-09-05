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


class CashSession(TimestampMixin, Base):
    __tablename__ = 'cash_sessions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_cash_sessions_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_cash_sessions_location_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_cash_sessions_resource_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['cashier_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_cash_sessions_cashier_membership', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'resource_id',
            name='uq_cash_sessions_scope',
        ),
        UniqueConstraint(
            'resource_id', 'open_slot', name='uq_cash_sessions_resource_open',
        ),
        UniqueConstraint(
            'tenant_id', 'open_actor_scope', 'open_idempotency_key',
            name='uq_cash_sessions_open_idempotency',
        ),
        CheckConstraint(
            "status IN ('OPEN','CLOSED')", name='ck_cash_sessions_status',
        ),
        CheckConstraint(
            'open_slot IS NULL OR open_slot = 1',
            name='ck_cash_sessions_open_slot',
        ),
        CheckConstraint(
            "(status='OPEN' AND open_slot=1) OR "
            "(status='CLOSED' AND open_slot IS NULL)",
            name='ck_cash_sessions_lifecycle',
        ),
        CheckConstraint(
            'movement_version >= 0 AND open_request_schema_version >= 1',
            name='ck_cash_sessions_versions',
        ),
        CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_cash_sessions_currency',
        ),
        CheckConstraint(
            "(opened_by_actor_type='EMPLOYEE' AND opened_by_actor_id IS NOT NULL "
            "AND opened_by_actor_reference IS NULL) OR "
            "(opened_by_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') "
            "AND opened_by_actor_id IS NULL AND opened_by_actor_reference IS NOT NULL)",
            name='ck_cash_sessions_open_actor',
        ),
        Index('ix_cash_sessions_resource_history', 'resource_id', 'id'),
        Index(
            'ix_cash_sessions_location_status',
            'tenant_id', 'location_id', 'status', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cashier_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3, collation='ascii_bin'), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='OPEN', server_default=text("'OPEN'")
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    opened_by_actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    opened_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    opened_by_actor_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    movement_version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default=text('0')
    )
    open_slot: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True, default=1, server_default=text('1')
    )
    open_actor_scope: Mapped[str] = mapped_column(
        String(200, collation='ascii_bin'), nullable=False
    )
    open_idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False
    )
    open_request_schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text('1')
    )
    open_request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
