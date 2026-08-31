"""add Restaurant Local Connector machine delivery identity

Revision ID: 0021_restaurant_local_connector_machine_delivery
Revises: 0020_preparation_dispatch_operational_delivery
Create Date: 2026-08-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0021_restaurant_local_connector_machine_delivery'
down_revision: str | None = '0020_preparation_dispatch_operational_delivery'
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
    code = 'preparation.connector.manage'
    permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
    if permission_id is None:
        connection.execute(permissions.insert().values(code=code, description='Manage Restaurant Local Connector machine credentials.'))
        permission_id = connection.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one()
    role_ids = tuple(connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE')).scalars())
    for role_id in role_ids:
        exists = connection.execute(sa.select(grants.c.id).where(grants.c.role_id == role_id, grants.c.permission_id == permission_id)).scalar_one_or_none()
        if exists is None:
            connection.execute(grants.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    options = _options()
    op.add_column('preparation_delivery_connectors', sa.Column('last_seen_at', sa.DateTime(), nullable=True))
    op.add_column('preparation_delivery_connectors', sa.Column('connector_version', sa.String(64, collation='ascii_bin'), nullable=True))
    op.add_column('preparation_delivery_connectors', sa.Column('protocol_version', sa.String(64, collation='ascii_bin'), nullable=True))

    op.create_table(
        'preparation_delivery_connector_enrollments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_id', sa.BigInteger(), nullable=False),
        sa.Column('enrollment_id', sa.String(36, collation='ascii_bin'), nullable=False),
        sa.Column('secret_digest', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_membership_id', sa.BigInteger(), nullable=False),
        sa.Column('active_slot', sa.SmallInteger(), server_default=sa.text('1'), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('enrollment_id', name='uq_connector_enrollments_public_id'),
        sa.UniqueConstraint('connector_id', 'active_slot', name='uq_connector_enrollments_active_slot'),
        sa.CheckConstraint('active_slot IS NULL OR active_slot = 1', name='ck_connector_enrollments_active_slot'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_connector_enrollments_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['connector_id', 'tenant_id', 'organization_id', 'location_id'], ['preparation_delivery_connectors.id', 'preparation_delivery_connectors.tenant_id', 'preparation_delivery_connectors.organization_id', 'preparation_delivery_connectors.location_id'], name='fk_connector_enrollments_connector_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by_membership_id', 'tenant_id'], ['tenant_memberships.id', 'tenant_memberships.tenant_id'], name='fk_connector_enrollments_membership', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_connector_enrollments_lookup', 'preparation_delivery_connector_enrollments', ['enrollment_id', 'connector_id', 'expires_at'])

    op.create_table(
        'preparation_delivery_connector_credentials',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_id', sa.BigInteger(), nullable=False),
        sa.Column('client_id', sa.String(36, collation='ascii_bin'), nullable=False),
        sa.Column('secret_digest', sa.String(64, collation='ascii_bin'), nullable=False),
        sa.Column('status', sa.String(16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('last_authenticated_at', sa.DateTime(), nullable=True),
        sa.Column('replaces_credential_id', sa.BigInteger(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id', name='uq_connector_credentials_client_id'),
        sa.UniqueConstraint('id', 'connector_id', name='uq_connector_credentials_connector'),
        sa.CheckConstraint("status IN ('ACTIVE','REVOKED')", name='ck_connector_credentials_status'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_connector_credentials_tenant', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['connector_id', 'tenant_id', 'organization_id', 'location_id'], ['preparation_delivery_connectors.id', 'preparation_delivery_connectors.tenant_id', 'preparation_delivery_connectors.organization_id', 'preparation_delivery_connectors.location_id'], name='fk_connector_credentials_connector_scope', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['replaces_credential_id', 'connector_id'], ['preparation_delivery_connector_credentials.id', 'preparation_delivery_connector_credentials.connector_id'], name='fk_connector_credentials_replacement', ondelete='RESTRICT'),
        **options,
    )
    op.create_index('ix_connector_credentials_auth', 'preparation_delivery_connector_credentials', ['client_id', 'status', 'expires_at'])
    op.create_index('ix_connector_credentials_connector', 'preparation_delivery_connector_credentials', ['tenant_id', 'connector_id', 'status', 'id'])

    op.add_column('preparation_dispatch_attempts', sa.Column('claim_request_id', sa.String(128, collation='ascii_bin'), nullable=True))
    op.create_unique_constraint('uq_dispatch_attempts_claim_request', 'preparation_dispatch_attempts', ['tenant_id', 'connector_id', 'claim_request_id'])
    op.create_index('ix_preparation_dispatches_connector_eligibility', 'preparation_dispatches', ['tenant_id', 'connector_id_snapshot', 'state', 'available_at', 'id'])
    _seed_permission()


def downgrade() -> None:
    op.drop_index('ix_preparation_dispatches_connector_eligibility', table_name='preparation_dispatches')
    op.drop_constraint('uq_dispatch_attempts_claim_request', 'preparation_dispatch_attempts', type_='unique')
    op.drop_column('preparation_dispatch_attempts', 'claim_request_id')
    op.drop_table('preparation_delivery_connector_credentials')
    op.drop_table('preparation_delivery_connector_enrollments')
    op.drop_column('preparation_delivery_connectors', 'protocol_version')
    op.drop_column('preparation_delivery_connectors', 'connector_version')
    op.drop_column('preparation_delivery_connectors', 'last_seen_at')
    # Preserve global permission rows/grants because later provenance is unknowable.
