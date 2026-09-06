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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


OPTIONS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


class PaidCheckDispatch(TimestampMixin, Base):
    """Immutable paid-check evidence queued for the existing local connector."""

    __tablename__ = 'paid_check_dispatches'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_paid_check_dispatches_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_check_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_checks.id', 'restaurant_checks.tenant_id',
                'restaurant_checks.organization_id', 'restaurant_checks.location_id',
            ],
            name='fk_paid_check_dispatches_check_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['cashier_resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_paid_check_dispatches_resource_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['connector_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'preparation_delivery_connectors.id',
                'preparation_delivery_connectors.tenant_id',
                'preparation_delivery_connectors.organization_id',
                'preparation_delivery_connectors.location_id',
            ],
            name='fk_paid_check_dispatches_connector_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['created_by_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_paid_check_dispatches_membership', ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', name='uq_paid_check_dispatches_id_tenant'),
        UniqueConstraint('tenant_id', 'operation_id', name='uq_paid_check_dispatches_operation'),
        UniqueConstraint(
            'tenant_id', 'actor_scope', 'idempotency_key',
            name='uq_paid_check_dispatches_idempotency',
        ),
        CheckConstraint('check_version >= 1', name='ck_paid_check_dispatches_check_version'),
        CheckConstraint(
            "state IN ('PENDING','IN_PROGRESS','DESTINATION_SUBMISSION_ACCEPTED',"
            "'RETRYABLE_FAILURE','UNCERTAIN','ACTION_REQUIRED')",
            name='ck_paid_check_dispatches_state',
        ),
        CheckConstraint('attempt_count >= 0', name='ck_paid_check_dispatches_attempt_count'),
        CheckConstraint(
            "(state = 'IN_PROGRESS' AND claim_token IS NOT NULL AND claim_expires_at IS NOT NULL) "
            "OR (state <> 'IN_PROGRESS' AND claim_token IS NULL AND claim_expires_at IS NULL)",
            name='ck_paid_check_dispatches_claim',
        ),
        Index(
            'ix_paid_check_dispatches_eligibility',
            'tenant_id', 'location_id', 'connector_id', 'state', 'available_at', 'id',
        ),
        Index(
            'ix_paid_check_dispatches_check',
            'tenant_id', 'restaurant_check_id', 'created_at', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_check_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    cashier_resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cashier_resource_code_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    cashier_resource_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    connector_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    connector_code_snapshot: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    connector_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    local_target_key_snapshot: Mapped[str] = mapped_column(
        String(128, collation='utf8mb4_bin'), nullable=False
    )
    operation_id: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False
    )
    actor_scope: Mapped[str] = mapped_column(
        String(200, collation='ascii_bin'), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False
    )
    request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    state: Mapped[str] = mapped_column(
        String(40), nullable=False, default='PENDING', server_default=text("'PENDING'")
    )
    payload_schema: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    payload_text: Mapped[str] = mapped_column(Text(collation='utf8mb4_bin'), nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    claim_token: Mapped[str | None] = mapped_column(
        String(36, collation='ascii_bin'), nullable=True
    )
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text('0')
    )
    available_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    last_error_kind: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class PaidCheckDispatchAttempt(TimestampMixin, Base):
    __tablename__ = 'paid_check_dispatch_attempts'
    __table_args__ = (
        ForeignKeyConstraint(
            ['dispatch_id', 'tenant_id'],
            ['paid_check_dispatches.id', 'paid_check_dispatches.tenant_id'],
            name='fk_paid_check_attempts_dispatch_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['connector_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'preparation_delivery_connectors.id',
                'preparation_delivery_connectors.tenant_id',
                'preparation_delivery_connectors.organization_id',
                'preparation_delivery_connectors.location_id',
            ],
            name='fk_paid_check_attempts_connector_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'dispatch_id', 'attempt_sequence', name='uq_paid_check_attempts_sequence'
        ),
        UniqueConstraint('claim_token', name='uq_paid_check_attempts_claim'),
        UniqueConstraint(
            'tenant_id', 'connector_id', 'claim_request_id',
            name='uq_paid_check_attempts_claim_request',
        ),
        CheckConstraint(
            "attempt_type IN ('DELIVER','RETRY','RECOVERY')",
            name='ck_paid_check_attempts_type',
        ),
        CheckConstraint(
            "result IN ('IN_PROGRESS','DESTINATION_SUBMISSION_ACCEPTED',"
            "'RETRYABLE_FAILURE','UNCERTAIN','ACTION_REQUIRED')",
            name='ck_paid_check_attempts_result',
        ),
        CheckConstraint(
            "(result = 'IN_PROGRESS' AND ended_at IS NULL AND result_fingerprint IS NULL) "
            "OR (result <> 'IN_PROGRESS' AND ended_at IS NOT NULL AND result_fingerprint IS NOT NULL)",
            name='ck_paid_check_attempts_lifecycle',
        ),
        Index(
            'ix_paid_check_attempts_ordered',
            'tenant_id', 'dispatch_id', 'attempt_sequence', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dispatch_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    connector_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attempt_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_type: Mapped[str] = mapped_column(String(16), nullable=False)
    claim_token: Mapped[str] = mapped_column(
        String(36, collation='ascii_bin'), nullable=False
    )
    claim_request_id: Mapped[str | None] = mapped_column(
        String(128, collation='ascii_bin'), nullable=True
    )
    actor_principal_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    result: Mapped[str] = mapped_column(
        String(40), nullable=False, default='IN_PROGRESS',
        server_default=text("'IN_PROGRESS'"),
    )
    result_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
    local_job_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    error_kind: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
