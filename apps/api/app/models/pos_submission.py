from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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


class LocationPosConnection(TimestampMixin, Base):
    __tablename__ = 'location_pos_connections'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_location_pos_connections_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_location_pos_connections_location_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('location_id', 'active_slot', name='uq_location_pos_connections_active'),
        UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_location_pos_connections_scope'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_location_pos_connections_status'),
        CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_location_pos_connections_active_slot'),
        CheckConstraint(
            "(status = 'ACTIVE' AND active_slot = 1 AND (stable_replay_supported = 1 OR recovery_supported = 1)) OR "
            "(status = 'INACTIVE' AND active_slot IS NULL)",
            name='ck_location_pos_connections_lifecycle',
        ),
        Index('ix_location_pos_connections_lookup', 'tenant_id', 'location_id', 'status', 'id'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    connector_key: Mapped[str] = mapped_column(String(128, collation='utf8mb4_bin'), nullable=False)
    external_location_id: Mapped[str] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'"))
    active_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, default=1, server_default=text('1'))
    stable_replay_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text('1'))
    recovery_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('0'))


class PosOrderSubmission(TimestampMixin, Base):
    __tablename__ = 'pos_order_submissions'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_pos_order_submissions_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(
            ['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'],
            ['restaurant_orders.id', 'restaurant_orders.tenant_id', 'restaurant_orders.organization_id', 'restaurant_orders.location_id'],
            name='fk_pos_order_submissions_order_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['connection_id', 'tenant_id', 'organization_id', 'location_id'],
            ['location_pos_connections.id', 'location_pos_connections.tenant_id', 'location_pos_connections.organization_id', 'location_pos_connections.location_id'],
            name='fk_pos_order_submissions_connection_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['initiated_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_pos_order_submissions_membership', ondelete='RESTRICT',
        ),
        UniqueConstraint('tenant_id', 'restaurant_order_id', 'connector_key', name='uq_pos_order_submissions_materialization'),
        UniqueConstraint('tenant_id', 'connector_key', 'external_location_id', 'idempotency_key', name='uq_pos_order_submissions_external_operation'),
        UniqueConstraint('id', 'tenant_id', name='uq_pos_order_submissions_id_tenant'),
        UniqueConstraint('id', 'tenant_id', 'restaurant_order_id', name='uq_pos_order_submissions_scope'),
        CheckConstraint(
            "state IN ('IN_PROGRESS','SUCCEEDED','RETRYABLE_FAILURE','REJECTED','UNCERTAIN','ACTION_REQUIRED')",
            name='ck_pos_order_submissions_state',
        ),
        CheckConstraint('request_schema_version >= 1 AND attempt_count >= 1', name='ck_pos_order_submissions_versions'),
        CheckConstraint(
            "(state = 'IN_PROGRESS' AND claim_token IS NOT NULL AND claim_expires_at IS NOT NULL) OR "
            "(state <> 'IN_PROGRESS' AND claim_token IS NULL AND claim_expires_at IS NULL)",
            name='ck_pos_order_submissions_claim',
        ),
        CheckConstraint(
            "(initiated_actor_type = 'EMPLOYEE' AND initiated_membership_id IS NOT NULL AND initiated_principal_reference IS NULL) OR "
            "(initiated_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND initiated_membership_id IS NULL AND initiated_principal_reference IS NOT NULL)",
            name='ck_pos_order_submissions_actor',
        ),
        CheckConstraint(
            "(state = 'SUCCEEDED' AND external_order_id IS NOT NULL) OR state <> 'SUCCEEDED'",
            name='ck_pos_order_submissions_success',
        ),
        Index('ix_pos_order_submissions_state_claim', 'tenant_id', 'state', 'claim_expires_at', 'id'),
        Index('ix_pos_order_submissions_location', 'tenant_id', 'location_id', 'connector_key', 'id'),
        Index('ix_pos_order_submissions_external', 'tenant_id', 'connector_key', 'external_order_id', 'id'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    connection_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    connector_key: Mapped[str] = mapped_column(String(128, collation='utf8mb4_bin'), nullable=False)
    external_location_id: Mapped[str] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=False)
    stable_replay_supported: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recovery_supported: Mapped[bool] = mapped_column(Boolean, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128, collation='ascii_bin'), nullable=False)
    request_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    request_fingerprint: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    external_order_id: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    external_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36, collation='ascii_bin'), nullable=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    last_error_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    initiated_actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    initiated_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    initiated_principal_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class PosOrderSubmissionLine(Base):
    __tablename__ = 'pos_order_submission_lines'
    __table_args__ = (
        ForeignKeyConstraint(
            ['submission_id', 'tenant_id', 'restaurant_order_id'],
            ['pos_order_submissions.id', 'pos_order_submissions.tenant_id', 'pos_order_submissions.restaurant_order_id'],
            name='fk_pos_submission_lines_submission_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'],
            ['restaurant_order_items.id', 'restaurant_order_items.tenant_id', 'restaurant_order_items.order_id'],
            name='fk_pos_submission_lines_order_item_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('submission_id', 'restaurant_order_item_id', name='uq_pos_submission_lines_order_item'),
        UniqueConstraint('submission_id', 'external_line_reference', name='uq_pos_submission_lines_external_ref'),
        UniqueConstraint('id', 'tenant_id', 'submission_id', 'restaurant_order_id', 'restaurant_order_item_id', name='uq_pos_submission_lines_scope'),
        Index('ix_pos_submission_lines_ordered', 'tenant_id', 'submission_id', 'position', 'id'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submission_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    external_product_id: Mapped[str] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=False)
    external_line_reference: Mapped[str] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=False)


class PosOrderSubmissionComponent(Base):
    __tablename__ = 'pos_order_submission_components'
    __table_args__ = (
        ForeignKeyConstraint(
            ['submission_line_id', 'tenant_id', 'submission_id', 'restaurant_order_id', 'restaurant_order_item_id'],
            ['pos_order_submission_lines.id', 'pos_order_submission_lines.tenant_id', 'pos_order_submission_lines.submission_id', 'pos_order_submission_lines.restaurant_order_id', 'pos_order_submission_lines.restaurant_order_item_id'],
            name='fk_pos_submission_components_line_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_order_item_component_id', 'tenant_id', 'restaurant_order_id', 'restaurant_order_item_id'],
            ['restaurant_order_item_components.id', 'restaurant_order_item_components.tenant_id', 'restaurant_order_item_components.order_id', 'restaurant_order_item_components.order_item_id'],
            name='fk_pos_submission_components_component_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('submission_id', 'restaurant_order_item_component_id', name='uq_pos_submission_components_source'),
        Index('ix_pos_submission_components_ordered', 'tenant_id', 'submission_line_id', 'position', 'id'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submission_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submission_line_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_item_component_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    external_product_id: Mapped[str] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=False)


class PosOrderSubmissionAttempt(Base):
    __tablename__ = 'pos_order_submission_attempts'
    __table_args__ = (
        ForeignKeyConstraint(
            ['submission_id', 'tenant_id'],
            ['pos_order_submissions.id', 'pos_order_submissions.tenant_id'],
            name='fk_pos_submission_attempts_submission_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_pos_submission_attempts_membership', ondelete='RESTRICT',
        ),
        UniqueConstraint('submission_id', 'attempt_sequence', name='uq_pos_submission_attempts_sequence'),
        UniqueConstraint('claim_token', name='uq_pos_submission_attempts_claim'),
        CheckConstraint("attempt_type IN ('CREATE','RETRY','RECOVER','STALE_RECOVERY')", name='ck_pos_submission_attempts_type'),
        CheckConstraint(
            "result IN ('IN_PROGRESS','SUCCEEDED','RETRYABLE_FAILURE','REJECTED','UNCERTAIN','ACTION_REQUIRED','DEFINITE_ABSENCE','FENCED')",
            name='ck_pos_submission_attempts_result',
        ),
        CheckConstraint(
            "(result = 'IN_PROGRESS' AND ended_at IS NULL) OR (result <> 'IN_PROGRESS' AND ended_at IS NOT NULL)",
            name='ck_pos_submission_attempts_lifecycle',
        ),
        CheckConstraint(
            "(actor_type = 'EMPLOYEE' AND actor_membership_id IS NOT NULL AND actor_principal_reference IS NULL) OR "
            "(actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND actor_membership_id IS NULL AND actor_principal_reference IS NOT NULL)",
            name='ck_pos_submission_attempts_actor',
        ),
        Index('ix_pos_submission_attempts_ordered', 'tenant_id', 'submission_id', 'attempt_sequence', 'id'),
        {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submission_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attempt_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt_type: Mapped[str] = mapped_column(String(32), nullable=False)
    claim_token: Mapped[str] = mapped_column(String(36, collation='ascii_bin'), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_membership_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_principal_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False, default='IN_PROGRESS')
    error_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_order_id: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
