from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


_ACTIVE_DEFAULT = text("'ACTIVE'")


class ProductCategory(TimestampMixin, Base):
    __tablename__ = 'product_categories'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_product_categories_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_categories_organization_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['parent_id', 'tenant_id', 'organization_id'],
            [
                'product_categories.id',
                'product_categories.tenant_id',
                'product_categories.organization_id',
            ],
            name='fk_product_categories_parent_tenant_org',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', name='uq_product_categories_id_tenant'),
        UniqueConstraint(
            'id',
            'tenant_id',
            'organization_id',
            name='uq_product_categories_id_tenant_org',
        ),
        UniqueConstraint(
            'tenant_id',
            'organization_id',
            'name',
            name='uq_product_categories_tenant_org_name',
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_product_categories_status'
        ),
        CheckConstraint(
            'display_order >= 0', name='ck_product_categories_display_order'
        ),
        Index(
            'ix_product_categories_tenant_org_status_name',
            'tenant_id',
            'organization_id',
            'status',
            'name',
            'id',
        ),
        Index(
            'ix_product_categories_tenant_org_parent_status_order',
            'tenant_id',
            'organization_id',
            'parent_id',
            'status',
            'display_order',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default='0'
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=_ACTIVE_DEFAULT
    )


class Product(TimestampMixin, Base):
    __tablename__ = 'products'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_products_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_products_organization_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['category_id', 'tenant_id', 'organization_id'],
            [
                'product_categories.id',
                'product_categories.tenant_id',
                'product_categories.organization_id',
            ],
            name='fk_products_category_tenant_org',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', name='uq_products_id_tenant'),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_products_id_tenant_org'
        ),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_products_status'),
        CheckConstraint("source IN ('PLATFORM', 'POS')", name='ck_products_source'),
        Index(
            'ix_products_tenant_org_status_name',
            'tenant_id',
            'organization_id',
            'status',
            'name',
            'id',
        ),
        Index(
            'ix_products_tenant_org_category',
            'tenant_id',
            'organization_id',
            'category_id',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    tax_classification_code: Mapped[str | None] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=_ACTIVE_DEFAULT
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)


class ProductExternalMapping(Base):
    __tablename__ = 'product_external_mappings'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'],
            ['tenants.id'],
            name='fk_product_external_mappings_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['product_id', 'tenant_id'],
            ['products.id', 'products.tenant_id'],
            name='fk_product_external_mappings_product_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'tenant_id',
            'connector_key',
            'external_product_id',
            name='uq_product_external_mapping_source',
        ),
        Index(
            'ix_product_external_mappings_product', 'tenant_id', 'product_id', 'id'
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    connector_key: Mapped[str] = mapped_column(String(128), nullable=False)
    external_product_id: Mapped[str] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class Menu(TimestampMixin, Base):
    __tablename__ = 'menus'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_menus_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_menus_organization_tenant',
            ondelete='RESTRICT',
        ),
        UniqueConstraint('id', 'tenant_id', name='uq_menus_id_tenant'),
        UniqueConstraint('id', 'tenant_id', 'organization_id', name='uq_menus_id_tenant_org'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_menus_status'),
        Index(
            'ix_menus_tenant_org_status_name',
            'tenant_id',
            'organization_id',
            'status',
            'name',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=_ACTIVE_DEFAULT
    )


class MenuLocation(TimestampMixin, Base):
    __tablename__ = 'menu_locations'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_menu_locations_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['menu_id', 'tenant_id', 'organization_id'],
            ['menus.id', 'menus.tenant_id', 'menus.organization_id'],
            name='fk_menu_locations_menu_tenant_org',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_menu_locations_location_tenant_org',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'tenant_id', 'menu_id', 'location_id', name='uq_menu_locations_tenant_menu_location'
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_menu_locations_status'
        ),
        Index(
            'ix_menu_locations_tenant_location_status',
            'tenant_id',
            'location_id',
            'status',
            'menu_id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    menu_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=_ACTIVE_DEFAULT
    )


class MenuSection(TimestampMixin, Base):
    __tablename__ = 'menu_sections'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_menu_sections_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['menu_id', 'tenant_id', 'organization_id'],
            ['menus.id', 'menus.tenant_id', 'menus.organization_id'],
            name='fk_menu_sections_menu_tenant_org',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id',
            'menu_id',
            'tenant_id',
            'organization_id',
            name='uq_menu_sections_id_menu_tenant_org',
        ),
        CheckConstraint("display_order >= 0", name='ck_menu_sections_display_order'),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')", name='ck_menu_sections_status'
        ),
        Index(
            'ix_menu_sections_menu_status_order',
            'tenant_id',
            'menu_id',
            'status',
            'display_order',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    menu_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=_ACTIVE_DEFAULT
    )


class MenuItem(TimestampMixin, Base):
    __tablename__ = 'menu_items'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_menu_items_tenant', ondelete='RESTRICT'
        ),
        ForeignKeyConstraint(
            ['menu_id', 'tenant_id', 'organization_id'],
            ['menus.id', 'menus.tenant_id', 'menus.organization_id'],
            name='fk_menu_items_menu_tenant_org',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['section_id', 'menu_id', 'tenant_id', 'organization_id'],
            [
                'menu_sections.id',
                'menu_sections.menu_id',
                'menu_sections.tenant_id',
                'menu_sections.organization_id',
            ],
            name='fk_menu_items_section_menu_tenant_org',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_menu_items_product_tenant_org',
            ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'tenant_id', 'menu_id', 'product_id', name='uq_menu_items_tenant_menu_product'
        ),
        CheckConstraint("display_order >= 0", name='ck_menu_items_display_order'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_menu_items_status'),
        Index(
            'ix_menu_items_section_status_order',
            'tenant_id',
            'menu_id',
            'section_id',
            'status',
            'display_order',
            'id',
        ),
        Index(
            'ix_menu_items_tenant_product', 'tenant_id', 'product_id', 'menu_id', 'id'
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    menu_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    section_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=_ACTIVE_DEFAULT
    )
