from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class Customer(TimestampMixin, Base):
    __tablename__ = 'customers'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_customers_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', name='uq_customers_id_tenant'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_customers_status'),
        CheckConstraint("source IN ('PLATFORM', 'POS')", name='ck_customers_source'),
        Index('ix_customers_tenant_status', 'tenant_id', 'status', 'id'),
        Index('ix_customers_tenant_email', 'tenant_id', 'email', 'id'),
        Index('ix_customers_tenant_phone', 'tenant_id', 'phone', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)


class CustomerExternalIdentity(Base):
    __tablename__ = 'customer_external_identities'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_customer_external_identities_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['customer_id', 'tenant_id'],
            ['customers.id', 'customers.tenant_id'],
            name='fk_customer_external_identities_customer_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'tenant_id',
            'connector_key',
            'external_customer_id',
            name='uq_customer_external_identity_source',
        ),
        Index(
            'ix_customer_external_identities_customer',
            'tenant_id',
            'customer_id',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    customer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    connector_key: Mapped[str] = mapped_column(String(128), nullable=False)
    external_customer_id: Mapped[str] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
