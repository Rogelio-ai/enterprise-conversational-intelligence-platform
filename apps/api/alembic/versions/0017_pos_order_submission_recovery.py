"""establish durable POS order submission and recovery

Revision ID: 0017_pos_order_submission_recovery
Revises: 0016_canonical_order_commercial_acceptance
Create Date: 2026-08-28
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0017_pos_order_submission_recovery'
down_revision: str | None = '0016_canonical_order_commercial_acceptance'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WS_18_PERMISSIONS = {
    'pos_submission.read': 'Read POS order submission state and history.',
    'pos_submission.submit': 'Submit accepted Restaurant Orders to a POS.',
    'pos_submission.retry': 'Retry safely retryable POS order submissions.',
    'pos_submission.recover': 'Recover uncertain POS order submissions.',
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
    for code, description in WS_18_PERMISSIONS.items():
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(code=code, description=description))
            permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one()
        for role_id in role_ids:
            if connection.execute(sa.select(grants.c.id).where(grants.c.role_id == role_id, grants.c.permission_id == permission_id)).scalar_one_or_none() is None:
                connection.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    options = _options()
    op.create_unique_constraint(
        'uq_restaurant_orders_pos_scope', 'restaurant_orders',
        ['id', 'tenant_id', 'organization_id', 'location_id'],
    )
    op.create_unique_constraint(
        'uq_restaurant_order_components_scope', 'restaurant_order_item_components',
        ['id', 'tenant_id', 'order_id', 'order_item_id'],
    )
    op.create_table(
        'location_pos_connections',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_key', sa.String(128, collation='utf8mb4_bin'), nullable=False),
        sa.Column('external_location_id', sa.String(200, collation='utf8mb4_bin'), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('active_slot', sa.SmallInteger(), server_default=sa.text('1'), nullable=True),
        sa.Column('stable_replay_supported', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.Column('recovery_supported', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('location_id', 'active_slot', name='uq_location_pos_connections_active'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_location_pos_connections_scope'),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_location_pos_connections_status'),
        sa.CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_location_pos_connections_active_slot'),
        sa.CheckConstraint("(status = 'ACTIVE' AND active_slot = 1 AND (stable_replay_supported = 1 OR recovery_supported = 1)) OR (status = 'INACTIVE' AND active_slot IS NULL)", name='ck_location_pos_connections_lifecycle'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_location_pos_connections_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_location_pos_connections_location_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_location_pos_connections_lookup', 'location_pos_connections', ['tenant_id', 'location_id', 'status', 'id'])

    op.create_table(
        'pos_order_submissions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('connection_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_key', sa.String(128, collation='utf8mb4_bin'), nullable=False),
        sa.Column('external_location_id', sa.String(200, collation='utf8mb4_bin'), nullable=False),
        sa.Column('stable_replay_supported', sa.Boolean(), nullable=False),
        sa.Column('recovery_supported', sa.Boolean(), nullable=False),
        sa.Column('idempotency_key', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('request_schema_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('request_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('state', sa.String(32), nullable=False),
        sa.Column('external_order_id', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('external_status', sa.String(32), nullable=True),
        sa.Column('claim_token', sa.String(36, collation='ascii_bin'), nullable=True),
        sa.Column('claim_expires_at', sa.DateTime(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('last_error_kind', sa.String(32), nullable=True),
        sa.Column('last_error_message', sa.String(500), nullable=True),
        sa.Column('initiated_actor_type', sa.String(32), nullable=False),
        sa.Column('initiated_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('initiated_principal_reference', sa.String(128), nullable=True),
        sa.Column('terminal_at', sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'restaurant_order_id', 'connector_key', name='uq_pos_order_submissions_materialization'),
        sa.UniqueConstraint('tenant_id', 'connector_key', 'external_location_id', 'idempotency_key', name='uq_pos_order_submissions_external_operation'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_pos_order_submissions_id_tenant'),
        sa.UniqueConstraint('id', 'tenant_id', 'restaurant_order_id', name='uq_pos_order_submissions_scope'),
        sa.CheckConstraint("state IN ('IN_PROGRESS','SUCCEEDED','RETRYABLE_FAILURE','REJECTED','UNCERTAIN','ACTION_REQUIRED')", name='ck_pos_order_submissions_state'),
        sa.CheckConstraint('request_schema_version >= 1 AND attempt_count >= 1', name='ck_pos_order_submissions_versions'),
        sa.CheckConstraint("(state = 'IN_PROGRESS' AND claim_token IS NOT NULL AND claim_expires_at IS NOT NULL) OR (state <> 'IN_PROGRESS' AND claim_token IS NULL AND claim_expires_at IS NULL)", name='ck_pos_order_submissions_claim'),
        sa.CheckConstraint("(initiated_actor_type = 'EMPLOYEE' AND initiated_membership_id IS NOT NULL AND initiated_principal_reference IS NULL) OR (initiated_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND initiated_membership_id IS NULL AND initiated_principal_reference IS NOT NULL)", name='ck_pos_order_submissions_actor'),
        sa.CheckConstraint("(state = 'SUCCEEDED' AND external_order_id IS NOT NULL) OR state <> 'SUCCEEDED'", name='ck_pos_order_submissions_success'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_pos_order_submissions_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_orders.id', 'restaurant_orders.tenant_id', 'restaurant_orders.organization_id', 'restaurant_orders.location_id'], name='fk_pos_order_submissions_order_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['connection_id', 'tenant_id', 'organization_id', 'location_id'], ['location_pos_connections.id', 'location_pos_connections.tenant_id', 'location_pos_connections.organization_id', 'location_pos_connections.location_id'], name='fk_pos_order_submissions_connection_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['initiated_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_pos_order_submissions_membership', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_pos_order_submissions_state_claim', 'pos_order_submissions', ['tenant_id', 'state', 'claim_expires_at', 'id'])
    op.create_index('ix_pos_order_submissions_location', 'pos_order_submissions', ['tenant_id', 'location_id', 'connector_key', 'id'])
    op.create_index('ix_pos_order_submissions_external', 'pos_order_submissions', ['tenant_id', 'connector_key', 'external_order_id', 'id'])

    op.create_table(
        'pos_order_submission_lines',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('submission_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_item_id', sa.BigInteger(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('external_product_id', sa.String(200, collation='utf8mb4_bin'), nullable=False),
        sa.Column('external_line_reference', sa.String(200, collation='utf8mb4_bin'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('submission_id', 'restaurant_order_item_id', name='uq_pos_submission_lines_order_item'),
        sa.UniqueConstraint('submission_id', 'external_line_reference', name='uq_pos_submission_lines_external_ref'),
        sa.UniqueConstraint('id', 'tenant_id', 'submission_id', 'restaurant_order_id', 'restaurant_order_item_id', name='uq_pos_submission_lines_scope'),
        sa.ForeignKeyConstraint(['submission_id', 'tenant_id', 'restaurant_order_id'], ['pos_order_submissions.id', 'pos_order_submissions.tenant_id', 'pos_order_submissions.restaurant_order_id'], name='fk_pos_submission_lines_submission_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'], ['restaurant_order_items.id', 'restaurant_order_items.tenant_id', 'restaurant_order_items.order_id'], name='fk_pos_submission_lines_order_item_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_pos_submission_lines_ordered', 'pos_order_submission_lines', ['tenant_id', 'submission_id', 'position', 'id'])

    op.create_table(
        'pos_order_submission_components',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_item_id', sa.BigInteger(), nullable=False),
        sa.Column('submission_id', sa.BigInteger(), nullable=False),
        sa.Column('submission_line_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_item_component_id', sa.BigInteger(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('external_product_id', sa.String(200, collation='utf8mb4_bin'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('submission_id', 'restaurant_order_item_component_id', name='uq_pos_submission_components_source'),
        sa.ForeignKeyConstraint(['submission_line_id', 'tenant_id', 'submission_id', 'restaurant_order_id', 'restaurant_order_item_id'], ['pos_order_submission_lines.id', 'pos_order_submission_lines.tenant_id', 'pos_order_submission_lines.submission_id', 'pos_order_submission_lines.restaurant_order_id', 'pos_order_submission_lines.restaurant_order_item_id'], name='fk_pos_submission_components_line_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['restaurant_order_item_component_id', 'tenant_id', 'restaurant_order_id', 'restaurant_order_item_id'], ['restaurant_order_item_components.id', 'restaurant_order_item_components.tenant_id', 'restaurant_order_item_components.order_id', 'restaurant_order_item_components.order_item_id'], name='fk_pos_submission_components_component_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_pos_submission_components_ordered', 'pos_order_submission_components', ['tenant_id', 'submission_line_id', 'position', 'id'])

    op.create_table(
        'pos_order_submission_attempts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('submission_id', sa.BigInteger(), nullable=False),
        sa.Column('attempt_sequence', sa.Integer(), nullable=False),
        sa.Column('attempt_type', sa.String(32), nullable=False),
        sa.Column('claim_token', sa.String(36, collation='ascii_bin'), nullable=False),
        sa.Column('actor_type', sa.String(32), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('actor_principal_reference', sa.String(128), nullable=True),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.String(32), server_default=sa.text("'IN_PROGRESS'"), nullable=False),
        sa.Column('error_kind', sa.String(32), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('external_order_id', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('submission_id', 'attempt_sequence', name='uq_pos_submission_attempts_sequence'),
        sa.UniqueConstraint('claim_token', name='uq_pos_submission_attempts_claim'),
        sa.CheckConstraint("attempt_type IN ('CREATE','RETRY','RECOVER','STALE_RECOVERY')", name='ck_pos_submission_attempts_type'),
        sa.CheckConstraint("result IN ('IN_PROGRESS','SUCCEEDED','RETRYABLE_FAILURE','REJECTED','UNCERTAIN','ACTION_REQUIRED','DEFINITE_ABSENCE','FENCED')", name='ck_pos_submission_attempts_result'),
        sa.CheckConstraint("(result = 'IN_PROGRESS' AND ended_at IS NULL) OR (result <> 'IN_PROGRESS' AND ended_at IS NOT NULL)", name='ck_pos_submission_attempts_lifecycle'),
        sa.CheckConstraint("(actor_type = 'EMPLOYEE' AND actor_membership_id IS NOT NULL AND actor_principal_reference IS NULL) OR (actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND actor_membership_id IS NULL AND actor_principal_reference IS NOT NULL)", name='ck_pos_submission_attempts_actor'),
        sa.ForeignKeyConstraint(['submission_id', 'tenant_id'], ['pos_order_submissions.id', 'pos_order_submissions.tenant_id'], name='fk_pos_submission_attempts_submission_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['actor_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_pos_submission_attempts_membership', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_pos_submission_attempts_ordered', 'pos_order_submission_attempts', ['tenant_id', 'submission_id', 'attempt_sequence', 'id'])
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('pos_order_submission_attempts')
    op.drop_table('pos_order_submission_components')
    op.drop_table('pos_order_submission_lines')
    op.drop_table('pos_order_submissions')
    op.drop_table('location_pos_connections')
    op.drop_constraint(
        'uq_restaurant_order_components_scope',
        'restaurant_order_item_components',
        type_='unique',
    )
    op.drop_constraint('uq_restaurant_orders_pos_scope', 'restaurant_orders', type_='unique')
    # Preserve global permission rows and grants; their later provenance is unknowable.
