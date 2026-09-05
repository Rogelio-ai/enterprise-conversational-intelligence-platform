"""establish cash register and CashSession foundation

Revision ID: 0032_cash_management_foundation
Revises: 0031_fiscal_result_artifact_persistence
Create Date: 2026-09-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0032_cash_management_foundation'
down_revision: str | None = '0031_fiscal_result_artifact_persistence'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    'cash_management.read': 'Read cash-management sessions.',
    'cash_session.manage': 'Open and manage cash sessions.',
}


def _seed_permissions() -> None:
    connection = op.get_bind()
    permissions = sa.table(
        'permissions',
        sa.column('id', sa.BigInteger()),
        sa.column('code', sa.String()),
        sa.column('description', sa.String()),
    )
    roles = sa.table(
        'roles',
        sa.column('id', sa.BigInteger()),
        sa.column('name', sa.String()),
        sa.column('status', sa.String()),
    )
    grants = sa.table(
        'role_permissions',
        sa.column('id', sa.BigInteger()),
        sa.column('role_id', sa.BigInteger()),
        sa.column('permission_id', sa.BigInteger()),
    )
    admin_role_ids = tuple(connection.execute(
        sa.select(roles.c.id).where(
            roles.c.name == 'TENANT_ADMIN', roles.c.status == 'ACTIVE'
        )
    ).scalars())
    for code, description in PERMISSIONS.items():
        permission_id = connection.execute(
            sa.select(permissions.c.id).where(permissions.c.code == code)
        ).scalar_one_or_none()
        if permission_id is None:
            connection.execute(
                permissions.insert().values(code=code, description=description)
            )
            permission_id = connection.execute(
                sa.select(permissions.c.id).where(permissions.c.code == code)
            ).scalar_one()
        for role_id in admin_role_ids:
            exists = connection.execute(sa.select(grants.c.id).where(
                grants.c.role_id == role_id,
                grants.c.permission_id == permission_id,
            )).scalar_one_or_none()
            if exists is None:
                connection.execute(grants.insert().values(
                    role_id=role_id, permission_id=permission_id
                ))


def upgrade() -> None:
    op.drop_constraint('ck_resources_type', 'resources', type_='check')
    op.create_check_constraint(
        'ck_resources_type',
        'resources',
        "resource_type IN ('AREA', 'TABLE', 'WORKSTATION', 'EQUIPMENT', "
        "'VEHICLE', 'DEVICE', 'CASH_REGISTER')",
    )
    op.add_column(
        'locations',
        sa.Column('cash_management_activated_at', sa.DateTime(), nullable=True),
    )
    op.create_table(
        'cash_sessions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.BigInteger(), nullable=False),
        sa.Column('cashier_membership_id', sa.BigInteger(), nullable=False),
        sa.Column(
            'currency', sa.String(3, collation='ascii_bin'), nullable=False
        ),
        sa.Column(
            'status', sa.String(16), server_default=sa.text("'OPEN'"),
            nullable=False,
        ),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('opened_by_actor_type', sa.String(24), nullable=False),
        sa.Column('opened_by_actor_id', sa.BigInteger(), nullable=True),
        sa.Column(
            'opened_by_actor_reference',
            sa.String(200, collation='utf8mb4_bin'), nullable=True,
        ),
        sa.Column(
            'movement_version', sa.BigInteger(), server_default=sa.text('0'),
            nullable=False,
        ),
        sa.Column(
            'open_slot', sa.SmallInteger(), server_default=sa.text('1'),
            nullable=True,
        ),
        sa.Column(
            'open_actor_scope', sa.String(200, collation='ascii_bin'),
            nullable=False,
        ),
        sa.Column(
            'open_idempotency_key', sa.String(128, collation='ascii_bin'),
            nullable=False,
        ),
        sa.Column(
            'open_request_schema_version', sa.Integer(),
            server_default=sa.text('1'), nullable=False,
        ),
        sa.Column(
            'open_request_fingerprint', sa.String(64, collation='ascii_bin'),
            nullable=False,
        ),
        sa.Column(
            'created_at', sa.DateTime(),
            server_default=sa.func.current_timestamp(), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(),
            server_default=sa.func.current_timestamp(), nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'resource_id',
            name='uq_cash_sessions_scope',
        ),
        sa.UniqueConstraint(
            'resource_id', 'open_slot', name='uq_cash_sessions_resource_open',
        ),
        sa.UniqueConstraint(
            'tenant_id', 'open_actor_scope', 'open_idempotency_key',
            name='uq_cash_sessions_open_idempotency',
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','CLOSED')", name='ck_cash_sessions_status'
        ),
        sa.CheckConstraint(
            'open_slot IS NULL OR open_slot = 1',
            name='ck_cash_sessions_open_slot',
        ),
        sa.CheckConstraint(
            "(status='OPEN' AND open_slot=1) OR "
            "(status='CLOSED' AND open_slot IS NULL)",
            name='ck_cash_sessions_lifecycle',
        ),
        sa.CheckConstraint(
            'movement_version >= 0 AND open_request_schema_version >= 1',
            name='ck_cash_sessions_versions',
        ),
        sa.CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_cash_sessions_currency',
        ),
        sa.CheckConstraint(
            "(opened_by_actor_type='EMPLOYEE' AND opened_by_actor_id IS NOT NULL "
            "AND opened_by_actor_reference IS NULL) OR "
            "(opened_by_actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') "
            "AND opened_by_actor_id IS NULL AND opened_by_actor_reference IS NOT NULL)",
            name='ck_cash_sessions_open_actor',
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_cash_sessions_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_cash_sessions_location_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['resource_id', 'tenant_id', 'location_id'],
            ['resources.id', 'resources.tenant_id', 'resources.location_id'],
            name='fk_cash_sessions_resource_scope', ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['cashier_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_cash_sessions_cashier_membership', ondelete='RESTRICT',
        ),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index(
        'ix_cash_sessions_resource_history', 'cash_sessions',
        ['resource_id', 'id'], unique=False,
    )
    op.create_index(
        'ix_cash_sessions_location_status', 'cash_sessions',
        ['tenant_id', 'location_id', 'status', 'id'], unique=False,
    )
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('cash_sessions')
    op.drop_column('locations', 'cash_management_activated_at')
    op.drop_constraint('ck_resources_type', 'resources', type_='check')
    op.create_check_constraint(
        'ck_resources_type',
        'resources',
        "resource_type IN ('AREA', 'TABLE', 'WORKSTATION', 'EQUIPMENT', "
        "'VEHICLE', 'DEVICE')",
    )
    # Preserve permission rows and grants because later provenance is unknowable.
