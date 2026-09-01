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
    JSON,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class RestaurantCheck(TimestampMixin, Base):
    __tablename__ = 'restaurant_checks'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_restaurant_checks_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_restaurant_checks_location_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['controller_diner_session_id', 'tenant_id', 'organization_id', 'location_id'],
            ['diner_sessions.id', 'diner_sessions.tenant_id', 'diner_sessions.organization_id', 'diner_sessions.location_id'],
            name='fk_restaurant_checks_controller_diner_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_restaurant_checks_scope'),
        UniqueConstraint('id', 'tenant_id', name='uq_restaurant_checks_id_tenant'),
        CheckConstraint("status IN ('OPEN','FROZEN','CANCELLED')", name='ck_restaurant_checks_status'),
        CheckConstraint('version >= 1 AND fingerprint_schema_version >= 1', name='ck_restaurant_checks_versions'),
        CheckConstraint('consumption_total >= 0 AND gratuity_total >= 0 AND liability_total >= 0', name='ck_restaurant_checks_money'),
        CheckConstraint('liability_total = consumption_total + gratuity_total', name='ck_restaurant_checks_arithmetic'),
        CheckConstraint("controller_actor_type IN ('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')", name='ck_restaurant_checks_controller_actor'),
        CheckConstraint("created_actor_type IN ('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')", name='ck_restaurant_checks_created_actor'),
        CheckConstraint(
            "(status='OPEN' AND frozen_at IS NULL AND cancelled_at IS NULL) OR "
            "(status='FROZEN' AND frozen_at IS NOT NULL AND cancelled_at IS NULL) OR "
            "(status='CANCELLED' AND cancelled_at IS NOT NULL)",
            name='ck_restaurant_checks_lifecycle',
        ),
        Index('ix_restaurant_checks_location_status', 'tenant_id', 'location_id', 'status', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='OPEN', server_default=text("'OPEN'"))
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default=text('1'))
    current_fingerprint: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    fingerprint_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text('1'))
    consumption_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    gratuity_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False, default=Decimal('0'), server_default=text('0'))
    liability_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    controller_actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    controller_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    controller_actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    controller_diner_session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    created_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    frozen_actor_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    frozen_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    frozen_actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    cancelled_actor_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    cancelled_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancelled_actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class RestaurantCheckMember(TimestampMixin, Base):
    __tablename__ = 'restaurant_check_members'
    __table_args__ = (
        ForeignKeyConstraint(
            ['check_id', 'tenant_id', 'organization_id', 'location_id'],
            ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'],
            name='fk_check_members_check_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id'],
            ['diner_sessions.id', 'diner_sessions.tenant_id', 'diner_sessions.organization_id', 'diner_sessions.location_id', 'diner_sessions.resource_id', 'diner_sessions.service_session_id', 'diner_sessions.conversation_id'],
            name='fk_check_members_diner_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('tenant_id', 'diner_session_id', 'active_slot', name='uq_check_members_diner_active'),
        UniqueConstraint('check_id', 'diner_session_id', name='uq_check_members_check_diner'),
        CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_check_members_active_slot'),
        CheckConstraint("relationship IN ('CONTROLLER','INCLUDED')", name='ck_check_members_relationship'),
        CheckConstraint('acquired_version >= 1 AND (released_version IS NULL OR released_version >= acquired_version)', name='ck_check_members_versions'),
        CheckConstraint('(active_slot=1 AND released_at IS NULL) OR (active_slot IS NULL AND released_at IS NOT NULL)', name='ck_check_members_lifecycle'),
        Index('ix_check_members_check_active', 'tenant_id', 'check_id', 'active_slot', 'diner_session_id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    diner_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    service_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    relationship: Mapped[str] = mapped_column(String(16), nullable=False)
    active_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, default=1, server_default=text('1'))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    acquired_actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    acquired_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    acquired_actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    acquired_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    released_actor_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    released_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    released_actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    release_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    released_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class RestaurantCheckAllocation(TimestampMixin, Base):
    __tablename__ = 'restaurant_check_allocations'
    __table_args__ = (
        ForeignKeyConstraint(
            ['check_id', 'tenant_id', 'organization_id', 'location_id'],
            ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'],
            name='fk_check_allocations_check_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'],
            ['restaurant_orders.id', 'restaurant_orders.tenant_id', 'restaurant_orders.organization_id', 'restaurant_orders.location_id'],
            name='fk_check_allocations_order_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['source_diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'source_resource_id', 'source_service_session_id', 'source_conversation_id'],
            ['diner_sessions.id', 'diner_sessions.tenant_id', 'diner_sessions.organization_id', 'diner_sessions.location_id', 'diner_sessions.resource_id', 'diner_sessions.service_session_id', 'diner_sessions.conversation_id'],
            name='fk_check_allocations_diner_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('tenant_id', 'restaurant_order_id', 'ownership_slot', name='uq_check_allocations_order_owner'),
        UniqueConstraint('check_id', 'restaurant_order_id', name='uq_check_allocations_check_order'),
        CheckConstraint("state IN ('CLAIMED','RELEASED','SETTLED')", name='ck_check_allocations_state'),
        CheckConstraint('ownership_slot IS NULL OR ownership_slot = 1', name='ck_check_allocations_owner_slot'),
        CheckConstraint(
            "(state='CLAIMED' AND ownership_slot=1 AND released_at IS NULL AND settled_at IS NULL) OR "
            "(state='SETTLED' AND ownership_slot=1 AND released_at IS NULL AND settled_at IS NOT NULL) OR "
            "(state='RELEASED' AND ownership_slot IS NULL AND released_at IS NOT NULL AND settled_at IS NULL)",
            name='ck_check_allocations_lifecycle',
        ),
        CheckConstraint('accepted_payable_amount >= 0 AND claimed_version >= 1', name='ck_check_allocations_values'),
        Index('ix_check_allocations_check_state', 'tenant_id', 'check_id', 'state', 'restaurant_order_id'),
        Index('ix_check_allocations_service_balance', 'tenant_id', 'source_service_session_id', 'state', 'restaurant_order_id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_diner_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_service_session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accepted_payable_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    accepted_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    accepted_commercial_fingerprint: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default='CLAIMED', server_default=text("'CLAIMED'"))
    ownership_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, default=1, server_default=text('1'))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    claimed_actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    claimed_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    claimed_actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    claimed_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    released_actor_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    released_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    released_actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    release_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    released_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    settlement_reference: Mapped[str | None] = mapped_column(String(200, collation='ascii_bin'), nullable=True)


class RestaurantCheckVersion(TimestampMixin, Base):
    __tablename__ = 'restaurant_check_versions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['check_id', 'tenant_id', 'organization_id', 'location_id'],
            ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'],
            name='fk_check_versions_check_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('check_id', 'version', name='uq_check_versions_check_version'),
        UniqueConstraint('check_id', 'fingerprint', name='uq_check_versions_check_fingerprint'),
        CheckConstraint('version >= 1 AND schema_version >= 1', name='ck_check_versions_versions'),
        CheckConstraint('consumption_total >= 0 AND gratuity_amount >= 0 AND liability_total = consumption_total + gratuity_amount', name='ck_check_versions_money'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    member_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    allocation_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    gratuity_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    consumption_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    gratuity_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    liability_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class RestaurantCheckGratuity(TimestampMixin, Base):
    __tablename__ = 'restaurant_check_gratuities'
    __table_args__ = (
        ForeignKeyConstraint(
            ['check_id', 'tenant_id', 'organization_id', 'location_id'],
            ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'],
            name='fk_check_gratuities_check_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('check_id', 'check_version', name='uq_check_gratuities_check_version'),
        CheckConstraint("input_type IN ('PERCENTAGE','FIXED_AMOUNT')", name='ck_check_gratuities_type'),
        CheckConstraint("rounding_policy_id='CURRENCY_MINOR_UNIT_HALF_DOWN_V1'", name='ck_check_gratuities_rounding'),
        CheckConstraint('input_value >= 0 AND calculation_basis >= 0 AND calculated_amount >= 0 AND check_version >= 1', name='ck_check_gratuities_values'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    input_type: Mapped[str] = mapped_column(String(24), nullable=False)
    input_value: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    calculation_basis: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    calculated_amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rounding_policy_id: Mapped[str] = mapped_column(String(48), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_reference: Mapped[str | None] = mapped_column(String(200, collation='utf8mb4_bin'), nullable=True)
    elected_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)


class RestaurantCheckCommand(TimestampMixin, Base):
    __tablename__ = 'restaurant_check_commands'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_check_commands_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['check_id', 'tenant_id'], ['restaurant_checks.id', 'restaurant_checks.tenant_id'], name='fk_check_commands_check_tenant', ondelete='RESTRICT'),
        UniqueConstraint('tenant_id', 'actor_scope', 'idempotency_key', name='uq_check_commands_idempotency'),
        CheckConstraint('result_version >= 1', name='ck_check_commands_result_version'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    check_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_scope: Mapped[str] = mapped_column(String(200, collation='ascii_bin'), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128, collation='ascii_bin'), nullable=False)
    operation: Mapped[str] = mapped_column(String(48), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64, collation='ascii_bin'), nullable=False)
    result_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
