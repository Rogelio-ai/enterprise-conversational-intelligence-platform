from __future__ import annotations

from sqlalchemy import (
    BigInteger,
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


class Resource(TimestampMixin, Base):
    __tablename__ = 'resources'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_resources_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id'],
            ['locations.id', 'locations.tenant_id'],
            name='fk_resources_location_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', name='uq_resources_id_tenant'),
        UniqueConstraint(
            'id',
            'tenant_id',
            'location_id',
            name='uq_resources_id_tenant_location',
        ),
        UniqueConstraint('location_id', 'code', name='uq_resources_location_code'),
        CheckConstraint(
            "resource_type IN ('AREA', 'TABLE', 'WORKSTATION', 'EQUIPMENT', 'VEHICLE', 'DEVICE', 'CASH_REGISTER')",
            name='ck_resources_type',
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name='ck_resources_status',
        ),
        Index(
            'ix_resources_tenant_location_type_status',
            'tenant_id',
            'location_id',
            'resource_type',
            'status',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
