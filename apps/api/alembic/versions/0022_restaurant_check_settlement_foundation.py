"""restaurant_check_settlement_foundation

Revision ID: 0022_restaurant_check_settlement_foundation
Revises: 0021_restaurant_local_connector_machine_delivery
Create Date: 2026-08-31 22:34:22.756219
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0022_restaurant_check_settlement_foundation'
down_revision: str | None = '0021_restaurant_local_connector_machine_delivery'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _seed_permissions() -> None:
    connection = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.BigInteger()), sa.column('code', sa.String()), sa.column('description', sa.String()))
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()), sa.column('status', sa.String()))
    grants = sa.table('role_permissions', sa.column('id', sa.BigInteger()), sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()))
    values = {
        'restaurant_check.read': 'Read canonical Restaurant Checks and table balances.',
        'restaurant_check.manage': 'Manage canonical Restaurant Checks.',
    }
    for code, description in values.items():
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(code=code, description=description))
            permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one()
        role_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE')).scalars())
        for role_id in role_ids:
            exists = connection.execute(sa.select(grants.c.id).where(grants.c.role_id == role_id, grants.c.permission_id == permission_id)).scalar_one_or_none()
            if exists is None:
                connection.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_diner_sessions_check_controller_scope', 'diner_sessions',
        ['id', 'tenant_id', 'organization_id', 'location_id'],
    )
    op.create_table('restaurant_checks',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('organization_id', sa.BigInteger(), nullable=False),
    sa.Column('location_id', sa.BigInteger(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('status', sa.String(length=16), server_default=sa.text("'OPEN'"), nullable=False),
    sa.Column('version', sa.BigInteger(), server_default=sa.text('1'), nullable=False),
    sa.Column('current_fingerprint', sa.String(length=64, collation='ascii_bin'), nullable=False),
    sa.Column('fingerprint_schema_version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.Column('consumption_total', sa.Numeric(precision=19, scale=4), nullable=False),
    sa.Column('gratuity_total', sa.Numeric(precision=19, scale=4), server_default=sa.text('0'), nullable=False),
    sa.Column('liability_total', sa.Numeric(precision=19, scale=4), nullable=False),
    sa.Column('controller_actor_type', sa.String(length=24), nullable=False),
    sa.Column('controller_actor_id', sa.BigInteger(), nullable=True),
    sa.Column('controller_actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True),
    sa.Column('controller_diner_session_id', sa.BigInteger(), nullable=True),
    sa.Column('created_actor_type', sa.String(length=24), nullable=False),
    sa.Column('created_actor_id', sa.BigInteger(), nullable=True),
    sa.Column('created_actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True),
    sa.Column('frozen_at', sa.DateTime(), nullable=True),
    sa.Column('frozen_actor_type', sa.String(length=24), nullable=True),
    sa.Column('frozen_actor_id', sa.BigInteger(), nullable=True),
    sa.Column('frozen_actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(), nullable=True),
    sa.Column('cancelled_actor_type', sa.String(length=24), nullable=True),
    sa.Column('cancelled_actor_id', sa.BigInteger(), nullable=True),
    sa.Column('cancelled_actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True),
    sa.Column('cancellation_reason', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("(status='OPEN' AND frozen_at IS NULL AND cancelled_at IS NULL) OR (status='FROZEN' AND frozen_at IS NOT NULL AND cancelled_at IS NULL) OR (status='CANCELLED' AND cancelled_at IS NOT NULL)", name='ck_restaurant_checks_lifecycle'),
    sa.CheckConstraint("controller_actor_type IN ('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')", name='ck_restaurant_checks_controller_actor'),
    sa.CheckConstraint("created_actor_type IN ('EMPLOYEE','DINER','SYSTEM','AGENT','EXTERNAL_SYSTEM')", name='ck_restaurant_checks_created_actor'),
    sa.CheckConstraint("status IN ('OPEN','FROZEN','CANCELLED')", name='ck_restaurant_checks_status'),
    sa.CheckConstraint('consumption_total >= 0 AND gratuity_total >= 0 AND liability_total >= 0', name='ck_restaurant_checks_money'),
    sa.CheckConstraint('liability_total = consumption_total + gratuity_total', name='ck_restaurant_checks_arithmetic'),
    sa.CheckConstraint('version >= 1 AND fingerprint_schema_version >= 1', name='ck_restaurant_checks_versions'),
    sa.ForeignKeyConstraint(['controller_diner_session_id', 'tenant_id', 'organization_id', 'location_id'], ['diner_sessions.id', 'diner_sessions.tenant_id', 'diner_sessions.organization_id', 'diner_sessions.location_id'], name='fk_restaurant_checks_controller_diner_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_restaurant_checks_location_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_restaurant_checks_tenant', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_restaurant_checks_scope'),
    sa.UniqueConstraint('id', 'tenant_id', name='uq_restaurant_checks_id_tenant'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_restaurant_checks_location_status', 'restaurant_checks', ['tenant_id', 'location_id', 'status', 'id'], unique=False)
    op.create_table('restaurant_check_allocations',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('organization_id', sa.BigInteger(), nullable=False),
    sa.Column('location_id', sa.BigInteger(), nullable=False),
    sa.Column('check_id', sa.BigInteger(), nullable=False),
    sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
    sa.Column('source_diner_session_id', sa.BigInteger(), nullable=False),
    sa.Column('source_service_session_id', sa.BigInteger(), nullable=False),
    sa.Column('source_resource_id', sa.BigInteger(), nullable=False),
    sa.Column('source_conversation_id', sa.BigInteger(), nullable=False),
    sa.Column('accepted_payable_amount', sa.Numeric(precision=19, scale=4), nullable=False),
    sa.Column('accepted_currency', sa.String(length=3), nullable=False),
    sa.Column('accepted_commercial_fingerprint', sa.String(length=64, collation='ascii_bin'), nullable=False),
    sa.Column('state', sa.String(length=16), server_default=sa.text("'CLAIMED'"), nullable=False),
    sa.Column('ownership_slot', sa.SmallInteger(), server_default=sa.text('1'), nullable=True),
    sa.Column('claimed_at', sa.DateTime(), nullable=False),
    sa.Column('claimed_actor_type', sa.String(length=24), nullable=False),
    sa.Column('claimed_actor_id', sa.BigInteger(), nullable=True),
    sa.Column('claimed_actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True),
    sa.Column('claimed_version', sa.BigInteger(), nullable=False),
    sa.Column('released_at', sa.DateTime(), nullable=True),
    sa.Column('released_actor_type', sa.String(length=24), nullable=True),
    sa.Column('released_actor_id', sa.BigInteger(), nullable=True),
    sa.Column('released_actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True),
    sa.Column('release_reason', sa.String(length=500), nullable=True),
    sa.Column('released_version', sa.BigInteger(), nullable=True),
    sa.Column('settled_at', sa.DateTime(), nullable=True),
    sa.Column('settlement_reference', sa.String(length=200, collation='ascii_bin'), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("(state='CLAIMED' AND ownership_slot=1 AND released_at IS NULL AND settled_at IS NULL) OR (state='SETTLED' AND ownership_slot=1 AND released_at IS NULL AND settled_at IS NOT NULL) OR (state='RELEASED' AND ownership_slot IS NULL AND released_at IS NOT NULL AND settled_at IS NULL)", name='ck_check_allocations_lifecycle'),
    sa.CheckConstraint("state IN ('CLAIMED','RELEASED','SETTLED')", name='ck_check_allocations_state'),
    sa.CheckConstraint('accepted_payable_amount >= 0 AND claimed_version >= 1', name='ck_check_allocations_values'),
    sa.CheckConstraint('ownership_slot IS NULL OR ownership_slot = 1', name='ck_check_allocations_owner_slot'),
    sa.ForeignKeyConstraint(['check_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'], name='fk_check_allocations_check_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_orders.id', 'restaurant_orders.tenant_id', 'restaurant_orders.organization_id', 'restaurant_orders.location_id'], name='fk_check_allocations_order_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['source_diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'source_resource_id', 'source_service_session_id', 'source_conversation_id'], ['diner_sessions.id', 'diner_sessions.tenant_id', 'diner_sessions.organization_id', 'diner_sessions.location_id', 'diner_sessions.resource_id', 'diner_sessions.service_session_id', 'diner_sessions.conversation_id'], name='fk_check_allocations_diner_scope', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('check_id', 'restaurant_order_id', name='uq_check_allocations_check_order'),
    sa.UniqueConstraint('tenant_id', 'restaurant_order_id', 'ownership_slot', name='uq_check_allocations_order_owner'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_check_allocations_check_state', 'restaurant_check_allocations', ['tenant_id', 'check_id', 'state', 'restaurant_order_id'], unique=False)
    op.create_index('ix_check_allocations_service_balance', 'restaurant_check_allocations', ['tenant_id', 'source_service_session_id', 'state', 'restaurant_order_id'], unique=False)
    op.create_table('restaurant_check_commands',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('check_id', sa.BigInteger(), nullable=False),
    sa.Column('actor_scope', sa.String(length=200, collation='ascii_bin'), nullable=False),
    sa.Column('idempotency_key', sa.String(length=128, collation='ascii_bin'), nullable=False),
    sa.Column('operation', sa.String(length=48), nullable=False),
    sa.Column('request_fingerprint', sa.String(length=64, collation='ascii_bin'), nullable=False),
    sa.Column('result_version', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint('result_version >= 1', name='ck_check_commands_result_version'),
    sa.ForeignKeyConstraint(['check_id', 'tenant_id'], ['restaurant_checks.id', 'restaurant_checks.tenant_id'], name='fk_check_commands_check_tenant', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_check_commands_tenant', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'actor_scope', 'idempotency_key', name='uq_check_commands_idempotency'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('restaurant_check_gratuities',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('organization_id', sa.BigInteger(), nullable=False),
    sa.Column('location_id', sa.BigInteger(), nullable=False),
    sa.Column('check_id', sa.BigInteger(), nullable=False),
    sa.Column('check_version', sa.BigInteger(), nullable=False),
    sa.Column('input_type', sa.String(length=24), nullable=False),
    sa.Column('input_value', sa.Numeric(precision=19, scale=4), nullable=False),
    sa.Column('calculation_basis', sa.Numeric(precision=19, scale=4), nullable=False),
    sa.Column('calculated_amount', sa.Numeric(precision=19, scale=4), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('rounding_policy_id', sa.String(length=48), nullable=False),
    sa.Column('actor_type', sa.String(length=24), nullable=False),
    sa.Column('actor_id', sa.BigInteger(), nullable=True),
    sa.Column('actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True),
    sa.Column('elected_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("input_type IN ('PERCENTAGE','FIXED_AMOUNT')", name='ck_check_gratuities_type'),
    sa.CheckConstraint("rounding_policy_id='CURRENCY_MINOR_UNIT_HALF_DOWN_V1'", name='ck_check_gratuities_rounding'),
    sa.CheckConstraint('input_value >= 0 AND calculation_basis >= 0 AND calculated_amount >= 0 AND check_version >= 1', name='ck_check_gratuities_values'),
    sa.ForeignKeyConstraint(['check_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'], name='fk_check_gratuities_check_scope', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('check_id', 'check_version', name='uq_check_gratuities_check_version'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    op.create_table('restaurant_check_members',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('organization_id', sa.BigInteger(), nullable=False),
    sa.Column('location_id', sa.BigInteger(), nullable=False),
    sa.Column('check_id', sa.BigInteger(), nullable=False),
    sa.Column('diner_session_id', sa.BigInteger(), nullable=False),
    sa.Column('service_session_id', sa.BigInteger(), nullable=False),
    sa.Column('resource_id', sa.BigInteger(), nullable=False),
    sa.Column('conversation_id', sa.BigInteger(), nullable=False),
    sa.Column('relationship', sa.String(length=16), nullable=False),
    sa.Column('active_slot', sa.SmallInteger(), server_default=sa.text('1'), nullable=True),
    sa.Column('acquired_at', sa.DateTime(), nullable=False),
    sa.Column('acquired_actor_type', sa.String(length=24), nullable=False),
    sa.Column('acquired_actor_id', sa.BigInteger(), nullable=True),
    sa.Column('acquired_actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True),
    sa.Column('acquired_version', sa.BigInteger(), nullable=False),
    sa.Column('released_at', sa.DateTime(), nullable=True),
    sa.Column('released_actor_type', sa.String(length=24), nullable=True),
    sa.Column('released_actor_id', sa.BigInteger(), nullable=True),
    sa.Column('released_actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True),
    sa.Column('release_reason', sa.String(length=500), nullable=True),
    sa.Column('released_version', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint("relationship IN ('CONTROLLER','INCLUDED')", name='ck_check_members_relationship'),
    sa.CheckConstraint('(active_slot=1 AND released_at IS NULL) OR (active_slot IS NULL AND released_at IS NOT NULL)', name='ck_check_members_lifecycle'),
    sa.CheckConstraint('acquired_version >= 1 AND (released_version IS NULL OR released_version >= acquired_version)', name='ck_check_members_versions'),
    sa.CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_check_members_active_slot'),
    sa.ForeignKeyConstraint(['check_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'], name='fk_check_members_check_scope', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['diner_session_id', 'tenant_id', 'organization_id', 'location_id', 'resource_id', 'service_session_id', 'conversation_id'], ['diner_sessions.id', 'diner_sessions.tenant_id', 'diner_sessions.organization_id', 'diner_sessions.location_id', 'diner_sessions.resource_id', 'diner_sessions.service_session_id', 'diner_sessions.conversation_id'], name='fk_check_members_diner_scope', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('check_id', 'diner_session_id', name='uq_check_members_check_diner'),
    sa.UniqueConstraint('tenant_id', 'diner_session_id', 'active_slot', name='uq_check_members_diner_active'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    op.create_index('ix_check_members_check_active', 'restaurant_check_members', ['tenant_id', 'check_id', 'active_slot', 'diner_session_id'], unique=False)
    op.create_table('restaurant_check_versions',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.BigInteger(), nullable=False),
    sa.Column('organization_id', sa.BigInteger(), nullable=False),
    sa.Column('location_id', sa.BigInteger(), nullable=False),
    sa.Column('check_id', sa.BigInteger(), nullable=False),
    sa.Column('version', sa.BigInteger(), nullable=False),
    sa.Column('schema_version', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('member_snapshot', sa.JSON(), nullable=False),
    sa.Column('allocation_snapshot', sa.JSON(), nullable=False),
    sa.Column('gratuity_snapshot', sa.JSON(), nullable=False),
    sa.Column('consumption_total', sa.Numeric(precision=19, scale=4), nullable=False),
    sa.Column('gratuity_amount', sa.Numeric(precision=19, scale=4), nullable=False),
    sa.Column('liability_total', sa.Numeric(precision=19, scale=4), nullable=False),
    sa.Column('fingerprint', sa.String(length=64, collation='ascii_bin'), nullable=False),
    sa.Column('actor_type', sa.String(length=24), nullable=False),
    sa.Column('actor_id', sa.BigInteger(), nullable=True),
    sa.Column('actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True),
    sa.Column('recorded_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.CheckConstraint('consumption_total >= 0 AND gratuity_amount >= 0 AND liability_total = consumption_total + gratuity_amount', name='ck_check_versions_money'),
    sa.CheckConstraint('version >= 1 AND schema_version >= 1', name='ck_check_versions_versions'),
    sa.ForeignKeyConstraint(['check_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_checks.id', 'restaurant_checks.tenant_id', 'restaurant_checks.organization_id', 'restaurant_checks.location_id'], name='fk_check_versions_check_scope', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('check_id', 'fingerprint', name='uq_check_versions_check_fingerprint'),
    sa.UniqueConstraint('check_id', 'version', name='uq_check_versions_check_version'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci',
    mysql_engine='InnoDB'
    )
    op.add_column('order_drafts', sa.Column('abandoned_actor_type', sa.String(length=24), nullable=True))
    op.add_column('order_drafts', sa.Column('abandoned_actor_id', sa.BigInteger(), nullable=True))
    op.add_column('order_drafts', sa.Column('abandoned_actor_reference', sa.String(length=200, collation='utf8mb4_bin'), nullable=True))
    op.add_column('order_drafts', sa.Column('abandon_idempotency_key', sa.String(length=128, collation='ascii_bin'), nullable=True))
    op.add_column('order_drafts', sa.Column('abandon_request_fingerprint', sa.String(length=64, collation='ascii_bin'), nullable=True))
    op.create_unique_constraint('uq_order_drafts_abandon_idempotency', 'order_drafts', ['tenant_id', 'conversation_id', 'abandon_idempotency_key'])
    _seed_permissions()


def downgrade() -> None:
    op.drop_constraint('uq_order_drafts_abandon_idempotency', 'order_drafts', type_='unique')
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('order_drafts', 'abandon_request_fingerprint')
    op.drop_column('order_drafts', 'abandon_idempotency_key')
    op.drop_column('order_drafts', 'abandoned_actor_reference')
    op.drop_column('order_drafts', 'abandoned_actor_id')
    op.drop_column('order_drafts', 'abandoned_actor_type')
    op.drop_table('restaurant_check_versions')
    op.drop_table('restaurant_check_members')
    op.drop_table('restaurant_check_gratuities')
    op.drop_table('restaurant_check_commands')
    op.drop_table('restaurant_check_allocations')
    op.drop_table('restaurant_checks')
    op.drop_constraint(
        'uq_diner_sessions_check_controller_scope', 'diner_sessions', type_='unique'
    )
