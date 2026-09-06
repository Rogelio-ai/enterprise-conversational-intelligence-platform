from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
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
        ForeignKeyConstraint(
            [
                'selected_cash_count_id', 'tenant_id', 'organization_id',
                'location_id', 'id',
            ],
            [
                'cash_counts.id', 'cash_counts.tenant_id',
                'cash_counts.organization_id', 'cash_counts.location_id',
                'cash_counts.cash_session_id',
            ],
            name='fk_cash_sessions_selected_count_scope', ondelete='RESTRICT',
            use_alter=True,
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_cash_sessions_command_scope',
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
        UniqueConstraint(
            'tenant_id', 'close_actor_scope', 'close_idempotency_key',
            name='uq_cash_sessions_close_idempotency',
        ),
        CheckConstraint(
            "status IN ('OPEN','CLOSED')", name='ck_cash_sessions_status',
        ),
        CheckConstraint(
            'open_slot IS NULL OR open_slot = 1',
            name='ck_cash_sessions_open_slot',
        ),
        CheckConstraint(
            "(status='OPEN' AND open_slot=1 AND selected_cash_count_id IS NULL "
            "AND final_movement_version IS NULL AND frozen_expected_cash IS NULL "
            "AND frozen_variance IS NULL AND closed_at IS NULL "
            "AND closed_by_actor_type IS NULL AND closed_by_actor_id IS NULL "
            "AND closed_by_actor_reference IS NULL AND variance_reason IS NULL "
            "AND close_actor_scope IS NULL AND close_idempotency_key IS NULL "
            "AND close_request_schema_version IS NULL "
            "AND close_request_fingerprint IS NULL) OR "
            "(status='CLOSED' AND open_slot IS NULL "
            "AND selected_cash_count_id IS NOT NULL "
            "AND final_movement_version IS NOT NULL "
            "AND frozen_expected_cash IS NOT NULL AND frozen_variance IS NOT NULL "
            "AND closed_at IS NOT NULL AND closed_by_actor_type IS NOT NULL "
            "AND close_actor_scope IS NOT NULL AND close_idempotency_key IS NOT NULL "
            "AND close_request_schema_version IS NOT NULL "
            "AND close_request_fingerprint IS NOT NULL)",
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
        CheckConstraint(
            "(status='OPEN' AND closed_by_actor_type IS NULL) OR "
            "(status='CLOSED' AND ((closed_by_actor_type='EMPLOYEE' "
            "AND closed_by_actor_id IS NOT NULL "
            "AND closed_by_actor_reference IS NULL) OR "
            "(closed_by_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') "
            "AND closed_by_actor_id IS NULL "
            "AND closed_by_actor_reference IS NOT NULL)))",
            name='ck_cash_sessions_close_actor',
        ),
        CheckConstraint(
            "(status='OPEN') OR (frozen_variance=0) OR "
            "(variance_reason IS NOT NULL AND TRIM(variance_reason)<>'')",
            name='ck_cash_sessions_variance_reason',
        ),
        CheckConstraint(
            'final_movement_version IS NULL OR final_movement_version >= 0',
            name='ck_cash_sessions_final_version',
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
    selected_cash_count_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    final_movement_version: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    frozen_expected_cash: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    frozen_variance: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    closed_by_actor_type: Mapped[str | None] = mapped_column(
        String(24), nullable=True
    )
    closed_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    closed_by_actor_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    variance_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    close_actor_scope: Mapped[str | None] = mapped_column(
        String(200, collation='ascii_bin'), nullable=True
    )
    close_idempotency_key: Mapped[str | None] = mapped_column(
        String(128, collation='ascii_bin'), nullable=True
    )
    close_request_schema_version: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    close_request_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )


class CashMovement(Base):
    __tablename__ = 'cash_movements'
    __table_args__ = (
        ForeignKeyConstraint(
            [
                'cash_session_id', 'tenant_id', 'organization_id', 'location_id',
            ],
            [
                'cash_sessions.id', 'cash_sessions.tenant_id',
                'cash_sessions.organization_id', 'cash_sessions.location_id',
            ],
            name='fk_cash_movements_session_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'restaurant_payment_id', 'tenant_id', 'organization_id',
                'location_id',
            ],
            [
                'restaurant_payments.id', 'restaurant_payments.tenant_id',
                'restaurant_payments.organization_id',
                'restaurant_payments.location_id',
            ],
            name='fk_cash_movements_payment_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            'cash_session_id', name='uq_cash_movements_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'idempotency_actor_scope', 'idempotency_key',
            name='uq_cash_movements_idempotency',
        ),
        UniqueConstraint(
            'cash_session_id', 'opening_float_slot',
            name='uq_cash_movements_opening_float',
        ),
        UniqueConstraint(
            'restaurant_payment_id', 'movement_type',
            name='uq_cash_movements_payment_type',
        ),
        CheckConstraint(
            "movement_type IN ('OPENING_FLOAT','CUSTOMER_TENDER',"
            "'CUSTOMER_CHANGE','CASH_IN','CASH_OUT','WITHDRAWAL','ADJUSTMENT')",
            name='ck_cash_movements_type',
        ),
        CheckConstraint('amount <> 0', name='ck_cash_movements_nonzero'),
        CheckConstraint(
            "(movement_type IN ('OPENING_FLOAT','CUSTOMER_TENDER','CASH_IN') "
            "AND amount>0) OR "
            "(movement_type IN ('CUSTOMER_CHANGE','CASH_OUT','WITHDRAWAL') "
            "AND amount<0) OR (movement_type='ADJUSTMENT' AND amount<>0)",
            name='ck_cash_movements_sign',
        ),
        CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_cash_movements_currency',
        ),
        CheckConstraint(
            "(movement_type='OPENING_FLOAT' AND opening_float_slot=1) OR "
            "(movement_type<>'OPENING_FLOAT' AND opening_float_slot IS NULL)",
            name='ck_cash_movements_opening_float_slot',
        ),
        CheckConstraint(
            "movement_type='OPENING_FLOAT' OR "
            "(reason IS NOT NULL AND TRIM(reason)<>'')",
            name='ck_cash_movements_reason',
        ),
        CheckConstraint(
            "(movement_type IN ('CUSTOMER_TENDER','CUSTOMER_CHANGE') "
            "AND restaurant_payment_id IS NOT NULL) OR "
            "(movement_type NOT IN ('CUSTOMER_TENDER','CUSTOMER_CHANGE') "
            "AND restaurant_payment_id IS NULL)",
            name='ck_cash_movements_payment_relation',
        ),
        CheckConstraint(
            'request_schema_version >= 1', name='ck_cash_movements_version',
        ),
        CheckConstraint(
            "(actor_type='EMPLOYEE' AND actor_id IS NOT NULL "
            "AND actor_reference IS NULL) OR "
            "(actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') "
            "AND actor_id IS NULL AND actor_reference IS NOT NULL)",
            name='ck_cash_movements_actor',
        ),
        CheckConstraint(
            "(authorized_by_actor_type='EMPLOYEE' "
            "AND authorized_by_actor_id IS NOT NULL "
            "AND authorized_by_actor_reference IS NULL) OR "
            "(authorized_by_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') "
            "AND authorized_by_actor_id IS NULL "
            "AND authorized_by_actor_reference IS NOT NULL)",
            name='ck_cash_movements_authorizer',
        ),
        Index(
            'ix_cash_movements_session_history',
            'tenant_id', 'cash_session_id', 'recorded_at', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cash_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_payment_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3, collation='ascii_bin'), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    authorized_by_actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    authorized_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    authorized_by_actor_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    opening_float_slot: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    idempotency_actor_scope: Mapped[str] = mapped_column(
        String(200, collation='ascii_bin'), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False
    )
    request_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )


class CashCount(Base):
    __tablename__ = 'cash_counts'
    __table_args__ = (
        ForeignKeyConstraint(
            [
                'cash_session_id', 'tenant_id', 'organization_id', 'location_id',
            ],
            [
                'cash_sessions.id', 'cash_sessions.tenant_id',
                'cash_sessions.organization_id', 'cash_sessions.location_id',
            ],
            name='fk_cash_counts_session_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            'cash_session_id', name='uq_cash_counts_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'idempotency_actor_scope', 'idempotency_key',
            name='uq_cash_counts_idempotency',
        ),
        CheckConstraint('counted_amount >= 0', name='ck_cash_counts_amount'),
        CheckConstraint(
            'captured_movement_version >= 0 AND request_schema_version >= 1',
            name='ck_cash_counts_versions',
        ),
        CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_cash_counts_currency',
        ),
        CheckConstraint(
            "(actor_type='EMPLOYEE' AND actor_id IS NOT NULL "
            "AND actor_reference IS NULL) OR "
            "(actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') "
            "AND actor_id IS NULL AND actor_reference IS NOT NULL)",
            name='ck_cash_counts_actor',
        ),
        Index(
            'ix_cash_counts_session_history',
            'tenant_id', 'cash_session_id', 'counted_at', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cash_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    counted_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3, collation='ascii_bin'), nullable=False
    )
    captured_movement_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    counted_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    idempotency_actor_scope: Mapped[str] = mapped_column(
        String(200, collation='ascii_bin'), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False
    )
    request_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=text('CURRENT_TIMESTAMP')
    )
