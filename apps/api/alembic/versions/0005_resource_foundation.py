"""establish tenant-safe resource foundation

Revision ID: 0005_resource_foundation
Revises: 0004_organization_location_foundation
Create Date: 2026-08-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0005_resource_foundation'
down_revision: str | None = '0004_organization_location_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


WS_03_PERMISSIONS = {
    'resource.read': 'Read Tenant resources.',
    'resource.manage': 'Manage Tenant resources.',
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
    )
    role_permissions = sa.table(
        'role_permissions',
        sa.column('id', sa.BigInteger()),
        sa.column('role_id', sa.BigInteger()),
        sa.column('permission_id', sa.BigInteger()),
    )

    admin_role_ids = tuple(
        connection.execute(sa.select(roles.c.id).where(roles.c.name == 'TENANT_ADMIN')).scalars()
    )
    for code, description in WS_03_PERMISSIONS.items():
        permission_id = connection.execute(
            sa.select(permissions.c.id).where(permissions.c.code == code)
        ).scalar_one_or_none()
        if permission_id is None:
            connection.execute(permissions.insert().values(code=code, description=description))
            permission_id = connection.execute(
                sa.select(permissions.c.id).where(permissions.c.code == code)
            ).scalar_one()

        for role_id in admin_role_ids:
            assignment_exists = connection.execute(
                sa.select(role_permissions.c.id).where(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id,
                )
            ).scalar_one_or_none()
            if assignment_exists is None:
                connection.execute(
                    role_permissions.insert().values(
                        role_id=role_id,
                        permission_id=permission_id,
                    )
                )


def upgrade() -> None:
    op.create_table(
        'resources',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('location_id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('resource_type', sa.String(length=32), nullable=False),
        sa.Column(
            'status',
            sa.String(length=16),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.CheckConstraint(
            "resource_type IN ('AREA', 'TABLE', 'WORKSTATION', 'EQUIPMENT', 'VEHICLE', 'DEVICE')",
            name='ck_resources_type',
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_resources_status'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_resources_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['location_id', 'tenant_id'],
            ['locations.id', 'locations.tenant_id'],
            name='fk_resources_location_tenant',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_resources_id_tenant'),
        sa.UniqueConstraint('location_id', 'code', name='uq_resources_location_code'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index(
        'ix_resources_tenant_location_type_status',
        'resources',
        ['tenant_id', 'location_id', 'resource_type', 'status', 'id'],
        unique=False,
    )
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('resources')
    # Permission provenance cannot be reconstructed safely after application use.
    # Preserve catalog entries and grants that administrators may have changed.
