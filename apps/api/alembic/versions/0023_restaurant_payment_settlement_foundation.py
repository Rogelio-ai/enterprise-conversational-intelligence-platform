"""canonical Restaurant Payment and Settlement foundation

Revision ID: 0023_restaurant_payment_settlement_foundation
Revises: 0022_restaurant_check_settlement_foundation
Create Date: 2026-08-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0023_restaurant_payment_settlement_foundation'
down_revision: str | None = '0022_restaurant_check_settlement_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    'restaurant_payment.read': 'Read canonical Restaurant Payments and settlements.',
    'restaurant_payment.manage': 'Initiate and confirm canonical Restaurant Payments.',
    'restaurant_payment.recover': 'Recover uncertain Restaurant Payment execution.',
}


def _options() -> dict[str, str]:
    return {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def _seed_permissions() -> None:
    connection = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.BigInteger()), sa.column('code', sa.String()), sa.column('description', sa.String()))
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()), sa.column('status', sa.String()))
    grants = sa.table('role_permissions', sa.column('id', sa.BigInteger()), sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()))
    role_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE')).scalars())
    for code, description in PERMISSIONS.items():
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(code=code, description=description))
            permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one()
        for role_id in role_ids:
            if connection.execute(sa.select(grants.c.id).where(grants.c.role_id == role_id, grants.c.permission_id == permission_id)).scalar_one_or_none() is None:
                connection.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    options = _options()
    op.drop_constraint('ck_restaurant_checks_lifecycle', 'restaurant_checks', type_='check')
    op.drop_constraint('ck_restaurant_checks_status', 'restaurant_checks', type_='check')
    op.add_column('restaurant_checks', sa.Column('settled_at', sa.DateTime(), nullable=True))
    op.add_column('restaurant_checks', sa.Column('settled_actor_type', sa.String(24), nullable=True))
    op.add_column('restaurant_checks', sa.Column('settled_actor_id', sa.BigInteger(), nullable=True))
    op.add_column('restaurant_checks', sa.Column('settled_actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True))
    op.add_column('restaurant_checks', sa.Column('continuation_decision', sa.String(16), server_default=sa.text("'NONE'"), nullable=False))
    op.add_column('restaurant_checks', sa.Column('continuation_decided_at', sa.DateTime(), nullable=True))
    op.add_column('restaurant_checks', sa.Column('continuation_actor_type', sa.String(24), nullable=True))
    op.add_column('restaurant_checks', sa.Column('continuation_actor_id', sa.BigInteger(), nullable=True))
    op.add_column('restaurant_checks', sa.Column('continuation_actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True))
    op.create_check_constraint('ck_restaurant_checks_status', 'restaurant_checks', "status IN ('OPEN','FROZEN','SETTLED','CANCELLED')")
    op.create_check_constraint('ck_restaurant_checks_continuation', 'restaurant_checks', "continuation_decision IN ('NONE','PENDING','YES','NO')")
    op.create_check_constraint(
        'ck_restaurant_checks_lifecycle', 'restaurant_checks',
        "(status='OPEN' AND frozen_at IS NULL AND settled_at IS NULL AND cancelled_at IS NULL AND continuation_decision='NONE') OR "
        "(status='FROZEN' AND frozen_at IS NOT NULL AND settled_at IS NULL AND cancelled_at IS NULL AND continuation_decision='NONE') OR "
        "(status='SETTLED' AND frozen_at IS NOT NULL AND settled_at IS NOT NULL AND cancelled_at IS NULL AND continuation_decision IN ('PENDING','YES','NO')) OR "
        "(status='CANCELLED' AND cancelled_at IS NOT NULL AND settled_at IS NULL AND continuation_decision='NONE')",
    )

    op.create_table(
        'restaurant_check_table_scopes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('check_id', sa.BigInteger(), nullable=False),
        sa.Column('service_session_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=False),
        sa.Column('lock_phase', sa.String(16), server_default=sa.text("'CHECK'"), nullable=False),
        sa.Column('active_slot', sa.SmallInteger(), server_default=sa.text('1'), nullable=True),
        sa.Column('acquired_at', sa.DateTime(), nullable=False),
        sa.Column('acquired_actor_type', sa.String(24), nullable=False),
        sa.Column('acquired_actor_id', sa.BigInteger(), nullable=True),
        sa.Column('acquired_actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.Column('released_actor_type', sa.String(24), nullable=True),
        sa.Column('released_actor_id', sa.BigInteger(), nullable=True),
        sa.Column('released_actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('release_reason', sa.String(500), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('check_id', 'service_session_id', name='uq_check_table_scopes_check_service'),
        sa.UniqueConstraint('tenant_id', 'service_session_id', 'active_slot', name='uq_check_table_scopes_service_active'),
        sa.CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_check_table_scopes_active_slot'),
        sa.CheckConstraint("lock_phase IN ('CHECK','CONTINUATION','RELEASED')", name='ck_check_table_scopes_phase'),
        sa.CheckConstraint("(lock_phase IN ('CHECK','CONTINUATION') AND active_slot=1 AND released_at IS NULL) OR (lock_phase='RELEASED' AND active_slot IS NULL AND released_at IS NOT NULL)", name='ck_check_table_scopes_lifecycle'),
        sa.ForeignKeyConstraint(['check_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'], name='fk_check_table_scopes_check_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['service_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id'], ['restaurant_service_sessions.id', 'restaurant_service_sessions.tenant_id', 'restaurant_service_sessions.organization_id', 'restaurant_service_sessions.location_id', 'restaurant_service_sessions.resource_id'], name='fk_check_table_scopes_service_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_check_table_scopes_check_active', 'restaurant_check_table_scopes', ['tenant_id', 'check_id', 'active_slot', 'service_session_id'])

    op.create_table(
        'restaurant_payments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('check_id', sa.BigInteger(), nullable=False),
        sa.Column('check_version', sa.BigInteger(), nullable=False),
        sa.Column('check_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('amount', sa.Numeric(19, 4), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('method_category', sa.String(16), nullable=False),
        sa.Column('payer_type', sa.String(16), nullable=False),
        sa.Column('payer_diner_session_id', sa.BigInteger(), nullable=True),
        sa.Column('payer_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('initiated_actor_type', sa.String(24), nullable=False),
        sa.Column('initiated_actor_id', sa.BigInteger(), nullable=True),
        sa.Column('initiated_actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('actor_scope', sa.String(200, collation='ascii_bin'), nullable=False),
        sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('request_schema_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('state', sa.String(16), server_default=sa.text("'RESERVED'"), nullable=False),
        sa.Column('executor_key', sa.String(128, collation='utf8mb4_bin'), nullable=True),
        sa.Column('provider_idempotency_key', sa.String(128, collation='ascii_bin'), nullable=True),
        sa.Column('external_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('external_status', sa.String(64), nullable=True),
        sa.Column('instrument_brand', sa.String(64), nullable=True),
        sa.Column('instrument_last_four', sa.String(4, collation='ascii_bin'), nullable=True),
        sa.Column('instrument_display', sa.String(100), nullable=True),
        sa.Column('claim_token', sa.String(36, collation='ascii_bin'), nullable=True),
        sa.Column('claim_expires_at', sa.DateTime(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_error_code', sa.String(64), nullable=True),
        sa.Column('last_error_message', sa.String(500), nullable=True),
        sa.Column('cash_tendered_amount', sa.Numeric(19, 4), nullable=True),
        sa.Column('cash_change_due', sa.Numeric(19, 4), nullable=True),
        sa.Column('terminal_at', sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_restaurant_payments_scope'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_restaurant_payments_id_tenant'),
        sa.UniqueConstraint('tenant_id', 'actor_scope', 'idempotency_key', name='uq_restaurant_payments_idempotency'),
        sa.CheckConstraint("state IN ('RESERVED','IN_PROGRESS','SUCCEEDED','FAILED','REJECTED','UNCERTAIN','CANCELLED')", name='ck_restaurant_payments_state'),
        sa.CheckConstraint("method_category IN ('CASH','CARD','TRANSFER')", name='ck_restaurant_payments_method'),
        sa.CheckConstraint("payer_type IN ('DINER','OTHER')", name='ck_restaurant_payments_payer_type'),
        sa.CheckConstraint("initiated_actor_type IN ('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')", name='ck_restaurant_payments_actor'),
        sa.CheckConstraint('amount > 0 AND check_version >= 1 AND request_schema_version >= 1 AND attempt_count >= 0', name='ck_restaurant_payments_values'),
        sa.CheckConstraint("(payer_type='DINER' AND payer_diner_session_id IS NOT NULL) OR (payer_type='OTHER' AND payer_diner_session_id IS NULL AND payer_reference IS NOT NULL)", name='ck_restaurant_payments_payer'),
        sa.CheckConstraint("(state='IN_PROGRESS' AND claim_token IS NOT NULL AND claim_expires_at IS NOT NULL) OR (state<>'IN_PROGRESS' AND claim_token IS NULL AND claim_expires_at IS NULL)", name='ck_restaurant_payments_claim'),
        sa.CheckConstraint("(method_category='CASH' AND cash_tendered_amount IS NOT NULL AND cash_change_due IS NOT NULL AND cash_tendered_amount >= amount AND cash_change_due = cash_tendered_amount - amount AND executor_key IS NULL AND provider_idempotency_key IS NULL) OR (method_category<>'CASH' AND cash_tendered_amount IS NULL AND cash_change_due IS NULL AND executor_key IS NOT NULL AND provider_idempotency_key IS NOT NULL)", name='ck_restaurant_payments_execution_evidence'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_restaurant_payments_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['check_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'], name='fk_restaurant_payments_check_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['payer_diner_session_id', 'tenant_id', 'organization_id', 'location_id'], ['diner_sessions.id', 'diner_sessions.tenant_id', 'diner_sessions.organization_id', 'diner_sessions.location_id'], name='fk_restaurant_payments_payer_diner_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_restaurant_payments_check_state', 'restaurant_payments', ['tenant_id', 'check_id', 'state', 'id'])
    op.create_index('ix_restaurant_payments_claim', 'restaurant_payments', ['tenant_id', 'state', 'claim_expires_at', 'id'])
    op.create_index('ix_restaurant_payments_external', 'restaurant_payments', ['tenant_id', 'executor_key', 'external_reference', 'id'])

    op.create_table(
        'restaurant_payment_attempts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('payment_id', sa.BigInteger(), nullable=False),
        sa.Column('attempt_sequence', sa.Integer(), nullable=False),
        sa.Column('attempt_type', sa.String(24), nullable=False),
        sa.Column('executor_key', sa.String(128, collation='utf8mb4_bin'), nullable=False),
        sa.Column('claim_token', sa.String(36, collation='ascii_bin'), nullable=False),
        sa.Column('actor_type', sa.String(24), nullable=False),
        sa.Column('actor_id', sa.BigInteger(), nullable=True),
        sa.Column('actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('correlation_id', sa.String(128, collation='ascii_bin'), nullable=True),
        sa.Column('causation_id', sa.String(128, collation='ascii_bin'), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('external_call_started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.String(16), nullable=False),
        sa.Column('external_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('external_status', sa.String(64), nullable=True),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('result_fingerprint', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_id', 'attempt_sequence', name='uq_restaurant_payment_attempts_sequence'),
        sa.UniqueConstraint('claim_token', name='uq_restaurant_payment_attempts_claim'),
        sa.CheckConstraint("attempt_type IN ('EXECUTE','RETRY','RECOVER','STALE_RECOVERY','RECONCILE')", name='ck_restaurant_payment_attempts_type'),
        sa.CheckConstraint("result IN ('IN_PROGRESS','SUCCEEDED','FAILED','REJECTED','UNCERTAIN','CANCELLED','FENCED')", name='ck_restaurant_payment_attempts_result'),
        sa.CheckConstraint("actor_type IN ('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')", name='ck_restaurant_payment_attempts_actor'),
        sa.CheckConstraint("(result='IN_PROGRESS' AND completed_at IS NULL) OR (result<>'IN_PROGRESS' AND completed_at IS NOT NULL)", name='ck_restaurant_payment_attempts_lifecycle'),
        sa.ForeignKeyConstraint(['payment_id', 'tenant_id'], ['restaurant_payments.id', 'restaurant_payments.tenant_id'], name='fk_restaurant_payment_attempts_payment_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_restaurant_payment_attempts_ordered', 'restaurant_payment_attempts', ['tenant_id', 'payment_id', 'attempt_sequence', 'id'])

    op.create_table(
        'restaurant_check_settlements',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('check_id', sa.BigInteger(), nullable=False),
        sa.Column('payment_id', sa.BigInteger(), nullable=False),
        sa.Column('amount', sa.Numeric(19, 4), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('application_actor_type', sa.String(24), nullable=False),
        sa.Column('application_actor_id', sa.BigInteger(), nullable=True),
        sa.Column('application_actor_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('applied_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_id', name='uq_check_settlements_payment'),
        sa.CheckConstraint('amount > 0', name='ck_check_settlements_amount'),
        sa.CheckConstraint("application_actor_type IN ('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')", name='ck_check_settlements_actor'),
        sa.ForeignKeyConstraint(['check_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'], name='fk_check_settlements_check_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['payment_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_payments.id', 'restaurant_payments.tenant_id', 'restaurant_payments.organization_id', 'restaurant_payments.location_id'], name='fk_check_settlements_payment_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_check_settlements_check', 'restaurant_check_settlements', ['tenant_id', 'check_id', 'applied_at', 'id'])
    _seed_permissions()


def downgrade() -> None:
    # MySQL-family DDL is non-transactional.  Keep downgrade restart-safe if an
    # operator resumes after an interruption between dependent table drops.
    op.execute('DROP TABLE IF EXISTS restaurant_check_settlements')
    op.execute('DROP TABLE IF EXISTS restaurant_payment_attempts')
    op.execute('DROP TABLE IF EXISTS restaurant_payments')
    op.execute('DROP TABLE IF EXISTS restaurant_check_table_scopes')
    op.drop_constraint('ck_restaurant_checks_lifecycle', 'restaurant_checks', type_='check')
    op.drop_constraint('ck_restaurant_checks_continuation', 'restaurant_checks', type_='check')
    op.drop_constraint('ck_restaurant_checks_status', 'restaurant_checks', type_='check')
    op.drop_column('restaurant_checks', 'settled_actor_reference')
    op.drop_column('restaurant_checks', 'settled_actor_id')
    op.drop_column('restaurant_checks', 'settled_actor_type')
    op.drop_column('restaurant_checks', 'settled_at')
    op.drop_column('restaurant_checks', 'continuation_actor_reference')
    op.drop_column('restaurant_checks', 'continuation_actor_id')
    op.drop_column('restaurant_checks', 'continuation_actor_type')
    op.drop_column('restaurant_checks', 'continuation_decided_at')
    op.drop_column('restaurant_checks', 'continuation_decision')
    op.create_check_constraint('ck_restaurant_checks_status', 'restaurant_checks', "status IN ('OPEN','FROZEN','CANCELLED')")
    op.create_check_constraint(
        'ck_restaurant_checks_lifecycle', 'restaurant_checks',
        "(status='OPEN' AND frozen_at IS NULL AND cancelled_at IS NULL) OR "
        "(status='FROZEN' AND frozen_at IS NOT NULL AND cancelled_at IS NULL) OR "
        "(status='CANCELLED' AND cancelled_at IS NOT NULL)",
    )
