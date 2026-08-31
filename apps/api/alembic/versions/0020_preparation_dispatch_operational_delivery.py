"""establish durable preparation dispatch operational delivery

Revision ID: 0020_preparation_dispatch_operational_delivery
Revises: 0019_preparation_execution_foundation
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0020_preparation_dispatch_operational_delivery'
down_revision: str | None = '0019_preparation_execution_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _options() -> dict[str, str]:
    return {'mysql_engine': 'InnoDB', 'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def _seed_permission() -> None:
    connection = op.get_bind()
    permissions = sa.table('permissions', sa.column('id', sa.BigInteger()), sa.column('code', sa.String()), sa.column('description', sa.String()))
    roles = sa.table('roles', sa.column('id', sa.BigInteger()), sa.column('name', sa.String()), sa.column('status', sa.String()))
    grants = sa.table('role_permissions', sa.column('id', sa.BigInteger()), sa.column('role_id', sa.BigInteger()), sa.column('permission_id', sa.BigInteger()))
    code = 'preparation.dispatch'
    permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
    if permission_id is None:
        connection.execute(permissions.insert().values(code=code, description='Perform human preparation dispatch interventions.'))
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one()
    role_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE')).scalars())
    for role_id in role_ids:
        if connection.execute(sa.select(grants.c.id).where(grants.c.role_id == role_id, grants.c.permission_id == permission_id)).scalar_one_or_none() is None:
            connection.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    options = _options()
    op.create_unique_constraint(
        'uq_preparation_works_dispatch_scope', 'preparation_works',
        ['id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_area_id'],
    )
    op.create_table(
        'preparation_delivery_connectors',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('auth_subject', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('location_id', 'code', name='uq_preparation_delivery_connectors_location_code'),
        sa.UniqueConstraint('auth_subject', name='uq_preparation_delivery_connectors_auth_subject'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', name='uq_preparation_delivery_connectors_scope'),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_preparation_delivery_connectors_status'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_preparation_delivery_connectors_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_preparation_delivery_connectors_location_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_preparation_delivery_connectors_lookup', 'preparation_delivery_connectors', ['tenant_id', 'location_id', 'status', 'code', 'id'])

    op.create_table(
        'preparation_delivery_destinations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('preparation_area_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('channel', sa.String(32), server_default=sa.text("'PRINTER'"), nullable=False),
        sa.Column('local_target_key', sa.String(128, collation='utf8mb4_bin'), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('active_slot', sa.SmallInteger(), server_default=sa.text('1'), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('location_id', 'code', name='uq_preparation_delivery_destinations_location_code'),
        sa.UniqueConstraint('connector_id', 'local_target_key', 'active_slot', name='uq_preparation_delivery_destinations_active_target'),
        sa.UniqueConstraint('id', 'tenant_id', 'organization_id', 'location_id', 'preparation_area_id', name='uq_preparation_delivery_destinations_scope'),
        sa.CheckConstraint("channel = 'PRINTER'", name='ck_preparation_delivery_destinations_channel'),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_preparation_delivery_destinations_status'),
        sa.CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_preparation_delivery_destinations_active_slot'),
        sa.CheckConstraint("(status = 'ACTIVE' AND active_slot = 1) OR (status = 'INACTIVE' AND active_slot IS NULL)", name='ck_preparation_delivery_destinations_lifecycle'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_preparation_delivery_destinations_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['preparation_area_id', 'tenant_id', 'organization_id', 'location_id'], ['preparation_areas.id', 'preparation_areas.tenant_id', 'preparation_areas.organization_id', 'preparation_areas.location_id'], name='fk_preparation_delivery_destinations_area_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['connector_id', 'tenant_id', 'organization_id', 'location_id'], ['preparation_delivery_connectors.id', 'preparation_delivery_connectors.tenant_id', 'preparation_delivery_connectors.organization_id', 'preparation_delivery_connectors.location_id'], name='fk_preparation_delivery_destinations_connector_scope', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_preparation_delivery_destinations_lookup', 'preparation_delivery_destinations', ['tenant_id', 'location_id', 'preparation_area_id', 'status', 'id'])

    op.create_table(
        'preparation_dispatches',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('restaurant_order_id', sa.BigInteger(), nullable=False),
        sa.Column('preparation_work_id', sa.BigInteger(), nullable=False),
        sa.Column('preparation_area_id', sa.BigInteger(), nullable=False),
        sa.Column('destination_id', sa.BigInteger(), nullable=False),
        sa.Column('operation_kind', sa.String(16), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False),
        sa.Column('operation_id', sa.String(128, collation='ascii_bin'), nullable=False),
        sa.Column('reprint_of_dispatch_id', sa.BigInteger(), nullable=True),
        sa.Column('state', sa.String(40), nullable=False),
        sa.Column('payload_schema', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('payload_text', sa.Text(collation='utf8mb4_bin'), nullable=False),
        sa.Column('payload_fingerprint', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('destination_code_snapshot', sa.String(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column('destination_name_snapshot', sa.String(200), nullable=False),
        sa.Column('destination_channel_snapshot', sa.String(32), nullable=False),
        sa.Column('connector_id_snapshot', sa.BigInteger(), nullable=False),
        sa.Column('connector_code_snapshot', sa.String(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column('connector_name_snapshot', sa.String(200), nullable=False),
        sa.Column('local_target_key_snapshot', sa.String(128, collation='utf8mb4_bin'), nullable=False),
        sa.Column('claim_token', sa.String(36, collation='ascii_bin'), nullable=True),
        sa.Column('claim_expires_at', sa.DateTime(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('available_at', sa.DateTime(), nullable=False),
        sa.Column('last_error_kind', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('last_error_message', sa.String(500), nullable=True),
        sa.Column('initiating_actor_type', sa.String(32), nullable=False),
        sa.Column('initiating_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('initiating_principal_reference', sa.String(128), nullable=True),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column('causation_id', sa.String(128), nullable=True),
        sa.Column('terminal_at', sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'preparation_work_id', 'destination_id', 'generation', name='uq_preparation_dispatches_generation'),
        sa.UniqueConstraint('tenant_id', 'operation_id', name='uq_preparation_dispatches_operation'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_preparation_dispatches_id_tenant'),
        sa.UniqueConstraint('id', 'tenant_id', 'preparation_work_id', 'destination_id', name='uq_preparation_dispatches_reprint_scope'),
        sa.CheckConstraint("operation_kind IN ('INITIAL','REPRINT')", name='ck_preparation_dispatches_operation_kind'),
        sa.CheckConstraint('generation >= 1', name='ck_preparation_dispatches_generation'),
        sa.CheckConstraint("(operation_kind = 'INITIAL' AND generation = 1 AND reprint_of_dispatch_id IS NULL) OR (operation_kind = 'REPRINT' AND generation > 1 AND reprint_of_dispatch_id IS NOT NULL)", name='ck_preparation_dispatches_operation_semantics'),
        sa.CheckConstraint("state IN ('PENDING','IN_PROGRESS','DESTINATION_SUBMISSION_ACCEPTED','RETRYABLE_FAILURE','UNCERTAIN','ACTION_REQUIRED')", name='ck_preparation_dispatches_state'),
        sa.CheckConstraint('attempt_count >= 0', name='ck_preparation_dispatches_attempt_count'),
        sa.CheckConstraint("(state = 'IN_PROGRESS' AND claim_token IS NOT NULL AND claim_expires_at IS NOT NULL) OR (state <> 'IN_PROGRESS' AND claim_token IS NULL AND claim_expires_at IS NULL)", name='ck_preparation_dispatches_claim'),
        sa.CheckConstraint("(initiating_actor_type = 'EMPLOYEE' AND initiating_membership_id IS NOT NULL AND initiating_principal_reference IS NULL) OR (initiating_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND initiating_membership_id IS NULL AND initiating_principal_reference IS NOT NULL)", name='ck_preparation_dispatches_actor'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_preparation_dispatches_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'], ['restaurant_orders.id', 'restaurant_orders.tenant_id', 'restaurant_orders.organization_id', 'restaurant_orders.location_id'], name='fk_preparation_dispatches_order_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['preparation_work_id', 'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id', 'preparation_area_id'], ['preparation_works.id', 'preparation_works.tenant_id', 'preparation_works.organization_id', 'preparation_works.location_id', 'preparation_works.restaurant_order_id', 'preparation_works.preparation_area_id'], name='fk_preparation_dispatches_work_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['destination_id', 'tenant_id', 'organization_id', 'location_id', 'preparation_area_id'], ['preparation_delivery_destinations.id', 'preparation_delivery_destinations.tenant_id', 'preparation_delivery_destinations.organization_id', 'preparation_delivery_destinations.location_id', 'preparation_delivery_destinations.preparation_area_id'], name='fk_preparation_dispatches_destination_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['initiating_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_preparation_dispatches_membership', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reprint_of_dispatch_id', 'tenant_id', 'preparation_work_id', 'destination_id'], ['preparation_dispatches.id', 'preparation_dispatches.tenant_id', 'preparation_dispatches.preparation_work_id', 'preparation_dispatches.destination_id'], name='fk_preparation_dispatches_reprint_origin', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_preparation_dispatches_eligibility', 'preparation_dispatches', ['tenant_id', 'location_id', 'state', 'available_at', 'id'])
    op.create_index('ix_preparation_dispatches_work', 'preparation_dispatches', ['tenant_id', 'preparation_work_id', 'generation', 'id'])
    op.create_index('ix_preparation_dispatches_destination', 'preparation_dispatches', ['tenant_id', 'destination_id', 'state', 'id'])

    op.create_table(
        'preparation_dispatch_attempts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('dispatch_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_id', sa.BigInteger(), nullable=False),
        sa.Column('attempt_sequence', sa.Integer(), nullable=False),
        sa.Column('attempt_type', sa.String(16), nullable=False),
        sa.Column('claim_token', sa.String(36, collation='ascii_bin'), nullable=False),
        sa.Column('actor_type', sa.String(32), nullable=False),
        sa.Column('actor_membership_id', sa.BigInteger(), nullable=True),
        sa.Column('actor_principal_reference', sa.String(128), nullable=True),
        sa.Column('correlation_id', sa.String(128), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('result', sa.String(40), server_default=sa.text("'IN_PROGRESS'"), nullable=False),
        sa.Column('result_fingerprint', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('local_job_reference', sa.String(200, collation='utf8mb4_bin'), nullable=True),
        sa.Column('error_kind', sa.String(64, collation='ascii_bin'), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dispatch_id', 'attempt_sequence', name='uq_preparation_dispatch_attempts_sequence'),
        sa.UniqueConstraint('claim_token', name='uq_preparation_dispatch_attempts_claim'),
        sa.CheckConstraint("attempt_type IN ('DELIVER','RETRY','RECOVERY')", name='ck_preparation_dispatch_attempts_type'),
        sa.CheckConstraint("result IN ('IN_PROGRESS','DESTINATION_SUBMISSION_ACCEPTED','RETRYABLE_FAILURE','UNCERTAIN','ACTION_REQUIRED')", name='ck_preparation_dispatch_attempts_result'),
        sa.CheckConstraint("(result = 'IN_PROGRESS' AND ended_at IS NULL AND result_fingerprint IS NULL) OR (result <> 'IN_PROGRESS' AND ended_at IS NOT NULL AND result_fingerprint IS NOT NULL)", name='ck_preparation_dispatch_attempts_lifecycle'),
        sa.CheckConstraint("(actor_type = 'EMPLOYEE' AND actor_membership_id IS NOT NULL AND actor_principal_reference IS NULL) OR (actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND actor_membership_id IS NULL AND actor_principal_reference IS NOT NULL)", name='ck_preparation_dispatch_attempts_actor'),
        sa.ForeignKeyConstraint(['dispatch_id', 'tenant_id'], ['preparation_dispatches.id', 'preparation_dispatches.tenant_id'], name='fk_preparation_dispatch_attempts_dispatch_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['connector_id', 'tenant_id', 'organization_id', 'location_id'], ['preparation_delivery_connectors.id', 'preparation_delivery_connectors.tenant_id', 'preparation_delivery_connectors.organization_id', 'preparation_delivery_connectors.location_id'], name='fk_preparation_dispatch_attempts_connector_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['actor_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_preparation_dispatch_attempts_membership', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_preparation_dispatch_attempts_ordered', 'preparation_dispatch_attempts', ['tenant_id', 'dispatch_id', 'attempt_sequence', 'id'])
    _seed_permission()


def downgrade() -> None:
    op.drop_table('preparation_dispatch_attempts')
    op.drop_table('preparation_dispatches')
    op.drop_table('preparation_delivery_destinations')
    op.drop_table('preparation_delivery_connectors')
    op.drop_constraint('uq_preparation_works_dispatch_scope', 'preparation_works', type_='unique')
    # Preserve global permission rows and grants; their later provenance is unknowable.
