from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
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
