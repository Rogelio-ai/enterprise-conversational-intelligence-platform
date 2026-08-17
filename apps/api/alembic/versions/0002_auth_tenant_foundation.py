"""establish authentication and tenant authorization foundation

Revision ID: 0002_auth_tenant_foundation
Revises: 0001_runtime_baseline
Create Date: 2026-08-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0002_auth_tenant_foundation'
down_revision: str | None = '0001_runtime_baseline'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        'tenants',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')", name='ck_tenants_status'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_tenants_slug'),
    )
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name='ck_users_status'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )
    op.create_table(
        'permissions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_permissions_code'),
    )
    op.create_table(
        'tenant_memberships',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')", name='ck_tenant_memberships_status'
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_tenant_memberships_id_tenant'),
        sa.UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_memberships_tenant_user'),
    )
    op.create_table(
        'roles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_roles_status'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id', 'tenant_id', name='uq_roles_id_tenant'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_roles_tenant_name'),
    )
    op.create_table(
        'role_permissions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('role_id', sa.BigInteger(), nullable=False),
        sa.Column('permission_id', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permissions_role_permission'),
    )
    op.create_table(
        'membership_roles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.BigInteger(), nullable=False),
        sa.Column('membership_id', sa.BigInteger(), nullable=False),
        sa.Column('role_id', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ['membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_membership_roles_membership_tenant',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['role_id', 'tenant_id'],
            ['roles.id', 'roles.tenant_id'],
            name='fk_membership_roles_role_tenant',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('membership_id', 'role_id', name='uq_membership_roles_membership_role'),
    )


def downgrade() -> None:
    op.drop_table('membership_roles')
    op.drop_table('role_permissions')
    op.drop_table('roles')
    op.drop_table('tenant_memberships')
    op.drop_table('permissions')
    op.drop_table('users')
    op.drop_table('tenants')
