from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.identity import TimestampMixin


class ProductPrice(TimestampMixin, Base):
    __tablename__ = 'product_prices'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_product_prices_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['organization_id', 'tenant_id'], ['organizations.id', 'organizations.tenant_id'], name='fk_product_prices_organization_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['product_id', 'tenant_id', 'organization_id'], ['products.id', 'products.tenant_id', 'products.organization_id'], name='fk_product_prices_product_tenant_org', ondelete='RESTRICT'),
        ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_product_prices_location_tenant_org', ondelete='RESTRICT'),
        UniqueConstraint('tenant_id', 'product_id', 'location_id', name='uq_product_prices_tenant_product_location'),
        CheckConstraint('amount >= 0', name='ck_product_prices_amount'),
        CheckConstraint("OCTET_LENGTH(currency) = 3 AND ASCII(SUBSTRING(currency, 1, 1)) BETWEEN 65 AND 90 AND ASCII(SUBSTRING(currency, 2, 1)) BETWEEN 65 AND 90 AND ASCII(SUBSTRING(currency, 3, 1)) BETWEEN 65 AND 90", name='ck_product_prices_currency'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_product_prices_status'),
        CheckConstraint("source IN ('PLATFORM', 'POS')", name='ck_product_prices_source'),
        Index('ix_product_prices_tenant_org_location_status_product', 'tenant_id', 'organization_id', 'location_id', 'status', 'product_id'),
        Index('ix_product_prices_tenant_org_product_status', 'tenant_id', 'organization_id', 'product_id', 'status'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'"))
    source: Mapped[str] = mapped_column(String(16), nullable=False)


class Promotion(TimestampMixin, Base):
    __tablename__ = 'promotions'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_promotions_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['organization_id', 'tenant_id'], ['organizations.id', 'organizations.tenant_id'], name='fk_promotions_organization_tenant', ondelete='RESTRICT'),
        UniqueConstraint('id', 'tenant_id', 'organization_id', name='uq_promotions_id_tenant_org'),
        CheckConstraint("promotion_type IN ('PERCENTAGE_DISCOUNT', 'FIXED_AMOUNT_DISCOUNT')", name='ck_promotions_type'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_promotions_status'),
        CheckConstraint("source IN ('PLATFORM', 'POS')", name='ck_promotions_source'),
        CheckConstraint('starts_at < ends_at', name='ck_promotions_interval'),
        CheckConstraint("currency IS NULL OR (OCTET_LENGTH(currency) = 3 AND ASCII(SUBSTRING(currency, 1, 1)) BETWEEN 65 AND 90 AND ASCII(SUBSTRING(currency, 2, 1)) BETWEEN 65 AND 90 AND ASCII(SUBSTRING(currency, 3, 1)) BETWEEN 65 AND 90)", name='ck_promotions_currency'),
        CheckConstraint("(promotion_type = 'PERCENTAGE_DISCOUNT' AND benefit_value > 0 AND benefit_value <= 100 AND currency IS NULL) OR (promotion_type = 'FIXED_AMOUNT_DISCOUNT' AND benefit_value > 0 AND currency IS NOT NULL)", name='ck_promotions_benefit'),
        CheckConstraint('applies_to_all_locations IN (0, 1)', name='ck_promotions_all_locations'),
        CheckConstraint('is_combinable IN (0, 1)', name='ck_promotions_is_combinable'),
        CheckConstraint('priority >= 0', name='ck_promotions_priority'),
        Index('ix_promotions_tenant_org_status_type', 'tenant_id', 'organization_id', 'status', 'promotion_type', 'id'),
        Index('ix_promotions_tenant_org_interval', 'tenant_id', 'organization_id', 'starts_at', 'ends_at', 'id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    promotion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    benefit_value: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    applies_to_all_locations: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_combinable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text('0')
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text('0')
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='INACTIVE', server_default=text("'INACTIVE'"))
    source: Mapped[str] = mapped_column(String(16), nullable=False)


class PromotionProduct(TimestampMixin, Base):
    __tablename__ = 'promotion_products'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_promotion_products_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['promotion_id', 'tenant_id', 'organization_id'], ['promotions.id', 'promotions.tenant_id', 'promotions.organization_id'], name='fk_promotion_products_promotion_tenant_org', ondelete='RESTRICT'),
        ForeignKeyConstraint(['product_id', 'tenant_id', 'organization_id'], ['products.id', 'products.tenant_id', 'products.organization_id'], name='fk_promotion_products_product_tenant_org', ondelete='RESTRICT'),
        UniqueConstraint('tenant_id', 'promotion_id', 'product_id', name='uq_promotion_products_tenant_promotion_product'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_promotion_products_status'),
        Index('ix_promotion_products_tenant_product_status', 'tenant_id', 'product_id', 'status', 'promotion_id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    promotion_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'"))


class PromotionLocation(TimestampMixin, Base):
    __tablename__ = 'promotion_locations'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_promotion_locations_tenant', ondelete='RESTRICT'),
        ForeignKeyConstraint(['promotion_id', 'tenant_id', 'organization_id'], ['promotions.id', 'promotions.tenant_id', 'promotions.organization_id'], name='fk_promotion_locations_promotion_tenant_org', ondelete='RESTRICT'),
        ForeignKeyConstraint(['location_id', 'tenant_id', 'organization_id'], ['locations.id', 'locations.tenant_id', 'locations.organization_id'], name='fk_promotion_locations_location_tenant_org', ondelete='RESTRICT'),
        UniqueConstraint('tenant_id', 'promotion_id', 'location_id', name='uq_promotion_locations_tenant_promotion_location'),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='ck_promotion_locations_status'),
        Index('ix_promotion_locations_tenant_location_status', 'tenant_id', 'location_id', 'status', 'promotion_id'),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    promotion_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='ACTIVE', server_default=text("'ACTIVE'"))
