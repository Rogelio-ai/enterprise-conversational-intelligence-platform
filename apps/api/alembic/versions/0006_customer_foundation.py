"""establish tenant-safe canonical Customer foundation

Revision ID: 0006_customer_foundation
Revises: 0005_resource_foundation
Create Date: 2026-08-19
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0006_customer_foundation'
down_revision: str | None = '0005_resource_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


WS_07_PERMISSIONS = {
    'customer.read': 'Read Tenant customers.',
    'customer.manage': 'Manage Tenant customers.',
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
    for code, description in WS_07_PERMISSIONS.items():
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
        'customers',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=True),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column(
            'status',
            sa.String(length=16),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column('source', sa.String(length=16), nullable=False),
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
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_customers_status'),
        sa.CheckConstraint("source IN ('PLATFORM', 'POS')", name='ck_customers_source'),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_customers_tenant', ondelete='RESTRICT'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_customers_id_tenant'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index(
        'ix_customers_tenant_status',
        'customers',
        ['tenant_id', 'status', 'id'],
        unique=False,
    )
    op.create_index(
        'ix_customers_tenant_email',
        'customers',
        ['tenant_id', 'email', 'id'],
        unique=False,
    )
    op.create_index(
        'ix_customers_tenant_phone',
        'customers',
        ['tenant_id', 'phone', 'id'],
        unique=False,
    )

    op.create_table(
        'customer_external_identities',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('customer_id', sa.BigInteger(), nullable=False),
        sa.Column('connector_key', sa.String(length=128), nullable=False),
        sa.Column(
            'external_customer_id',
            sa.String(length=200, collation='utf8mb4_bin'),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_customer_external_identities_tenant',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['customer_id', 'tenant_id'],
            ['customers.id', 'customers.tenant_id'],
            name='fk_customer_external_identities_customer_tenant',
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id',
            'connector_key',
            'external_customer_id',
            name='uq_customer_external_identity_source',
        ),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index(
        'ix_customer_external_identities_customer',
        'customer_external_identities',
        ['tenant_id', 'customer_id', 'id'],
        unique=False,
    )
    _seed_permissions()


def downgrade() -> None:
    op.drop_table('customer_external_identities')
    op.drop_table('customers')
    # Permission provenance cannot be reconstructed safely after application use.
    # Preserve catalog entries and grants that administrators may have changed.
