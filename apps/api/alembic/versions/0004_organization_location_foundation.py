"""establish tenant-safe organization and location foundation

Revision ID: 0004_organization_location_foundation
Revises: 0003_database_portability_remediation
Create Date: 2026-08-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0004_organization_location_foundation'
down_revision: str | None = '0003_database_portability_remediation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


WS_02_PERMISSIONS = {
    'organization.read': 'Read Tenant organizations.',
    'organization.manage': 'Manage Tenant organizations.',
    'location.read': 'Read Tenant locations.',
    'location.manage': 'Manage Tenant locations.',
}


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
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
    )


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
    for code, description in WS_02_PERMISSIONS.items():
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
    table_options = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
        'mysql_collate': 'utf8mb4_unicode_ci',
    }
    op.create_table(
        'organizations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_organizations_status'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_organizations_tenant', ondelete='RESTRICT'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_organizations_id_tenant'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_organizations_tenant_code'),
        **table_options,
    )
    op.create_index(
        'ix_organizations_tenant_status',
        'organizations',
        ['tenant_id', 'status', 'id'],
        unique=False,
    )

    op.create_table(
        'locations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('organization_id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=16), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column('address_line1', sa.String(length=200), nullable=True),
        sa.Column('address_line2', sa.String(length=200), nullable=True),
        sa.Column('locality', sa.String(length=100), nullable=True),
        sa.Column('administrative_area', sa.String(length=100), nullable=True),
        sa.Column('postal_code', sa.String(length=32), nullable=True),
        sa.Column('country_code', sa.CHAR(length=2), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('email', sa.String(length=320), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_locations_status'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_locations_tenant', ondelete='RESTRICT'
        ),
        sa.ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_locations_organization_tenant',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_locations_id_tenant'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_locations_organization_code'),
        **table_options,
    )
    op.create_index(
        'ix_locations_tenant_organization_status',
        'locations',
        ['tenant_id', 'organization_id', 'status', 'id'],
        unique=False,
    )
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('locations')
    op.drop_table('organizations')
    # Permission provenance cannot be reconstructed safely after application use.
    # Preserve the harmless catalog entries and assignments rather than deleting
    # grants that an administrator may have intentionally changed after upgrade.
