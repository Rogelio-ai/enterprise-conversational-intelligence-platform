from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


OPTIONS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8mb4',
    'mysql_collate': 'utf8mb4_unicode_ci',
}


class Warehouse(TimestampMixin, Base):
    __tablename__ = 'warehouses'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_warehouses_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_warehouses_organization_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_warehouses_location_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_warehouses_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'code',
            name='uq_warehouses_location_code',
        ),
        UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'default_slot',
            name='uq_warehouses_location_default',
        ),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_warehouses_status'),
        CheckConstraint(
            'default_slot IS NULL OR default_slot=1',
            name='ck_warehouses_default_slot',
        ),
        CheckConstraint(
            "negative_stock_policy IN ('ALLOW','WARN','BLOCK')",
            name='ck_warehouses_negative_stock_policy',
        ),
        CheckConstraint('version >= 1', name='ck_warehouses_version'),
        Index(
            'ix_warehouses_location_status', 'tenant_id', 'location_id',
            'status', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    code: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    default_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    negative_stock_policy: Mapped[str] = mapped_column(
        String(8), nullable=False, default='ALLOW', server_default=text("'ALLOW'")
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )


class InventoryItem(TimestampMixin, Base):
    __tablename__ = 'inventory_items'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_inventory_items_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_inventory_items_organization_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_inventory_items_location_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_inventory_items_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'code',
            name='uq_inventory_items_location_code',
        ),
        CheckConstraint(
            "base_uom IN ('KG','G','L','ML','UNIT','PORTION')",
            name='ck_inventory_items_base_uom',
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')", name='ck_inventory_items_status',
        ),
        CheckConstraint(
            'standard_unit_cost >= 0', name='ck_inventory_items_standard_cost',
        ),
        CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_inventory_items_currency',
        ),
        CheckConstraint('version >= 1', name='ck_inventory_items_version'),
        Index(
            'ix_inventory_items_location_status_name', 'tenant_id', 'location_id',
            'status', 'name', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    code: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_uom: Mapped[str] = mapped_column(String(16), nullable=False)
    standard_unit_cost: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3, collation='ascii_bin'), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )


class ItemUomConversion(Base):
    __tablename__ = 'item_uom_conversions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'inventory_items.id', 'inventory_items.tenant_id',
                'inventory_items.organization_id', 'inventory_items.location_id',
            ],
            name='fk_item_uom_conversions_item_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            'inventory_item_id', name='uq_item_uom_conversions_scope',
        ),
        UniqueConstraint(
            'inventory_item_id', 'operational_uom', 'revision',
            name='uq_item_uom_conversions_revision',
        ),
        CheckConstraint('factor_to_base > 0', name='ck_item_uom_conversions_factor'),
        CheckConstraint('revision >= 1', name='ck_item_uom_conversions_revision'),
        CheckConstraint(
            "operational_uom REGEXP '^[A-Z][A-Z0-9_]{0,31}$'",
            name='ck_item_uom_conversions_uom',
        ),
        Index(
            'ix_item_uom_conversions_resolve', 'tenant_id', 'inventory_item_id',
            'operational_uom', 'effective_at', 'revision',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operational_uom: Mapped[str] = mapped_column(
        String(32, collation='ascii_bin'), nullable=False
    )
    factor_to_base: Mapped[Decimal] = mapped_column(Numeric(25, 12), nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class InventoryCostRevision(Base):
    __tablename__ = 'inventory_cost_revisions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'inventory_items.id', 'inventory_items.tenant_id',
                'inventory_items.organization_id', 'inventory_items.location_id',
            ],
            name='fk_inventory_cost_revisions_item_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            'inventory_item_id', name='uq_inventory_cost_revisions_scope',
        ),
        UniqueConstraint(
            'inventory_item_id', 'revision',
            name='uq_inventory_cost_revisions_revision',
        ),
        CheckConstraint('standard_unit_cost >= 0', name='ck_cost_revisions_cost'),
        CheckConstraint('revision >= 1', name='ck_cost_revisions_revision'),
        CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_cost_revisions_currency',
        ),
        Index(
            'ix_inventory_cost_revisions_resolve', 'tenant_id', 'inventory_item_id',
            'effective_at', 'revision',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    standard_unit_cost: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3, collation='ascii_bin'), nullable=False
    )
    effective_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    source: Mapped[str] = mapped_column(
        String(48, collation='ascii_bin'), nullable=False
    )
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class ProductConsumptionDefinition(TimestampMixin, Base):
    __tablename__ = 'product_consumption_definitions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_consumption_definitions_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_consumption_definitions_organization_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_consumption_definitions_location_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_consumption_definitions_product_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_consumption_definitions_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'product_id',
            name='uq_consumption_definitions_product_location',
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_consumption_definitions_status',
        ),
        CheckConstraint(
            "tracking_mode IN ('DERIVABLE','NON_DERIVABLE')",
            name='ck_consumption_definitions_tracking_mode',
        ),
        CheckConstraint('version >= 1', name='ck_consumption_definitions_version'),
        Index(
            'ix_consumption_definitions_location_status', 'tenant_id', 'location_id',
            'status', 'product_id', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    tracking_mode: Mapped[str] = mapped_column(String(24), nullable=False)


class ProductConsumptionComponent(Base):
    __tablename__ = 'product_consumption_components'
    __table_args__ = (
        ForeignKeyConstraint(
            ['definition_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'product_consumption_definitions.id',
                'product_consumption_definitions.tenant_id',
                'product_consumption_definitions.organization_id',
                'product_consumption_definitions.location_id',
            ],
            name='fk_consumption_components_definition_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'inventory_items.id', 'inventory_items.tenant_id',
                'inventory_items.organization_id', 'inventory_items.location_id',
            ],
            name='fk_consumption_components_item_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'definition_id', 'inventory_item_id',
            name='uq_consumption_components_definition_item',
        ),
        CheckConstraint('quantity > 0', name='ck_consumption_components_quantity'),
        Index(
            'ix_consumption_components_definition', 'tenant_id', 'definition_id',
            'inventory_item_id', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    definition_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class ProductConsumptionVersion(Base):
    __tablename__ = 'product_consumption_versions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['definition_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'product_consumption_definitions.id',
                'product_consumption_definitions.tenant_id',
                'product_consumption_definitions.organization_id',
                'product_consumption_definitions.location_id',
            ],
            name='fk_consumption_versions_definition_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'definition_id',
            name='uq_consumption_versions_scope',
        ),
        UniqueConstraint(
            'definition_id', 'revision', name='uq_consumption_versions_revision',
        ),
        CheckConstraint('revision >= 1', name='ck_consumption_versions_revision'),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')", name='ck_consumption_versions_status',
        ),
        CheckConstraint(
            "tracking_mode IN ('DERIVABLE','NON_DERIVABLE')",
            name='ck_consumption_versions_tracking_mode',
        ),
        CheckConstraint(
            "publication_status='PUBLISHED'",
            name='ck_consumption_versions_publication',
        ),
        CheckConstraint(
            'effective_to IS NULL OR effective_to >= effective_from',
            name='ck_consumption_versions_effectivity',
        ),
        Index(
            'ix_consumption_versions_resolve', 'tenant_id', 'location_id',
            'definition_id', 'effective_from', 'effective_to', 'revision',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    definition_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    tracking_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    publication_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='PUBLISHED',
        server_default=text("'PUBLISHED'"),
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(48, collation='ascii_bin'), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class ProductConsumptionVersionComponent(Base):
    __tablename__ = 'product_consumption_version_components'
    __table_args__ = (
        ForeignKeyConstraint(
            [
                'version_id', 'tenant_id', 'organization_id', 'location_id',
                'definition_id',
            ],
            [
                'product_consumption_versions.id',
                'product_consumption_versions.tenant_id',
                'product_consumption_versions.organization_id',
                'product_consumption_versions.location_id',
                'product_consumption_versions.definition_id',
            ],
            name='fk_version_components_version_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'inventory_items.id', 'inventory_items.tenant_id',
                'inventory_items.organization_id', 'inventory_items.location_id',
            ],
            name='fk_version_components_item_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'conversion_revision_id', 'tenant_id', 'organization_id',
                'location_id', 'inventory_item_id',
            ],
            [
                'item_uom_conversions.id', 'item_uom_conversions.tenant_id',
                'item_uom_conversions.organization_id',
                'item_uom_conversions.location_id',
                'item_uom_conversions.inventory_item_id',
            ],
            name='fk_version_components_conversion_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'definition_id',
            'version_id', name='uq_version_components_scope',
        ),
        UniqueConstraint(
            'version_id', 'inventory_item_id',
            name='uq_version_components_version_item',
        ),
        CheckConstraint(
            'quantity > 0 AND source_quantity > 0 AND conversion_factor > 0',
            name='ck_version_components_quantity_evidence',
        ),
        Index(
            'ix_version_components_version', 'tenant_id', 'version_id',
            'inventory_item_id', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    definition_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    source_quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    source_uom: Mapped[str] = mapped_column(
        String(32, collation='ascii_bin'), nullable=False
    )
    conversion_revision_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(25, 12), nullable=False)
    base_uom_evidence: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class RestaurantOrderConsumption(Base):
    __tablename__ = 'restaurant_order_consumptions'
    __table_args__ = (
        ForeignKeyConstraint(
            ['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_orders.id', 'restaurant_orders.tenant_id',
                'restaurant_orders.organization_id', 'restaurant_orders.location_id',
            ],
            name='fk_order_consumptions_order_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            'restaurant_order_id', name='uq_order_consumptions_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'organization_id', 'location_id', 'restaurant_order_id',
            name='uq_order_consumptions_order',
        ),
        CheckConstraint(
            "coverage_status IN ('COMPLETE','PARTIAL')",
            name='ck_order_consumptions_coverage',
        ),
        CheckConstraint('schema_version >= 1', name='ck_order_consumptions_version'),
        Index(
            'ix_order_consumptions_order', 'tenant_id', 'restaurant_order_id', 'id'
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    coverage_status: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    unresolved_evidence: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class Supplier(TimestampMixin, Base):
    __tablename__ = 'suppliers'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name='fk_suppliers_tenant',
            ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_suppliers_organization_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', name='uq_suppliers_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'organization_id', 'code',
            name='uq_suppliers_organization_code',
        ),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_suppliers_status'),
        CheckConstraint('version >= 1', name='ck_suppliers_version'),
        Index(
            'ix_suppliers_organization_status', 'tenant_id', 'organization_id',
            'status', 'name', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    code: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    contact_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )


class SupplierLocation(Base):
    __tablename__ = 'supplier_locations'
    __table_args__ = (
        ForeignKeyConstraint(
            ['supplier_id', 'tenant_id', 'organization_id'],
            ['suppliers.id', 'suppliers.tenant_id', 'suppliers.organization_id'],
            name='fk_supplier_locations_supplier_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_supplier_locations_location_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id',
            name='uq_supplier_locations_scope',
        ),
        UniqueConstraint(
            'supplier_id', 'tenant_id', 'organization_id', 'location_id',
            name='uq_supplier_locations_supplier_location',
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')", name='ck_supplier_locations_status'
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class SupplierOffering(TimestampMixin, Base):
    __tablename__ = 'supplier_offerings'
    __table_args__ = (
        ForeignKeyConstraint(
            ['supplier_id', 'tenant_id', 'organization_id'],
            ['suppliers.id', 'suppliers.tenant_id', 'suppliers.organization_id'],
            name='fk_supplier_offerings_supplier_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['supplier_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'supplier_locations.supplier_id', 'supplier_locations.tenant_id',
                'supplier_locations.organization_id', 'supplier_locations.location_id',
            ],
            name='fk_supplier_offerings_availability_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'inventory_items.id', 'inventory_items.tenant_id',
                'inventory_items.organization_id', 'inventory_items.location_id',
            ],
            name='fk_supplier_offerings_item_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id',
            'inventory_item_id', name='uq_supplier_offerings_scope',
        ),
        UniqueConstraint(
            'supplier_id', 'location_id', 'inventory_item_id',
            name='uq_supplier_offerings_supplier_item',
        ),
        CheckConstraint(
            "purchase_uom REGEXP '^[A-Z][A-Z0-9_]{0,31}$'",
            name='ck_supplier_offerings_purchase_uom',
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')", name='ck_supplier_offerings_status'
        ),
        CheckConstraint('version >= 1', name='ck_supplier_offerings_version'),
        Index(
            'ix_supplier_offerings_location_status', 'tenant_id', 'location_id',
            'supplier_id', 'status', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_item_code: Mapped[str | None] = mapped_column(
        String(100, collation='utf8mb4_bin'), nullable=True
    )
    purchase_uom: Mapped[str] = mapped_column(
        String(32, collation='ascii_bin'), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )


class GoodsReceipt(TimestampMixin, Base):
    __tablename__ = 'goods_receipts'
    __table_args__ = (
        ForeignKeyConstraint(
            ['supplier_id', 'tenant_id', 'organization_id'],
            ['suppliers.id', 'suppliers.tenant_id', 'suppliers.organization_id'],
            name='fk_goods_receipts_supplier_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['supplier_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'supplier_locations.supplier_id', 'supplier_locations.tenant_id',
                'supplier_locations.organization_id', 'supplier_locations.location_id',
            ],
            name='fk_goods_receipts_availability_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['warehouse_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'warehouses.id', 'warehouses.tenant_id',
                'warehouses.organization_id', 'warehouses.location_id',
            ],
            name='fk_goods_receipts_warehouse_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'supplier_id',
            'warehouse_id', name='uq_goods_receipts_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'acceptance_actor_scope', 'acceptance_idempotency_key',
            name='uq_goods_receipts_acceptance_idempotency',
        ),
        UniqueConstraint(
            'supplier_id', 'location_id', 'external_reference',
            name='uq_goods_receipts_external_reference',
        ),
        CheckConstraint(
            "status IN ('DRAFT','ACCEPTED','CANCELLED')",
            name='ck_goods_receipts_status',
        ),
        CheckConstraint('version >= 1', name='ck_goods_receipts_version'),
        CheckConstraint(
            "(status='DRAFT' AND accepted_at IS NULL AND cancelled_at IS NULL) OR "
            "(status='ACCEPTED' AND accepted_at IS NOT NULL AND accepted_by_actor_id IS NOT NULL "
            "AND acceptance_actor_scope IS NOT NULL AND acceptance_idempotency_key IS NOT NULL "
            "AND acceptance_fingerprint IS NOT NULL AND cancelled_at IS NULL) OR "
            "(status='CANCELLED' AND cancelled_at IS NOT NULL AND accepted_at IS NULL)",
            name='ck_goods_receipts_lifecycle_evidence',
        ),
        Index(
            'ix_goods_receipts_location_status', 'tenant_id', 'location_id',
            'status', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    external_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='DRAFT', server_default=text("'DRAFT'")
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )
    created_by_actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    accepted_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    cancelled_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    acceptance_actor_scope: Mapped[str | None] = mapped_column(
        String(200, collation='ascii_bin'), nullable=True
    )
    acceptance_idempotency_key: Mapped[str | None] = mapped_column(
        String(128, collation='ascii_bin'), nullable=True
    )
    acceptance_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )


class GoodsReceiptLine(Base):
    __tablename__ = 'goods_receipt_lines'
    __table_args__ = (
        ForeignKeyConstraint(
            ['goods_receipt_id', 'tenant_id', 'organization_id', 'location_id',
             'supplier_id', 'warehouse_id'],
            [
                'goods_receipts.id', 'goods_receipts.tenant_id',
                'goods_receipts.organization_id', 'goods_receipts.location_id',
                'goods_receipts.supplier_id', 'goods_receipts.warehouse_id',
            ],
            name='fk_goods_receipt_lines_receipt_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['supplier_offering_id', 'tenant_id', 'organization_id', 'location_id',
             'supplier_id', 'inventory_item_id'],
            [
                'supplier_offerings.id', 'supplier_offerings.tenant_id',
                'supplier_offerings.organization_id', 'supplier_offerings.location_id',
                'supplier_offerings.supplier_id',
                'supplier_offerings.inventory_item_id',
            ],
            name='fk_goods_receipt_lines_offering_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['conversion_revision_id', 'tenant_id', 'organization_id', 'location_id',
             'inventory_item_id'],
            [
                'item_uom_conversions.id', 'item_uom_conversions.tenant_id',
                'item_uom_conversions.organization_id',
                'item_uom_conversions.location_id',
                'item_uom_conversions.inventory_item_id',
            ],
            name='fk_goods_receipt_lines_conversion_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            'goods_receipt_id', 'inventory_item_id', name='uq_goods_receipt_lines_scope',
        ),
        UniqueConstraint(
            'goods_receipt_id', 'line_number', name='uq_goods_receipt_lines_number'
        ),
        UniqueConstraint(
            'goods_receipt_id', 'supplier_offering_id',
            name='uq_goods_receipt_lines_offering',
        ),
        CheckConstraint('line_number >= 1', name='ck_goods_receipt_lines_number'),
        CheckConstraint(
            'received_quantity > 0 AND accepted_quantity >= 0 AND rejected_quantity >= 0 '
            'AND accepted_quantity + rejected_quantity = received_quantity',
            name='ck_goods_receipt_lines_quantities',
        ),
        CheckConstraint('unit_cost >= 0', name='ck_goods_receipt_lines_cost'),
        CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_goods_receipt_lines_currency',
        ),
        CheckConstraint(
            "source_uom REGEXP '^[A-Z][A-Z0-9_]{0,31}$'",
            name='ck_goods_receipt_lines_source_uom',
        ),
        CheckConstraint(
            "evidence_status IN ('PENDING','RESOLVED','REJECTED_ONLY')",
            name='ck_goods_receipt_lines_evidence_status',
        ),
        CheckConstraint(
            "(evidence_status='PENDING' AND normalized_quantity IS NULL AND "
            "conversion_factor IS NULL AND base_uom_evidence IS NULL AND extended_cost IS NULL) "
            "OR (evidence_status='RESOLVED' AND accepted_quantity > 0 AND "
            "normalized_quantity > 0 AND conversion_factor > 0 AND "
            "base_uom_evidence IS NOT NULL AND extended_cost IS NOT NULL) "
            "OR (evidence_status='REJECTED_ONLY' AND accepted_quantity=0 AND "
            "normalized_quantity=0 AND conversion_factor > 0 AND "
            "base_uom_evidence IS NOT NULL AND extended_cost=0)",
            name='ck_goods_receipt_lines_evidence',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    goods_receipt_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_offering_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    accepted_quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    rejected_quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    source_uom: Mapped[str] = mapped_column(
        String(32, collation='ascii_bin'), nullable=False
    )
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3, collation='ascii_bin'), nullable=False
    )
    conversion_revision_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversion_factor: Mapped[Decimal | None] = mapped_column(
        Numeric(25, 12), nullable=True
    )
    base_uom_evidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    normalized_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 6), nullable=True
    )
    extended_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(31, 12), nullable=True
    )
    evidence_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='PENDING', server_default=text("'PENDING'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )


class InventoryLossPolicy(TimestampMixin, Base):
    __tablename__ = 'inventory_loss_policies'
    __table_args__ = (
        ForeignKeyConstraint(
            ['warehouse_id', 'tenant_id', 'organization_id', 'location_id'],
            ['warehouses.id', 'warehouses.tenant_id', 'warehouses.organization_id',
             'warehouses.location_id'],
            name='fk_inventory_loss_policies_warehouse_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'warehouse_id', name='uq_inventory_loss_policies_warehouse',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id',
            name='uq_inventory_loss_policies_scope',
        ),
        CheckConstraint(
            'approval_value_threshold >= 0',
            name='ck_inventory_loss_policies_threshold',
        ),
        CheckConstraint(
            "currency REGEXP '^[A-Z][A-Z][A-Z]$'",
            name='ck_inventory_loss_policies_currency',
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_inventory_loss_policies_status',
        ),
        CheckConstraint('version >= 1', name='ck_inventory_loss_policies_version'),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    approval_value_threshold: Mapped[Decimal] = mapped_column(
        Numeric(31, 12), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3, collation='ascii_bin'), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )


class InventoryLoss(TimestampMixin, Base):
    __tablename__ = 'inventory_losses'
    __table_args__ = (
        ForeignKeyConstraint(
            ['warehouse_id', 'tenant_id', 'organization_id', 'location_id'],
            ['warehouses.id', 'warehouses.tenant_id', 'warehouses.organization_id',
             'warehouses.location_id'],
            name='fk_inventory_losses_warehouse_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            ['inventory_items.id', 'inventory_items.tenant_id',
             'inventory_items.organization_id', 'inventory_items.location_id'],
            name='fk_inventory_losses_item_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['conversion_revision_id', 'tenant_id', 'organization_id', 'location_id',
             'inventory_item_id'],
            ['item_uom_conversions.id', 'item_uom_conversions.tenant_id',
             'item_uom_conversions.organization_id',
             'item_uom_conversions.location_id',
             'item_uom_conversions.inventory_item_id'],
            name='fk_inventory_losses_conversion_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['standard_cost_revision_id', 'tenant_id', 'organization_id',
             'location_id', 'inventory_item_id'],
            ['inventory_cost_revisions.id', 'inventory_cost_revisions.tenant_id',
             'inventory_cost_revisions.organization_id',
             'inventory_cost_revisions.location_id',
             'inventory_cost_revisions.inventory_item_id'],
            name='fk_inventory_losses_cost_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id',
            'inventory_item_id', name='uq_inventory_losses_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'post_actor_scope', 'post_idempotency_key',
            name='uq_inventory_losses_post_idempotency',
        ),
        UniqueConstraint(
            'tenant_id', 'approval_actor_scope', 'approval_idempotency_key',
            name='uq_inventory_losses_approval_idempotency',
        ),
        UniqueConstraint(
            'tenant_id', 'reversal_actor_scope', 'reversal_idempotency_key',
            name='uq_inventory_losses_reversal_idempotency',
        ),
        CheckConstraint(
            "category IN ('WASTE','SPOILAGE','BREAKAGE','EXPIRY',"
            "'PREPARATION_LOSS','OTHER')",
            name='ck_inventory_losses_category',
        ),
        CheckConstraint(
            "status IN ('DRAFT','PENDING_APPROVAL','POSTED','CANCELLED','REVERSED')",
            name='ck_inventory_losses_status',
        ),
        CheckConstraint('source_quantity > 0', name='ck_inventory_losses_quantity'),
        CheckConstraint(
            "source_uom REGEXP '^[A-Z][A-Z0-9_]{0,31}$'",
            name='ck_inventory_losses_source_uom',
        ),
        CheckConstraint(
            "category<>'OTHER' OR reason IS NOT NULL",
            name='ck_inventory_losses_other_reason',
        ),
        CheckConstraint(
            "evidence_status IN ('PENDING','RESOLVED','COST_NON_DERIVABLE')",
            name='ck_inventory_losses_evidence_status',
        ),
        CheckConstraint(
            "(evidence_status='PENDING' AND conversion_factor IS NULL AND "
            "base_uom_evidence IS NULL AND normalized_quantity IS NULL AND "
            "standard_cost_revision_id IS NULL AND standard_unit_cost_evidence IS NULL "
            "AND cost_currency_evidence IS NULL AND extended_loss_cost IS NULL) OR "
            "(evidence_status='RESOLVED' AND conversion_factor>0 AND "
            "base_uom_evidence IS NOT NULL AND normalized_quantity>0 AND "
            "standard_cost_revision_id IS NOT NULL AND standard_unit_cost_evidence>=0 "
            "AND cost_currency_evidence IS NOT NULL AND extended_loss_cost>=0) OR "
            "(evidence_status='COST_NON_DERIVABLE' AND conversion_factor>0 AND "
            "base_uom_evidence IS NOT NULL AND normalized_quantity>0 AND "
            "standard_cost_revision_id IS NULL AND standard_unit_cost_evidence IS NULL "
            "AND cost_currency_evidence IS NULL AND extended_loss_cost IS NULL)",
            name='ck_inventory_losses_evidence',
        ),
        CheckConstraint(
            '(approved_by_actor_id IS NULL OR approval_requested_by_actor_id IS NULL '
            'OR approved_by_actor_id<>approval_requested_by_actor_id)',
            name='ck_inventory_losses_separation',
        ),
        CheckConstraint(
            "approval_reason IS NULL OR approval_reason IN ('BELOW_THRESHOLD',"
            "'VALUE_THRESHOLD','COST_NON_DERIVABLE','CURRENCY_MISMATCH','NO_POLICY')",
            name='ck_inventory_losses_approval_reason',
        ),
        CheckConstraint(
            "(status='DRAFT' AND evidence_status='PENDING' AND posted_at IS NULL "
            "AND cancelled_at IS NULL AND reversed_at IS NULL) OR "
            "(status='PENDING_APPROVAL' AND approval_required=1 AND "
            "evidence_status<>'PENDING' AND approval_requested_at IS NOT NULL AND "
            "approval_requested_by_actor_id IS NOT NULL AND post_actor_scope IS NOT NULL "
            "AND post_idempotency_key IS NOT NULL AND post_fingerprint IS NOT NULL "
            "AND posted_at IS NULL AND cancelled_at IS NULL AND reversed_at IS NULL) OR "
            "(status='POSTED' AND evidence_status<>'PENDING' AND posted_at IS NOT NULL "
            "AND posted_by_actor_id IS NOT NULL AND post_actor_scope IS NOT NULL "
            "AND post_idempotency_key IS NOT NULL AND post_fingerprint IS NOT NULL "
            "AND cancelled_at IS NULL AND reversed_at IS NULL AND "
            "(approval_required=0 OR (approved_at IS NOT NULL AND "
            "approved_by_actor_id IS NOT NULL))) OR "
            "(status='CANCELLED' AND cancelled_at IS NOT NULL AND "
            "cancelled_by_actor_id IS NOT NULL AND posted_at IS NULL AND reversed_at IS NULL) OR "
            "(status='REVERSED' AND evidence_status<>'PENDING' AND posted_at IS NOT NULL "
            "AND posted_by_actor_id IS NOT NULL AND reversed_at IS NOT NULL AND "
            "reversed_by_actor_id IS NOT NULL AND reversal_actor_scope IS NOT NULL AND "
            "reversal_idempotency_key IS NOT NULL AND reversal_fingerprint IS NOT NULL "
            "AND cancelled_at IS NULL)",
            name='ck_inventory_losses_lifecycle',
        ),
        CheckConstraint('version >= 1', name='ck_inventory_losses_version'),
        Index(
            'ix_inventory_losses_location_status', 'tenant_id', 'location_id',
            'status', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    source_quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    source_uom: Mapped[str] = mapped_column(
        String(32, collation='ascii_bin'), nullable=False
    )
    conversion_revision_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversion_factor: Mapped[Decimal | None] = mapped_column(
        Numeric(25, 12), nullable=True
    )
    base_uom_evidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    normalized_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 6), nullable=True
    )
    standard_cost_revision_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    standard_unit_cost_evidence: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 6), nullable=True
    )
    cost_currency_evidence: Mapped[str | None] = mapped_column(
        String(3, collation='ascii_bin'), nullable=True
    )
    extended_loss_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(31, 12), nullable=True
    )
    evidence_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default='PENDING', server_default=text("'PENDING'")
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    created_by_actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default='DRAFT', server_default=text("'DRAFT'")
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )
    approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text('0')
    )
    approval_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approval_requested_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    approval_requested_by_actor_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    approved_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    posted_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    cancelled_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    reversed_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    post_actor_scope: Mapped[str | None] = mapped_column(
        String(200, collation='ascii_bin'), nullable=True
    )
    post_idempotency_key: Mapped[str | None] = mapped_column(
        String(128, collation='ascii_bin'), nullable=True
    )
    post_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
    approval_actor_scope: Mapped[str | None] = mapped_column(
        String(200, collation='ascii_bin'), nullable=True
    )
    approval_idempotency_key: Mapped[str | None] = mapped_column(
        String(128, collation='ascii_bin'), nullable=True
    )
    approval_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )
    reversal_actor_scope: Mapped[str | None] = mapped_column(
        String(200, collation='ascii_bin'), nullable=True
    )
    reversal_idempotency_key: Mapped[str | None] = mapped_column(
        String(128, collation='ascii_bin'), nullable=True
    )
    reversal_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )


class PhysicalCount(TimestampMixin, Base):
    __tablename__ = 'physical_counts'
    __table_args__ = (
        ForeignKeyConstraint(
            ['warehouse_id', 'tenant_id', 'organization_id', 'location_id'],
            ['warehouses.id', 'warehouses.tenant_id', 'warehouses.organization_id',
             'warehouses.location_id'],
            name='fk_physical_counts_warehouse_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id',
            name='uq_physical_counts_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'post_actor_scope', 'post_idempotency_key',
            name='uq_physical_counts_post_idempotency',
        ),
        CheckConstraint(
            "count_scope IN ('PARTIAL','FULL')", name='ck_physical_counts_scope',
        ),
        CheckConstraint(
            "status IN ('DRAFT','COUNTING','SUBMITTED','APPROVED','POSTED','CANCELLED')",
            name='ck_physical_counts_status',
        ),
        CheckConstraint('version >= 1', name='ck_physical_counts_version'),
        Index(
            'ix_physical_counts_location_status', 'tenant_id', 'location_id',
            'status', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    count_scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default='PARTIAL', server_default=text("'PARTIAL'")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='DRAFT', server_default=text("'DRAFT'")
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    cursor_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    cursor_movement_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    opened_by_actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    submitted_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    approved_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    posted_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    cancelled_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )
    post_actor_scope: Mapped[str | None] = mapped_column(
        String(200, collation='ascii_bin'), nullable=True
    )
    post_idempotency_key: Mapped[str | None] = mapped_column(
        String(128, collation='ascii_bin'), nullable=True
    )
    post_fingerprint: Mapped[str | None] = mapped_column(
        String(64, collation='ascii_bin'), nullable=True
    )


class PhysicalCountLine(Base):
    __tablename__ = 'physical_count_lines'
    __table_args__ = (
        ForeignKeyConstraint(
            ['physical_count_id', 'tenant_id', 'organization_id', 'location_id',
             'warehouse_id'],
            ['physical_counts.id', 'physical_counts.tenant_id',
             'physical_counts.organization_id', 'physical_counts.location_id',
             'physical_counts.warehouse_id'],
            name='fk_physical_count_lines_count_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            ['inventory_items.id', 'inventory_items.tenant_id',
             'inventory_items.organization_id', 'inventory_items.location_id'],
            name='fk_physical_count_lines_item_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['conversion_revision_id', 'tenant_id', 'organization_id', 'location_id',
             'inventory_item_id'],
            ['item_uom_conversions.id', 'item_uom_conversions.tenant_id',
             'item_uom_conversions.organization_id',
             'item_uom_conversions.location_id',
             'item_uom_conversions.inventory_item_id'],
            name='fk_physical_count_lines_conversion_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['standard_cost_revision_id', 'tenant_id', 'organization_id',
             'location_id', 'inventory_item_id'],
            ['inventory_cost_revisions.id', 'inventory_cost_revisions.tenant_id',
             'inventory_cost_revisions.organization_id',
             'inventory_cost_revisions.location_id',
             'inventory_cost_revisions.inventory_item_id'],
            name='fk_physical_count_lines_cost_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'warehouse_id',
            'physical_count_id', 'inventory_item_id',
            name='uq_physical_count_lines_scope',
        ),
        UniqueConstraint(
            'physical_count_id', 'inventory_item_id',
            name='uq_physical_count_lines_item',
        ),
        CheckConstraint('source_quantity >= 0', name='ck_physical_count_lines_source'),
        CheckConstraint('conversion_factor > 0', name='ck_physical_count_lines_factor'),
        CheckConstraint(
            "evidence_status IN ('RESOLVED','COST_NON_DERIVABLE')",
            name='ck_physical_count_lines_evidence_status',
        ),
        CheckConstraint('version >= 1', name='ck_physical_count_lines_version'),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    physical_count_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_quantity_at_cursor: Mapped[Decimal] = mapped_column(
        Numeric(19, 6), nullable=False
    )
    source_quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    source_uom: Mapped[str] = mapped_column(
        String(32, collation='ascii_bin'), nullable=False
    )
    conversion_revision_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversion_factor: Mapped[Decimal] = mapped_column(Numeric(25, 12), nullable=False)
    base_uom_evidence: Mapped[str] = mapped_column(String(16), nullable=False)
    normalized_counted_quantity: Mapped[Decimal] = mapped_column(
        Numeric(19, 6), nullable=False
    )
    variance_quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    standard_cost_revision_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    standard_unit_cost_evidence: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 6), nullable=True
    )
    cost_currency_evidence: Mapped[str | None] = mapped_column(
        String(3, collation='ascii_bin'), nullable=True
    )
    variance_value: Mapped[Decimal | None] = mapped_column(Numeric(31, 12), nullable=True)
    evidence_status: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1, server_default=text('1')
    )
    counted_by_actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    counted_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class InventoryReconciliation(TimestampMixin, Base):
    __tablename__ = 'inventory_reconciliations'
    __table_args__ = (
        ForeignKeyConstraint(
            ['physical_count_line_id', 'tenant_id', 'organization_id', 'location_id',
             'warehouse_id', 'physical_count_id', 'inventory_item_id'],
            ['physical_count_lines.id', 'physical_count_lines.tenant_id',
             'physical_count_lines.organization_id',
             'physical_count_lines.location_id', 'physical_count_lines.warehouse_id',
             'physical_count_lines.physical_count_id',
             'physical_count_lines.inventory_item_id'],
            name='fk_inventory_reconciliations_line_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'physical_count_line_id', name='uq_inventory_reconciliations_count_line'
        ),
        CheckConstraint("status IN ('OPEN','CLOSED')", name='ck_inventory_reconciliations_status'),
        CheckConstraint('period_start < period_end', name='ck_inventory_reconciliations_period'),
        CheckConstraint('version >= 1', name='ck_inventory_reconciliations_version'),
        Index(
            'ix_inventory_reconciliations_location_status', 'tenant_id',
            'location_id', 'status', 'id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    physical_count_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    physical_count_line_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='OPEN', server_default=text("'OPEN'")
    )
    opening_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    receiving_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    theoretical_consumption_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    dedicated_loss_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    other_adjustment_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    physical_count_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    count_adjustment_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    theoretical_closing_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    closing_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    variance_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    variance_percentage: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    standard_cost_revision_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    standard_unit_cost_evidence: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    cost_currency_evidence: Mapped[str | None] = mapped_column(String(3, collation='ascii_bin'), nullable=True)
    variance_value: Mapped[Decimal | None] = mapped_column(Numeric(31, 12), nullable=True)
    evidence_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_by_actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    closed_by_actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default=text('1'))


class StockMovement(Base):
    __tablename__ = 'stock_movements'
    __table_args__ = (
        ForeignKeyConstraint(
            ['warehouse_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'warehouses.id', 'warehouses.tenant_id',
                'warehouses.organization_id', 'warehouses.location_id',
            ],
            name='fk_stock_movements_warehouse_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['inventory_item_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'inventory_items.id', 'inventory_items.tenant_id',
                'inventory_items.organization_id', 'inventory_items.location_id',
            ],
            name='fk_stock_movements_item_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'conversion_revision_id', 'tenant_id', 'organization_id',
                'location_id', 'inventory_item_id',
            ],
            [
                'item_uom_conversions.id', 'item_uom_conversions.tenant_id',
                'item_uom_conversions.organization_id',
                'item_uom_conversions.location_id',
                'item_uom_conversions.inventory_item_id',
            ],
            name='fk_stock_movements_conversion_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'standard_cost_revision_id', 'tenant_id', 'organization_id',
                'location_id', 'inventory_item_id',
            ],
            [
                'inventory_cost_revisions.id', 'inventory_cost_revisions.tenant_id',
                'inventory_cost_revisions.organization_id',
                'inventory_cost_revisions.location_id',
                'inventory_cost_revisions.inventory_item_id',
            ],
            name='fk_stock_movements_cost_revision_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'consumption_version_id', 'tenant_id', 'organization_id',
                'location_id', 'consumption_definition_id',
            ],
            [
                'product_consumption_versions.id',
                'product_consumption_versions.tenant_id',
                'product_consumption_versions.organization_id',
                'product_consumption_versions.location_id',
                'product_consumption_versions.definition_id',
            ],
            name='fk_stock_movements_consumption_version_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'consumption_version_component_id', 'tenant_id', 'organization_id',
                'location_id', 'consumption_definition_id',
                'consumption_version_id',
            ],
            [
                'product_consumption_version_components.id',
                'product_consumption_version_components.tenant_id',
                'product_consumption_version_components.organization_id',
                'product_consumption_version_components.location_id',
                'product_consumption_version_components.definition_id',
                'product_consumption_version_components.version_id',
            ],
            name='fk_stock_movements_version_component_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'reversal_of_movement_id', 'tenant_id', 'organization_id',
                'location_id', 'inventory_item_id', 'warehouse_id',
            ],
            [
                'stock_movements.id', 'stock_movements.tenant_id',
                'stock_movements.organization_id', 'stock_movements.location_id',
                'stock_movements.inventory_item_id', 'stock_movements.warehouse_id',
            ],
            name='fk_stock_movements_reversal_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'restaurant_order_consumption_id', 'tenant_id', 'organization_id',
                'location_id', 'restaurant_order_id',
            ],
            [
                'restaurant_order_consumptions.id',
                'restaurant_order_consumptions.tenant_id',
                'restaurant_order_consumptions.organization_id',
                'restaurant_order_consumptions.location_id',
                'restaurant_order_consumptions.restaurant_order_id',
            ],
            name='fk_stock_movements_order_consumption_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'],
            [
                'restaurant_order_items.id', 'restaurant_order_items.tenant_id',
                'restaurant_order_items.order_id',
            ],
            name='fk_stock_movements_order_item_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'restaurant_order_item_component_id', 'tenant_id',
                'restaurant_order_id', 'restaurant_order_item_id',
            ],
            [
                'restaurant_order_item_components.id',
                'restaurant_order_item_components.tenant_id',
                'restaurant_order_item_components.order_id',
                'restaurant_order_item_components.order_item_id',
            ],
            name='fk_stock_movements_order_component_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'goods_receipt_line_id', 'tenant_id', 'organization_id',
                'location_id', 'goods_receipt_id', 'inventory_item_id',
            ],
            [
                'goods_receipt_lines.id', 'goods_receipt_lines.tenant_id',
                'goods_receipt_lines.organization_id',
                'goods_receipt_lines.location_id',
                'goods_receipt_lines.goods_receipt_id',
                'goods_receipt_lines.inventory_item_id',
            ],
            name='fk_stock_movements_receipt_line_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['inventory_loss_id', 'tenant_id', 'organization_id', 'location_id',
             'warehouse_id', 'inventory_item_id'],
            ['inventory_losses.id', 'inventory_losses.tenant_id',
             'inventory_losses.organization_id', 'inventory_losses.location_id',
             'inventory_losses.warehouse_id', 'inventory_losses.inventory_item_id'],
            name='fk_stock_movements_loss_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['physical_count_line_id', 'tenant_id', 'organization_id', 'location_id',
             'warehouse_id', 'physical_count_id', 'inventory_item_id'],
            ['physical_count_lines.id', 'physical_count_lines.tenant_id',
             'physical_count_lines.organization_id',
             'physical_count_lines.location_id', 'physical_count_lines.warehouse_id',
             'physical_count_lines.physical_count_id',
             'physical_count_lines.inventory_item_id'],
            name='fk_stock_movements_count_line_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['source_product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_stock_movements_source_product_scope', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            [
                'consumption_definition_id', 'tenant_id', 'organization_id',
                'location_id',
            ],
            [
                'product_consumption_definitions.id',
                'product_consumption_definitions.tenant_id',
                'product_consumption_definitions.organization_id',
                'product_consumption_definitions.location_id',
            ],
            name='fk_stock_movements_definition_scope', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id', 'inventory_item_id',
            name='uq_stock_movements_scope',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id', 'location_id',
            'inventory_item_id', 'warehouse_id',
            name='uq_stock_movements_warehouse_scope',
        ),
        UniqueConstraint(
            'tenant_id', 'idempotency_actor_scope', 'idempotency_key',
            name='uq_stock_movements_idempotency',
        ),
        UniqueConstraint(
            'inventory_item_id', 'opening_balance_slot',
            name='uq_stock_movements_opening_balance',
        ),
        UniqueConstraint(
            'reversal_of_movement_id', name='uq_stock_movements_direct_reversal'
        ),
        UniqueConstraint(
            'restaurant_order_consumption_id', 'consumption_source_key',
            name='uq_stock_movements_consumption_source',
        ),
        UniqueConstraint(
            'goods_receipt_line_id', name='uq_stock_movements_receipt_line'
        ),
        UniqueConstraint(
            'inventory_loss_id', 'loss_movement_role',
            name='uq_stock_movements_loss_role',
        ),
        UniqueConstraint(
            'physical_count_line_id', name='uq_stock_movements_count_line',
        ),
        CheckConstraint(
            "movement_type IN ('OPENING_BALANCE','MANUAL_IN','MANUAL_OUT',"
            "'ADJUSTMENT','REVERSAL','CONSUMPTION','GOODS_RECEIPT','WASTE')",
            name='ck_stock_movements_type',
        ),
        CheckConstraint('quantity <> 0', name='ck_stock_movements_nonzero'),
        CheckConstraint(
            "(movement_type IN ('OPENING_BALANCE','MANUAL_IN','GOODS_RECEIPT') "
            "AND quantity>0) OR "
            "(movement_type IN ('MANUAL_OUT','CONSUMPTION','WASTE') AND quantity<0) OR "
            "(movement_type IN ('ADJUSTMENT','REVERSAL') AND quantity<>0)",
            name='ck_stock_movements_sign',
        ),
        CheckConstraint(
            "(movement_type='OPENING_BALANCE' AND opening_balance_slot=1) OR "
            "(movement_type<>'OPENING_BALANCE' AND opening_balance_slot IS NULL)",
            name='ck_stock_movements_opening_slot',
        ),
        CheckConstraint(
            "(movement_type='REVERSAL' AND reversal_of_movement_id IS NOT NULL) OR "
            "(movement_type<>'REVERSAL' AND reversal_of_movement_id IS NULL)",
            name='ck_stock_movements_reversal',
        ),
        CheckConstraint(
            "movement_type='OPENING_BALANCE' OR "
            "(reason IS NOT NULL AND TRIM(reason)<>'')",
            name='ck_stock_movements_reason',
        ),
        CheckConstraint('request_schema_version >= 1', name='ck_stock_movements_version'),
        CheckConstraint(
            "negative_stock_policy IN ('ALLOW','WARN','BLOCK')",
            name='ck_stock_movements_negative_policy',
        ),
        CheckConstraint(
            "evidence_status IN ('LEGACY_UNAVAILABLE','LEGACY_SNAPSHOT','RESOLVED',"
            "'COST_NON_DERIVABLE')", name='ck_stock_movements_evidence_status',
        ),
        CheckConstraint(
            '(conversion_factor IS NULL OR conversion_factor > 0) AND '
            '(standard_unit_cost_evidence IS NULL OR standard_unit_cost_evidence >= 0)',
            name='ck_stock_movements_operational_evidence_values',
        ),
        CheckConstraint(
            "(evidence_status IN ('RESOLVED','COST_NON_DERIVABLE') AND "
            'source_quantity IS NOT NULL AND source_uom IS NOT NULL AND '
            'conversion_factor IS NOT NULL AND base_uom_evidence IS NOT NULL) OR '
            "(evidence_status='LEGACY_SNAPSHOT' AND source_quantity IS NOT NULL AND "
            'source_uom IS NOT NULL AND conversion_factor IS NOT NULL AND '
            'base_uom_evidence IS NOT NULL) OR '
            "evidence_status='LEGACY_UNAVAILABLE'",
            name='ck_stock_movements_quantity_evidence',
        ),
        CheckConstraint(
            "(evidence_status='RESOLVED' AND standard_cost_revision_id IS NOT NULL "
            'AND standard_unit_cost_evidence IS NOT NULL AND '
            'cost_currency_evidence IS NOT NULL AND extended_standard_cost IS NOT NULL) OR '
            "(evidence_status='COST_NON_DERIVABLE' AND "
            'standard_cost_revision_id IS NULL AND standard_unit_cost_evidence IS NULL '
            'AND cost_currency_evidence IS NULL AND extended_standard_cost IS NULL) OR '
            "evidence_status IN ('LEGACY_UNAVAILABLE','LEGACY_SNAPSHOT')",
            name='ck_stock_movements_standard_cost_evidence',
        ),
        CheckConstraint(
            "(actor_type='EMPLOYEE' AND actor_id IS NOT NULL AND actor_reference IS NULL) OR "
            "(actor_type IN ('SYSTEM','AGENT','EXTERNAL_SYSTEM') AND actor_id IS NULL "
            "AND actor_reference IS NOT NULL)",
            name='ck_stock_movements_actor',
        ),
        CheckConstraint(
            "(movement_type='CONSUMPTION' AND "
            'restaurant_order_consumption_id IS NOT NULL AND '
            'restaurant_order_id IS NOT NULL AND restaurant_order_item_id IS NOT NULL AND '
            'source_product_id IS NOT NULL AND consumption_definition_id IS NOT NULL AND '
            'consumption_definition_version IS NOT NULL AND '
            'inventory_item_name_snapshot IS NOT NULL AND base_uom_snapshot IS NOT NULL AND '
            'unit_cost_snapshot IS NOT NULL AND currency_snapshot IS NOT NULL AND '
            'extended_cost_snapshot IS NOT NULL AND consumption_source_key IS NOT NULL) OR '
            "(movement_type<>'CONSUMPTION' AND "
            'restaurant_order_consumption_id IS NULL AND restaurant_order_id IS NULL AND '
            'restaurant_order_item_id IS NULL AND restaurant_order_item_component_id IS NULL AND '
            'source_product_id IS NULL AND consumption_definition_id IS NULL AND '
            'consumption_definition_version IS NULL AND inventory_item_name_snapshot IS NULL AND '
            'base_uom_snapshot IS NULL AND unit_cost_snapshot IS NULL AND '
            'currency_snapshot IS NULL AND extended_cost_snapshot IS NULL AND '
            'consumption_source_key IS NULL)',
            name='ck_stock_movements_consumption_evidence',
        ),
        CheckConstraint(
            "(movement_type='GOODS_RECEIPT' AND goods_receipt_id IS NOT NULL AND "
            "goods_receipt_line_id IS NOT NULL) OR "
            "(movement_type<>'GOODS_RECEIPT' AND goods_receipt_id IS NULL AND "
            "goods_receipt_line_id IS NULL)",
            name='ck_stock_movements_receipt_evidence',
        ),
        CheckConstraint(
            "(movement_type='WASTE' AND inventory_loss_id IS NOT NULL AND "
            "loss_movement_role='ORIGINAL') OR "
            "(movement_type='REVERSAL' AND ((inventory_loss_id IS NULL AND "
            "loss_movement_role IS NULL) OR (inventory_loss_id IS NOT NULL AND "
            "loss_movement_role='REVERSAL'))) OR "
            "(movement_type NOT IN ('WASTE','REVERSAL') AND inventory_loss_id IS NULL "
            "AND loss_movement_role IS NULL)",
            name='ck_stock_movements_loss_evidence',
        ),
        CheckConstraint(
            "(movement_type='ADJUSTMENT' AND ((physical_count_id IS NULL AND "
            "physical_count_line_id IS NULL) OR (physical_count_id IS NOT NULL AND "
            "physical_count_line_id IS NOT NULL))) OR (movement_type<>'ADJUSTMENT' AND "
            "physical_count_id IS NULL AND physical_count_line_id IS NULL)",
            name='ck_stock_movements_count_evidence',
        ),
        CheckConstraint(
            '(unit_cost_snapshot IS NULL OR unit_cost_snapshot >= 0) AND '
            '(extended_cost_snapshot IS NULL OR extended_cost_snapshot >= 0)',
            name='ck_stock_movements_consumption_cost',
        ),
        Index(
            'ix_stock_movements_stock', 'tenant_id', 'location_id',
            'inventory_item_id', 'recorded_at', 'id',
        ),
        Index(
            'ix_stock_movements_warehouse_stock', 'tenant_id', 'location_id',
            'warehouse_id', 'inventory_item_id', 'recorded_at', 'id',
        ),
        Index(
            'ix_stock_movements_order_consumption', 'tenant_id',
            'restaurant_order_id', 'restaurant_order_item_id', 'id',
        ),
        Index(
            'ix_stock_movements_receipt', 'tenant_id', 'goods_receipt_id',
            'goods_receipt_line_id',
        ),
        Index(
            'ix_stock_movements_loss', 'tenant_id', 'inventory_loss_id',
            'loss_movement_role',
        ),
        Index(
            'ix_stock_movements_count', 'tenant_id', 'physical_count_id',
            'physical_count_line_id',
        ),
        OPTIONS,
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False)
    reversal_of_movement_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_reference: Mapped[str | None] = mapped_column(
        String(200, collation='utf8mb4_bin'), nullable=True
    )
    opening_balance_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    idempotency_actor_scope: Mapped[str] = mapped_column(
        String(200, collation='ascii_bin'), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128, collation='ascii_bin'), nullable=False
    )
    request_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    negative_stock_policy: Mapped[str] = mapped_column(
        String(8), nullable=False, default='ALLOW', server_default=text("'ALLOW'")
    )
    negative_stock_warning: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text('0')
    )
    resulting_stock_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 6), nullable=True
    )
    source_quantity: Mapped[Decimal | None] = mapped_column(Numeric(19, 6), nullable=True)
    source_uom: Mapped[str | None] = mapped_column(
        String(32, collation='ascii_bin'), nullable=True
    )
    conversion_revision_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversion_factor: Mapped[Decimal | None] = mapped_column(
        Numeric(25, 12), nullable=True
    )
    base_uom_evidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    standard_cost_revision_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    standard_unit_cost_evidence: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 6), nullable=True
    )
    cost_currency_evidence: Mapped[str | None] = mapped_column(
        String(3, collation='ascii_bin'), nullable=True
    )
    extended_standard_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(31, 12), nullable=True
    )
    evidence_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default='LEGACY_UNAVAILABLE',
        server_default=text("'LEGACY_UNAVAILABLE'"),
    )
    goods_receipt_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    goods_receipt_line_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    inventory_loss_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    loss_movement_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    physical_count_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    physical_count_line_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    restaurant_order_consumption_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    restaurant_order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    restaurant_order_item_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    restaurant_order_item_component_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    source_product_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    consumption_definition_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    consumption_definition_version: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    consumption_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    consumption_version_component_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    inventory_item_name_snapshot: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    base_uom_snapshot: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_cost_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 6), nullable=True
    )
    currency_snapshot: Mapped[str | None] = mapped_column(
        String(3, collation='ascii_bin'), nullable=True
    )
    extended_cost_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(31, 12), nullable=True
    )
    consumption_source_key: Mapped[str | None] = mapped_column(
        String(128, collation='ascii_bin'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
