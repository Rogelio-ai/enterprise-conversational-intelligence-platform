from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class Tenant(TimestampMixin, Base):
    __tablename__ = 'tenants'
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')", name='ck_tenants_status'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE')


class User(TimestampMixin, Base):
    __tablename__ = 'users'
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'DISABLED')", name='ck_users_status'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE')


class TenantMembership(TimestampMixin, Base):
    __tablename__ = 'tenant_memberships'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_memberships_tenant_user'),
        UniqueConstraint('id', 'tenant_id', name='uq_tenant_memberships_id_tenant'),
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE')",
            name='ck_tenant_memberships_status',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE')


class Role(TimestampMixin, Base):
    __tablename__ = 'roles'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_roles_tenant_name'),
        UniqueConstraint('id', 'tenant_id', name='uq_roles_id_tenant'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_roles_status'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE')


class Permission(TimestampMixin, Base):
    __tablename__ = 'permissions'

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)


class RolePermission(Base):
    __tablename__ = 'role_permissions'
    __table_args__ = (
        UniqueConstraint('role_id', 'permission_id', name='uq_role_permissions_role_permission'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('roles.id', ondelete='CASCADE'), nullable=False
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False
    )


class MembershipRole(Base):
    __tablename__ = 'membership_roles'
    __table_args__ = (
        ForeignKeyConstraint(
            ['membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_membership_roles_membership_tenant',
            ondelete='CASCADE',
        ),
        ForeignKeyConstraint(
            ['role_id', 'tenant_id'],
            ['roles.id', 'roles.tenant_id'],
            name='fk_membership_roles_role_tenant',
            ondelete='CASCADE',
        ),
        UniqueConstraint('membership_id', 'role_id', name='uq_membership_roles_membership_role'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
