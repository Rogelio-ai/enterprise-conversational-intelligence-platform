from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class Organization(TimestampMixin, Base):
    __tablename__ = 'organizations'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_organizations_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('tenant_id', 'code', name='uq_organizations_tenant_code'),
        UniqueConstraint('id', 'tenant_id', name='uq_organizations_id_tenant'),
        ForeignKeyConstraint(
            ['headquarters_location_id', 'tenant_id', 'id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_organizations_headquarters_scope',
            ondelete='RESTRICT',
            use_alter=True,
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name='ck_organizations_status',
        ),
        Index('ix_organizations_tenant_status', 'tenant_id', 'status', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    headquarters_location_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )


class Location(TimestampMixin, Base):
    __tablename__ = 'locations'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_locations_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_locations_organization_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('organization_id', 'code', name='uq_locations_organization_code'),
        UniqueConstraint('id', 'tenant_id', name='uq_locations_id_tenant'),
        UniqueConstraint(
            'id',
            'tenant_id',
            'organization_id',
            name='uq_locations_id_tenant_organization',
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name='ck_locations_status',
        ),
        Index(
            'ix_locations_tenant_organization_status',
            'tenant_id',
            'organization_id',
            'status',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    locality: Mapped[str | None] = mapped_column(String(100), nullable=True)
    administrative_area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country_code: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    cash_management_activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(), nullable=True
    )


class OrganizationHeadquartersChange(Base):
    __tablename__ = 'organization_headquarters_changes'
    __table_args__ = (
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_headquarters_changes_organization_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['previous_location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_headquarters_changes_previous_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['new_location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_headquarters_changes_new_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_headquarters_changes_actor_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint('tenant_id', 'operation_id', name='uq_headquarters_changes_operation'),
        Index(
            'ix_headquarters_changes_organization_time',
            'tenant_id', 'organization_id', 'changed_at', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    previous_location_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    new_location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation_id: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=text('CURRENT_TIMESTAMP'),
    )


class MinimalProvisioningRun(Base):
    __tablename__ = 'minimal_provisioning_runs'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_minimal_provisioning_runs_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['actor_membership_id', 'tenant_id'],
            ['tenant_memberships.id', 'tenant_memberships.tenant_id'],
            name='fk_minimal_provisioning_runs_actor_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_minimal_provisioning_runs_organization_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_minimal_provisioning_runs_location_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['staff_user_id'], ['users.id'],
            name='fk_minimal_provisioning_runs_staff_user', ondelete='RESTRICT',
        ),
        UniqueConstraint('tenant_id', 'operation_id', name='uq_minimal_provisioning_runs_operation'),
        Index('ix_minimal_provisioning_runs_organization', 'tenant_id', 'organization_id', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation_id: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False,
    )
    manifest_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(
        CHAR(64, collation='ascii_bin'), nullable=False,
    )
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    staff_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=text('CURRENT_TIMESTAMP'),
    )
