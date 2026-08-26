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


class ProductAlias(TimestampMixin, Base):
    __tablename__ = 'product_aliases'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_aliases_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_aliases_organization_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_product_aliases_product_tenant_org',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'tenant_id',
            'organization_id',
            'product_id',
            'normalized_alias',
            'language',
            name='uq_product_aliases_product_identity',
        ),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_product_aliases_status'),
        CheckConstraint("CHAR_LENGTH(alias) > 0", name='ck_product_aliases_alias_nonempty'),
        CheckConstraint(
            "CHAR_LENGTH(normalized_alias) > 0",
            name='ck_product_aliases_normalized_nonempty',
        ),
        CheckConstraint(
            "CHAR_LENGTH(language) <= 63", name='ck_product_aliases_language_length'
        ),
        Index(
            'ix_product_aliases_tenant_org_lookup',
            'tenant_id',
            'organization_id',
            'normalized_alias',
            'language',
            'status',
            'product_id',
            'id',
        ),
        Index(
            'ix_product_aliases_tenant_org_product',
            'tenant_id',
            'organization_id',
            'product_id',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(
        String(400, collation='utf8mb4_bin'), nullable=False
    )
    language: Mapped[str] = mapped_column(
        String(63, collation='utf8mb4_bin'), nullable=False, default='', server_default=''
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
