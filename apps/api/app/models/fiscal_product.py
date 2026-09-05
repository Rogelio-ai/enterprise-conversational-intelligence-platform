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


class ProductFiscalClassification(TimestampMixin, Base):
    __tablename__ = 'product_fiscal_classifications'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_product_fiscal_classifications_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_product_fiscal_classifications_org', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['product_id', 'tenant_id', 'organization_id'],
            ['products.id', 'products.tenant_id', 'products.organization_id'],
            name='fk_product_fiscal_classifications_product', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'id', 'tenant_id', 'organization_id',
            name='uq_product_fiscal_classifications_scope',
        ),
        CheckConstraint(
            'effective_to IS NULL OR effective_from < effective_to',
            name='ck_product_fiscal_classifications_interval',
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name='ck_product_fiscal_classifications_status',
        ),
        Index(
            'ix_product_fiscal_classifications_resolution',
            'tenant_id', 'organization_id', 'product_id',
            'fiscal_jurisdiction_code', 'status', 'effective_from', 'effective_to', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fiscal_jurisdiction_code: Mapped[str] = mapped_column(
        String(16, collation='utf8mb4_bin'), nullable=False
    )
    product_classification_scheme: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    product_classification_code: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    unit_classification_scheme: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    unit_classification_code: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'")
    )


class RestaurantOrderItemFiscalSnapshot(Base):
    __tablename__ = 'restaurant_order_item_fiscal_snapshots'
    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'],
            name='fk_order_item_fiscal_snapshots_tenant', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['organization_id', 'tenant_id'],
            ['organizations.id', 'organizations.tenant_id'],
            name='fk_order_item_fiscal_snapshots_org', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['location_id', 'tenant_id', 'organization_id'],
            ['locations.id', 'locations.tenant_id', 'locations.organization_id'],
            name='fk_order_item_fiscal_snapshots_location', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_order_id', 'tenant_id', 'organization_id', 'location_id'],
            [
                'restaurant_orders.id', 'restaurant_orders.tenant_id',
                'restaurant_orders.organization_id', 'restaurant_orders.location_id',
            ],
            name='fk_order_item_fiscal_snapshots_order', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['restaurant_order_item_id', 'tenant_id', 'restaurant_order_id'],
            [
                'restaurant_order_items.id', 'restaurant_order_items.tenant_id',
                'restaurant_order_items.order_id',
            ],
            name='fk_order_item_fiscal_snapshots_item', ondelete='RESTRICT',
        ),
        ForeignKeyConstraint(
            ['source_product_fiscal_classification_id', 'tenant_id', 'organization_id'],
            [
                'product_fiscal_classifications.id',
                'product_fiscal_classifications.tenant_id',
                'product_fiscal_classifications.organization_id',
            ],
            name='fk_order_item_fiscal_snapshots_source', ondelete='RESTRICT',
        ),
        UniqueConstraint(
            'restaurant_order_item_id',
            name='uq_order_item_fiscal_snapshots_item',
        ),
        CheckConstraint(
            'schema_version >= 1', name='ck_order_item_fiscal_snapshots_version'
        ),
        Index(
            'ix_order_item_fiscal_snapshots_item',
            'tenant_id', 'restaurant_order_id', 'restaurant_order_item_id', 'id',
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restaurant_order_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_product_fiscal_classification_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    fiscal_jurisdiction_code: Mapped[str] = mapped_column(
        String(16, collation='utf8mb4_bin'), nullable=False
    )
    product_classification_scheme: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    product_classification_code: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    unit_classification_scheme: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    unit_classification_code: Mapped[str] = mapped_column(
        String(64, collation='utf8mb4_bin'), nullable=False
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(
        String(64, collation='ascii_bin'), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), nullable=False, server_default=func.current_timestamp()
    )
