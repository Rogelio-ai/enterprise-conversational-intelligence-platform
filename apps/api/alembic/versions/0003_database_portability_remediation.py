"""enforce portable database storage and referential integrity

Revision ID: 0003_database_portability_remediation
Revises: 0002_auth_tenant_foundation
Create Date: 2026-08-17
"""
from collections.abc import Sequence
from dataclasses import dataclass

import sqlalchemy as sa
from alembic import op


revision: str = '0003_database_portability_remediation'
down_revision: str | None = '0002_auth_tenant_foundation'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


APPLICATION_TABLES = (
    'tenants',
    'users',
    'permissions',
    'tenant_memberships',
    'roles',
    'role_permissions',
    'membership_roles',
)


@dataclass(frozen=True)
class ForeignKeyDefinition:
    name: str
    source_table: str
    local_columns: tuple[str, ...]
    target_table: str
    remote_columns: tuple[str, ...]


FOREIGN_KEYS = (
    ForeignKeyDefinition(
        'fk_tenant_memberships_tenant',
        'tenant_memberships',
        ('tenant_id',),
        'tenants',
        ('id',),
    ),
    ForeignKeyDefinition(
        'fk_tenant_memberships_user',
        'tenant_memberships',
        ('user_id',),
        'users',
        ('id',),
    ),
    ForeignKeyDefinition('fk_roles_tenant', 'roles', ('tenant_id',), 'tenants', ('id',)),
    ForeignKeyDefinition(
        'fk_role_permissions_role',
        'role_permissions',
        ('role_id',),
        'roles',
        ('id',),
    ),
    ForeignKeyDefinition(
        'fk_role_permissions_permission',
        'role_permissions',
        ('permission_id',),
        'permissions',
        ('id',),
    ),
    ForeignKeyDefinition(
        'fk_membership_roles_membership_tenant',
        'membership_roles',
        ('membership_id', 'tenant_id'),
        'tenant_memberships',
        ('id', 'tenant_id'),
    ),
    ForeignKeyDefinition(
        'fk_membership_roles_role_tenant',
        'membership_roles',
        ('role_id', 'tenant_id'),
        'roles',
        ('id', 'tenant_id'),
    ),
)


def _expected_signature(foreign_key: ForeignKeyDefinition) -> tuple:
    return (
        foreign_key.source_table,
        foreign_key.local_columns,
        foreign_key.target_table,
        foreign_key.remote_columns,
    )


def _drop_existing_expected_foreign_keys() -> None:
    inspector = sa.inspect(op.get_bind())
    expected_signatures = {_expected_signature(foreign_key) for foreign_key in FOREIGN_KEYS}

    for table_name in APPLICATION_TABLES:
        for foreign_key in inspector.get_foreign_keys(table_name):
            signature = (
                table_name,
                tuple(foreign_key['constrained_columns']),
                foreign_key['referred_table'],
                tuple(foreign_key['referred_columns']),
            )
            if signature in expected_signatures:
                op.drop_constraint(foreign_key['name'], table_name, type_='foreignkey')


def upgrade() -> None:
    # Alembic defaults version_num to VARCHAR(32), while this descriptive revision
    # identifier is longer. Widen it before Alembic records the completed step.
    op.alter_column(
        'alembic_version',
        'version_num',
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.execute(
        sa.text(
            'ALTER TABLE `alembic_version` ENGINE=InnoDB, '
            'CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
        )
    )

    # MyISAM silently ignores FK declarations. Remove any FKs retained by InnoDB
    # installations so table conversions behave identically in both cases.
    _drop_existing_expected_foreign_keys()

    for table_name in APPLICATION_TABLES:
        op.execute(
            sa.text(
                f'ALTER TABLE `{table_name}` ENGINE=InnoDB, '
                'CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
            )
        )

    for foreign_key in FOREIGN_KEYS:
        op.create_foreign_key(
            foreign_key.name,
            foreign_key.source_table,
            foreign_key.target_table,
            list(foreign_key.local_columns),
            list(foreign_key.remote_columns),
            ondelete='CASCADE',
        )


def downgrade() -> None:
    """Keep the safe table contract; reverting to MyISAM/latin1 would lose integrity."""
