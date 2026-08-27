from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


_ACTIVE_DEFAULT = text("'ACTIVE'")
_INACTIVE_DEFAULT = text("'INACTIVE'")


class ProductComposition(TimestampMixin, Base):
    __tablename__ = 'product_compositions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_compositions_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_compositions_organization_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_product_compositions_product_tenant_org',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_product_compositions_id_tenant_org'
        ),
        UniqueConstraint(
            'id',
            'tenant_id',
            'organization_id',
            'product_id',
            name='uq_product_compositions_id_tenant_org_product',
        ),
        UniqueConstraint(
            'tenant_id',
            'organization_id',
            'product_id',
            name='uq_product_compositions_tenant_org_product',
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_compositions_status'
        ),
        Index(
            'ix_product_compositions_tenant_org_product_status',
            'tenant_id',
            'organization_id',
            'product_id',
            'status',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='INACTIVE', server_default=_INACTIVE_DEFAULT
    )


class ProductComponent(TimestampMixin, Base):
    __tablename__ = 'product_components'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_components_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_components_organization_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['composition_id', 'tenant_id', 'organization_id'],
            [
                'product_compositions.id',
                'product_compositions.tenant_id',
                'product_compositions.organization_id',
            ],
            name='fk_product_components_composition_tenant_org',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['component_product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_product_components_product_tenant_org',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'tenant_id',
            'organization_id',
            'composition_id',
            'component_product_id',
            name='uq_product_components_composition_product',
        ),
        CheckConstraint('quantity > 0', name='ck_product_components_quantity'),
        CheckConstraint('display_order >= 0', name='ck_product_components_display_order'),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_components_status'
        ),
        Index(
            'ix_product_components_tenant_org_composition_status_order',
            'tenant_id',
            'organization_id',
            'composition_id',
            'status',
            'display_order',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    composition_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    component_product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=_ACTIVE_DEFAULT
    )


class ProductChoiceGroup(TimestampMixin, Base):
    __tablename__ = 'product_choice_groups'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_choice_groups_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_choice_groups_organization_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['composition_id', 'tenant_id', 'organization_id'],
            [
                'product_compositions.id',
                'product_compositions.tenant_id',
                'product_compositions.organization_id',
            ],
            name='fk_product_choice_groups_composition_tenant_org',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_product_choice_groups_id_tenant_org'
        ),
        UniqueConstraint(
            'id',
            'tenant_id',
            'organization_id',
            'composition_id',
            name='uq_product_choice_groups_id_tenant_org_composition',
        ),
        UniqueConstraint(
            'tenant_id',
            'organization_id',
            'composition_id',
            'name',
            name='uq_product_choice_groups_composition_name',
        ),
        CheckConstraint('min_selections >= 0', name='ck_product_choice_groups_min'),
        CheckConstraint('max_selections > 0', name='ck_product_choice_groups_max'),
        CheckConstraint(
            'min_selections <= max_selections', name='ck_product_choice_groups_range'
        ),
        CheckConstraint('display_order >= 0', name='ck_product_choice_groups_display_order'),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_choice_groups_status'
        ),
        Index(
            'ix_product_choice_groups_tenant_org_composition_status_order',
            'tenant_id',
            'organization_id',
            'composition_id',
            'status',
            'display_order',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    composition_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    min_selections: Mapped[int] = mapped_column(Integer, nullable=False)
    max_selections: Mapped[int] = mapped_column(Integer, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=_ACTIVE_DEFAULT
    )


class ProductChoiceOption(TimestampMixin, Base):
    __tablename__ = 'product_choice_options'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_choice_options_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_choice_options_organization_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['group_id', 'tenant_id', 'organization_id'],
            [
                'product_choice_groups.id',
                'product_choice_groups.tenant_id',
                'product_choice_groups.organization_id',
            ],
            name='fk_product_choice_options_group_tenant_org',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['option_product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_product_choice_options_product_tenant_org',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id',
            'tenant_id',
            'organization_id',
            'group_id',
            name='uq_product_choice_options_id_tenant_org_group',
        ),
        UniqueConstraint(
            'tenant_id',
            'organization_id',
            'group_id',
            'option_product_id',
            name='uq_product_choice_options_group_product',
        ),
        CheckConstraint('quantity > 0', name='ck_product_choice_options_quantity'),
        CheckConstraint('display_order >= 0', name='ck_product_choice_options_display_order'),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_choice_options_status'
        ),
        Index(
            'ix_product_choice_options_tenant_org_group_status_order',
            'tenant_id',
            'organization_id',
            'group_id',
            'status',
            'display_order',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    group_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    option_product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=_ACTIVE_DEFAULT
    )
