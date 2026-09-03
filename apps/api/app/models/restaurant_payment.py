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
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class LocationPaymentExecutorConfiguration(TimestampMixin, Base):
    __tablename__ = 'location_payment_executor_configurations'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_payment_executor_configurations_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_payment_executor_configurations_location_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_payment_executor_configurations_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'executor_key',
            name='uq_payment_executor_configurations_location_key',
        ),
        CheckConstraint(
            "topology IN ('LOCAL','EXTERNAL')",
            name='ck_payment_executor_configurations_topology',
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_payment_executor_configurations_status',
        ),
        CheckConstraint(
            'selection_priority >= 0',
            name='ck_payment_executor_configurations_priority',
        ),
        Index(
            'ix_payment_executor_configurations_lookup',
            'tenant_id', 'organization_id', 'location_id', 'status',
            'selection_priority', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    executor_key: Mapped[str] = mapped_column(String(128, collation='utf8mb4_bin'), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    adapter_kind: Mapped[str] = mapped_column(String(128, collation='utf8mb4_bin'), nullable=False)
    topology: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    credential_binding: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    selection_priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default=text('100')
    )


class LocationPaymentExecutorCapability(TimestampMixin, Base):
    __tablename__ = 'location_payment_executor_capabilities'
    __table_args__ = (
        ForeignKeyConstraint(
            ['executor_configuration_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'location_payment_executor_configurations.id',
                'location_payment_executor_configurations.tenant_id',
                'location_payment_executor_configurations.organization_id',
                'location_payment_executor_configurations.location_id',
            ],
            name='fk_payment_executor_capabilities_configuration_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'executor_configuration_id', 'method_category', 'currency',
            name='uq_payment_executor_capabilities_method_currency',
        ),
        CheckConstraint(
            "method_category IN ('CASH','CARD','TRANSFER')",
            name='ck_payment_executor_capabilities_method',
        ),
        CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_payment_executor_capabilities_currency',
        ),
        Index(
            'ix_payment_executor_capabilities_lookup',
            'tenant_id', 'organization_id', 'location_id',
            'method_category', 'currency', 'executor_configuration_id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    executor_configuration_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    method_category: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(3, collation='ascii_bin'), nullable=False)


class RestaurantPayment(TimestampMixin, Base):
    __tablename__ = 'restaurant_payments'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_restaurant_payments_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(
            ['check_id', 'tenant_id', 'organization_id', 'location_id'],
            ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'],
            name='fk_restaurant_payments_check_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['payer_diner_session_id', 'tenant_id', 'organization_id', 'location_id'],
            ['diner_sessions.id', 'diner_sessions.tenant_id', 'diner_sessions.organization_id', 'diner_sessions.location_id'],
            name='fk_restaurant_payments_payer_diner_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['executor_configuration_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'location_payment_executor_configurations.id',
                'location_payment_executor_configurations.tenant_id',
                'location_payment_executor_configurations.organization_id',
                'location_payment_executor_configurations.location_id',
            ],
            name='fk_restaurant_payments_executor_configuration_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_restaurant_payments_scope'),
        UniqueConstraint('id', 'tenant_id', name='uq_restaurant_payments_id_tenant'),
        UniqueConstraint('tenant_id', 'actor_scope', 'idempotency_key', name='uq_restaurant_payments_idempotency'),
        UniqueConstraint(
            'executor_configuration_id', 'external_reference',
            name='uq_restaurant_payments_configuration_external_reference',
        ),
        CheckConstraint("state IN ('RESERVED','IN_PROGRESS','SUCCEEDED','FAILED','REJECTED','UNCERTAIN','CANCELLED')", name='ck_restaurant_payments_state'),
        CheckConstraint("method_category IN ('CASH','CARD','TRANSFER')", name='ck_restaurant_payments_method'),
        CheckConstraint("payer_type IN ('DINER','OTHER')", name='ck_restaurant_payments_payer_type'),
        CheckConstraint("initiated_actor_type IN ('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')", name='ck_restaurant_payments_actor'),
        CheckConstraint('amount > 0 AND check_version >= 1 AND request_schema_version >= 1 AND attempt_count >= 0', name='ck_restaurant_payments_values'),
        CheckConstraint(
            "(payer_type='DINER' AND payer_diner_session_id IS NOT NULL) OR "
            "(payer_type='OTHER' AND payer_diner_session_id IS NULL AND payer_reference IS NOT NULL)",
            name='ck_restaurant_payments_payer',
        ),
        CheckConstraint(
            "(state='IN_PROGRESS' AND claim_token IS NOT NULL AND claim_expires_at IS NOT NULL) OR "
            "(state<>'IN_PROGRESS' AND claim_token IS NULL AND claim_expires_at IS NULL)",
            name='ck_restaurant_payments_claim',
        ),
        CheckConstraint(
            "(method_category='CASH' AND cash_tendered_amount IS NOT NULL AND cash_change_due IS NOT NULL "
            "AND cash_tendered_amount >= amount AND cash_change_due = cash_tendered_amount - amount "
            "AND executor_key IS NULL AND provider_idempotency_key IS NULL) OR "
            "(method_category<>'CASH' AND cash_tendered_amount IS NULL AND cash_change_due IS NULL "
            "AND executor_key IS NOT NULL AND provider_idempotency_key IS NOT NULL)",
            name='ck_restaurant_payments_execution_evidence',
        ),
        Index('ix_restaurant_payments_check_state', 'tenant_id', 'check_id', 'state', 'id'),
        Index('ix_restaurant_payments_claim', 'tenant_id', 'state', 'claim_expires_at', 'id'),
        Index('ix_restaurant_payments_external', 'tenant_id', 'executor_key', 'external_reference', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_fingerprint: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method_category: Mapped[str] = mapped_column(String(16), nullable=False)
    payer_type: Mapped[str] = mapped_column(String(16), nullable=False)
    payer_diner_session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payer_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    initiated_actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    initiated_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    initiated_actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    actor_scope: Mapped[str] = mapped_column(String(200, collation='ascii_bin'), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128, collation='ascii_bin'), nullable=False)
    request_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    request_fingerprint: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default='RESERVED', server_default=text("'RESERVED'"))
    executor_key: Mapped[str | None] = mapped_column(String(128, collation='utf8mb4_bin'), nullable=True)
    executor_configuration_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    provider_idempotency_key: Mapped[str | None] = mapped_column(String(128, collation='ascii_bin'), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    external_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instrument_brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instrument_last_four: Mapped[str | None] = mapped_column(String(4, collation='ascii_bin'), nullable=True)
    instrument_display: Mapped[str | None] = mapped_column(String(100), nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36, collation='ascii_bin'), nullable=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text('0'))
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cash_tendered_amount: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    cash_change_due: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class RestaurantPaymentAttempt(Base):
    __tablename__ = 'restaurant_payment_attempts'
    __table_args__ = (
        ForeignKeyConstraint(
            ['payment_id', 'tenant_id'], ['restaurant_payments.id', 'restaurant_payments.tenant_id'],
            name='fk_restaurant_payment_attempts_payment_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('payment_id', 'attempt_sequence', name='uq_restaurant_payment_attempts_sequence'),
        UniqueConstraint('claim_token', name='uq_restaurant_payment_attempts_claim'),
        CheckConstraint("attempt_type IN ('EXECUTE','RETRY','RECOVER','STALE_RECOVERY','RECONCILE')", name='ck_restaurant_payment_attempts_type'),
        CheckConstraint("result IN ('IN_PROGRESS','SUCCEEDED','FAILED','REJECTED','UNCERTAIN','CANCELLED','FENCED')", name='ck_restaurant_payment_attempts_result'),
        CheckConstraint("actor_type IN ('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')", name='ck_restaurant_payment_attempts_actor'),
        CheckConstraint("(result='IN_PROGRESS' AND completed_at IS NULL) OR (result<>'IN_PROGRESS' AND completed_at IS NOT NULL)", name='ck_restaurant_payment_attempts_lifecycle'),
        Index('ix_restaurant_payment_attempts_ordered', 'tenant_id', 'payment_id', 'attempt_sequence', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payment_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attempt_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_type: Mapped[str] = mapped_column(String(24), nullable=False)
    executor_key: Mapped[str] = mapped_column(String(128, collation='utf8mb4_bin'), nullable=False)
    claim_token: Mapped[str] = mapped_column(String(36, collation='ascii_bin'), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128, collation='ascii_bin'), nullable=True)
    causation_id: Mapped[str | None] = mapped_column(String(128, collation='ascii_bin'), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    external_call_started_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False, default='IN_PROGRESS')
    external_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    external_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result_fingerprint: Mapped[str | None] = mapped_column(String(64, collation='ascii_bin'), nullable=True)


class RestaurantCheckSettlement(Base):
    __tablename__ = 'restaurant_check_settlements'
    __table_args__ = (
        ForeignKeyConstraint(
            ['check_id', 'tenant_id', 'organization_id', 'location_id'],
            ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'],
            name='fk_check_settlements_check_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['payment_id', 'tenant_id', 'organization_id', 'location_id'],
            ['restaurant_payments.id', 'restaurant_payments.tenant_id', 'restaurant_payments.organization_id', 'restaurant_payments.location_id'],
            name='fk_check_settlements_payment_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('payment_id', name='uq_check_settlements_payment'),
        CheckConstraint('amount > 0', name='ck_check_settlements_amount'),
        CheckConstraint("application_actor_type IN ('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')", name='ck_check_settlements_actor'),
        Index('ix_check_settlements_check', 'tenant_id', 'check_id', 'applied_at', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payment_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    application_actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    application_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    application_actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
